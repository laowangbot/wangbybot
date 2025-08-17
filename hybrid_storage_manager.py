#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
混合存储管理器 - 智能切换Firebase和本地缓存
支持降级策略和自动同步
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from firebase_manager import FirebaseManager
from cloud_storage_manager import LocalCacheManager

class HybridStorageManager:
    """混合存储管理器"""
    
    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.storage_type = os.getenv('STORAGE_TYPE', 'hybrid')  # hybrid, firebase, local
        
        # 初始化存储管理器
        self.firebase = FirebaseManager(bot_id)
        self.local_cache = LocalCacheManager(bot_id, f"cache_{bot_id}")
        
        # 缓存配置
        self.cache_ttl = int(os.getenv('CACHE_TTL', '300'))  # 5分钟缓存
        self.sync_interval = int(os.getenv('SYNC_INTERVAL', '60'))  # 1分钟同步间隔
        
        # 同步状态
        self.last_sync = {}
        self.sync_errors = 0
        self.max_sync_errors = 3
        
        logging.info(f"[{self.bot_id}] 混合存储管理器初始化完成，类型: {self.storage_type}")
    
    def _is_cache_valid(self, cached_data: Dict[str, Any]) -> bool:
        """检查缓存是否有效"""
        if not cached_data or 'cached_at' not in cached_data:
            return False
        
        try:
            cached_time = datetime.fromisoformat(cached_data['cached_at'])
            return datetime.now() - cached_time < timedelta(seconds=self.cache_ttl)
        except:
            return False
    
    async def save_user_config(self, user_id: int, config: Dict[str, Any]) -> bool:
        """保存用户配置"""
        user_id_str = str(user_id)
        success = False
        
        # 1. 保存到本地缓存
        try:
            local_data = {
                user_id_str: {
                    'config': config,
                    'cached_at': datetime.now().isoformat(),
                    'bot_id': self.bot_id
                }
            }
            self.local_cache.save_data('user_configs', local_data)
            logging.info(f"[{self.bot_id}] 用户 {user_id} 配置已保存到本地缓存")
            success = True
        except Exception as e:
            logging.error(f"[{self.bot_id}] 保存到本地缓存失败: {e}")
        
        # 2. 尝试保存到Firebase
        if self.storage_type in ['hybrid', 'firebase']:
            try:
                firebase_success = await self.firebase.save_user_config(user_id, config)
                if firebase_success:
                    logging.info(f"[{self.bot_id}] 用户 {user_id} 配置已保存到Firebase")
                    # 更新同步时间
                    self.last_sync[user_id_str] = datetime.now()
                    self.sync_errors = 0  # 重置错误计数
                else:
                    self.sync_errors += 1
                    logging.warning(f"[{self.bot_id}] Firebase保存失败，错误计数: {self.sync_errors}")
            except Exception as e:
                self.sync_errors += 1
                logging.error(f"[{self.bot_id}] Firebase保存异常: {e}")
        
        return success
    
    async def get_user_config(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户配置"""
        user_id_str = str(user_id)
        
        # 1. 先查本地缓存
        try:
            cached_data = self.local_cache.load_data('user_configs')
            user_cache = cached_data.get(user_id_str, {})
            
            if self._is_cache_valid(user_cache):
                logging.info(f"[{self.bot_id}] 从本地缓存获取用户 {user_id} 配置")
                return user_cache.get('config', {})
        except Exception as e:
            logging.error(f"[{self.bot_id}] 读取本地缓存失败: {e}")
        
        # 2. 从Firebase获取
        if self.storage_type in ['hybrid', 'firebase']:
            try:
                firebase_config = await self.firebase.get_user_config(user_id)
                if firebase_config:
                    # 更新本地缓存
                    local_data = {
                        user_id_str: {
                            'config': firebase_config,
                            'cached_at': datetime.now().isoformat(),
                            'bot_id': self.bot_id
                        }
                    }
                    self.local_cache.save_data('user_configs', local_data)
                    
                    logging.info(f"[{self.bot_id}] 从Firebase获取用户 {user_id} 配置并更新本地缓存")
                    return firebase_config
                else:
                    logging.info(f"[{self.bot_id}] Firebase中未找到用户 {user_id} 配置")
            except Exception as e:
                logging.error(f"[{self.bot_id}] 从Firebase获取配置失败: {e}")
        
        # 3. 降级到本地缓存（即使过期）
        try:
            cached_data = self.local_cache.load_data('user_configs')
            user_cache = cached_data.get(user_id_str, {})
            if user_cache and 'config' in user_cache:
                logging.warning(f"[{self.bot_id}] 使用过期的本地缓存配置")
                return user_cache.get('config', {})
        except Exception as e:
            logging.error(f"[{self.bot_id}] 降级读取本地缓存失败: {e}")
        
        return None
    
    async def save_task_status(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """保存任务状态"""
        success = False
        
        # 1. 保存到本地缓存
        try:
            local_data = {
                task_id: {
                    'task_data': task_data,
                    'cached_at': datetime.now().isoformat(),
                    'bot_id': self.bot_id
                }
            }
            self.local_cache.save_data('running_tasks', local_data)
            success = True
        except Exception as e:
            logging.error(f"[{self.bot_id}] 保存任务状态到本地缓存失败: {e}")
        
        # 2. 保存到Firebase
        if self.storage_type in ['hybrid', 'firebase']:
            try:
                firebase_success = await self.firebase.save_task_status(task_id, task_data)
                if firebase_success:
                    logging.info(f"[{self.bot_id}] 任务 {task_id} 状态已保存到Firebase")
                else:
                    logging.warning(f"[{self.bot_id}] 任务状态保存到Firebase失败")
            except Exception as e:
                logging.error(f"[{self.bot_id}] 保存任务状态到Firebase异常: {e}")
        
        return success
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        # 1. 先查本地缓存
        try:
            cached_data = self.local_cache.load_data('running_tasks')
            task_cache = cached_data.get(task_id, {})
            
            if self._is_cache_valid(task_cache):
                return task_cache.get('task_data', {})
        except Exception as e:
            logging.error(f"[{self.bot_id}] 读取任务状态缓存失败: {e}")
        
        # 2. 从Firebase获取
        if self.storage_type in ['hybrid', 'firebase']:
            try:
                firebase_task = await self.firebase.get_task_status(task_id)
                if firebase_task:
                    # 更新本地缓存
                    local_data = {
                        task_id: {
                            'task_data': firebase_task,
                            'cached_at': datetime.now().isoformat(),
                            'bot_id': self.bot_id
                        }
                    }
                    self.local_cache.save_data('running_tasks', local_data)
                    return firebase_task
            except Exception as e:
                logging.error(f"[{self.bot_id}] 从Firebase获取任务状态失败: {e}")
        
        return None
    
    async def sync_all_data(self) -> Dict[str, Any]:
        """同步所有数据"""
        sync_results = {
            'users_synced': 0,
            'tasks_synced': 0,
            'errors': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        if self.storage_type not in ['hybrid', 'firebase']:
            logging.info(f"[{self.bot_id}] 当前存储类型不支持同步: {self.storage_type}")
            return sync_results
        
        try:
            # 同步用户配置
            users = await self.firebase.get_all_users()
            for user in users:
                try:
                    user_id = user.get('user_id')
                    config = user.get('config', {})
                    if user_id and config:
                        await self.save_user_config(user_id, config)
                        sync_results['users_synced'] += 1
                except Exception as e:
                    sync_results['errors'] += 1
                    logging.error(f"[{self.bot_id}] 同步用户 {user.get('user_id')} 失败: {e}")
            
            logging.info(f"[{self.bot_id}] 数据同步完成: {sync_results}")
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 数据同步失败: {e}")
            sync_results['errors'] += 1
        
        return sync_results
    
    async def get_storage_health(self) -> Dict[str, Any]:
        """获取存储健康状态"""
        health = {
            'bot_id': self.bot_id,
            'storage_type': self.storage_type,
            'firebase_health': self.firebase.get_health_status(),
            'local_cache_health': self.local_cache.get_cache_info(),
            'sync_status': {
                'last_sync_count': len(self.last_sync),
                'sync_errors': self.sync_errors,
                'is_healthy': self.sync_errors < self.max_sync_errors
            },
            'timestamp': datetime.now().isoformat()
        }
        
        return health
    
    async def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """清理旧数据"""
        cleanup_results = {
            'users_cleaned': 0,
            'tasks_cleaned': 0,
            'cache_cleaned': 0
        }
        
        try:
            # 清理过期的本地缓存
            cached_data = self.local_cache.load_data('user_configs')
            current_time = datetime.now()
            
            for user_id, user_data in list(cached_data.items()):
                try:
                    cached_time = datetime.fromisoformat(user_data.get('cached_at', '1970-01-01'))
                    if current_time - cached_time > timedelta(days=days):
                        del cached_data[user_id]
                        cleanup_results['users_cleaned'] += 1
                except:
                    pass
            
            # 保存清理后的数据
            self.local_cache.save_data('user_configs', cached_data)
            
            logging.info(f"[{self.bot_id}] 数据清理完成: {cleanup_results}")
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 数据清理失败: {e}")
        
        return cleanup_results
    
    async def close(self):
        """关闭存储管理器"""
        try:
            await self.firebase.close()
            logging.info(f"[{self.bot_id}] 混合存储管理器已关闭")
        except Exception as e:
            logging.error(f"[{self.bot_id}] 关闭存储管理器失败: {e}")

# 测试函数
async def test_hybrid_storage():
    """测试混合存储管理器"""
    manager = HybridStorageManager('test_bot')
    
    # 测试保存用户配置
    test_config = {
        'language': 'zh-CN',
        'theme': 'dark',
        'notifications': True
    }
    
    success = await manager.save_user_config(12345, test_config)
    print(f"保存用户配置: {'成功' if success else '失败'}")
    
    # 测试获取用户配置
    config = await manager.get_user_config(12345)
    print(f"获取用户配置: {config}")
    
    # 测试获取存储健康状态
    health = await manager.get_storage_health()
    print(f"存储健康状态: {health}")
    
    await manager.close()

if __name__ == "__main__":
    # 设置环境变量进行测试
    os.environ['STORAGE_TYPE'] = 'hybrid'
    os.environ['CACHE_TTL'] = '300'
    os.environ['SYNC_INTERVAL'] = '60'
    
    # 运行测试
    asyncio.run(test_hybrid_storage())
