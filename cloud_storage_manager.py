#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云存储管理器 - 支持多种存储方式
确保用户配置文件在Render环境中持久化保存
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

# ==================== 存储配置 ====================
class StorageConfig:
    """存储配置类"""
    
    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.storage_type = os.getenv('STORAGE_TYPE', 'local')  # local, mongodb, supabase, gdrive
        
        # MongoDB配置
        self.mongo_uri = os.getenv('MONGO_URI')
        self.mongo_db = os.getenv('MONGO_DB', 'csbybot')
        
        # Supabase配置
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        # Google Drive配置
        self.gdrive_credentials = os.getenv('GDRIVE_CREDENTIALS')
        self.gdrive_folder_id = os.getenv('GDRIVE_FOLDER_ID')
        
        # 本地缓存配置
        self.local_cache_dir = f"cache_{bot_id}"
        self.backup_interval = int(os.getenv('BACKUP_INTERVAL', '300'))  # 5分钟
        
        # 创建本地缓存目录
        os.makedirs(self.local_cache_dir, exist_ok=True)

# ==================== 本地缓存管理器 ====================
class LocalCacheManager:
    """本地缓存管理器"""
    
    def __init__(self, bot_id: str, cache_dir: str):
        self.bot_id = bot_id
        self.cache_dir = cache_dir
        self.cache_files = {
            'user_configs': f"{cache_dir}/user_configs.json",
            'user_states': f"{cache_dir}/user_states.json",
            'user_history': f"{cache_dir}/user_history.json",
            'running_tasks': f"{cache_dir}/running_tasks.json"
        }
    
    def save_data(self, data_type: str, data: Dict[str, Any]) -> bool:
        """保存数据到本地缓存"""
        try:
            cache_file = self.cache_files.get(data_type)
            if cache_file:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logging.info(f"[{self.bot_id}] {data_type} 已保存到本地缓存")
                return True
        except Exception as e:
            logging.error(f"[{self.bot_id}] 保存 {data_type} 到本地缓存失败: {e}")
        return False
    
    def load_data(self, data_type: str) -> Dict[str, Any]:
        """从本地缓存加载数据"""
        try:
            cache_file = self.cache_files.get(data_type)
            if cache_file and os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logging.info(f"[{self.bot_id}] {data_type} 已从本地缓存加载")
                return data
        except Exception as e:
            logging.error(f"[{self.bot_id}] 从本地缓存加载 {data_type} 失败: {e}")
        return {}
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        info = {}
        for data_type, cache_file in self.cache_files.items():
            if os.path.exists(cache_file):
                size = os.path.getsize(cache_file)
                mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
                info[data_type] = {
                    'size': size,
                    'last_modified': mtime.strftime('%Y-%m-%d %H:%M:%S'),
                    'exists': True
                }
            else:
                info[data_type] = {'exists': False}
        return info

# ==================== MongoDB存储管理器 ====================
class MongoDBManager:
    """MongoDB存储管理器"""
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self.client = None
        self.db = None
        self._connect()
    
    def _connect(self):
        """连接到MongoDB"""
        try:
            if self.config.mongo_uri:
                from pymongo import MongoClient
                self.client = MongoClient(self.config.mongo_uri)
                self.db = self.client[self.config.mongo_db]
                logging.info(f"[{self.config.bot_id}] MongoDB连接成功")
            else:
                logging.warning(f"[{self.config.bot_id}] MongoDB URI未配置")
        except Exception as e:
            logging.error(f"[{self.config.bot_id}] MongoDB连接失败: {e}")
    
    def save_data(self, data_type: str, data: Dict[str, Any]) -> bool:
        """保存数据到MongoDB"""
        try:
            if not self.db:
                return False
            
            collection = self.db[f"{self.config.bot_id}_{data_type}"]
            # 使用bot_id作为文档ID，实现数据隔离
            collection.replace_one(
                {'_id': self.config.bot_id},
                {
                    '_id': self.config.bot_id,
                    'data': data,
                    'updated_at': datetime.utcnow(),
                    'bot_id': self.config.bot_id
                },
                upsert=True
            )
            logging.info(f"[{self.config.bot_id}] {data_type} 已保存到MongoDB")
            return True
        except Exception as e:
            logging.error(f"[{self.config.bot_id}] 保存 {data_type} 到MongoDB失败: {e}")
            return False
    
    def load_data(self, data_type: str) -> Dict[str, Any]:
        """从MongoDB加载数据"""
        try:
            if not self.db:
                return {}
            
            collection = self.db[f"{self.config.bot_id}_{data_type}"]
            doc = collection.find_one({'_id': self.config.bot_id})
            if doc:
                logging.info(f"[{self.config.bot_id}] {data_type} 已从MongoDB加载")
                return doc.get('data', {})
        except Exception as e:
            logging.error(f"[{self.config.bot_id}] 从MongoDB加载 {data_type} 失败: {e}")
        return {}
    
    def close(self):
        """关闭MongoDB连接"""
        if self.client:
            self.client.close()

# ==================== 云存储管理器主类 ====================
class CloudStorageManager:
    """云存储管理器主类"""
    
    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.config = StorageConfig(bot_id)
        self.local_cache = LocalCacheManager(bot_id, self.config.local_cache_dir)
        self.mongodb = MongoDBManager(self.config) if self.config.mongo_uri else None
        
        # 启动定期备份任务
        self._start_backup_task()
    
    def _start_backup_task(self):
        """启动定期备份任务"""
        async def backup_loop():
            while True:
                try:
                    await asyncio.sleep(self.config.backup_interval)
                    await self._backup_all_data()
                except Exception as e:
                    logging.error(f"[{self.bot_id}] 备份任务出错: {e}")
        
        # 在后台启动备份任务
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(backup_loop())
        else:
            loop.create_task(backup_loop())
    
    async def _backup_all_data(self):
        """备份所有数据"""
        logging.info(f"[{self.bot_id}] 开始定期备份...")
        
        # 这里可以从全局变量获取最新数据
        # 由于这个文件是独立的，我们通过参数传递数据
        
        logging.info(f"[{self.bot_id}] 定期备份完成")
    
    def save_user_configs(self, user_configs: Dict[str, Any]) -> bool:
        """保存用户配置"""
        # 先保存到本地缓存
        local_success = self.local_cache.save_data('user_configs', user_configs)
        
        # 再保存到云存储
        cloud_success = False
        if self.mongodb:
            cloud_success = self.mongodb.save_data('user_configs', user_configs)
        
        return local_success or cloud_success
    
    def load_user_configs(self) -> Dict[str, Any]:
        """加载用户配置"""
        # 优先从云存储加载
        if self.mongodb:
            data = self.mongodb.load_data('user_configs')
            if data:
                # 同步到本地缓存
                self.local_cache.save_data('user_configs', data)
                return data
        
        # 从本地缓存加载
        return self.local_cache.load_data('user_configs')
    
    def save_user_states(self, user_states: Dict[str, Any]) -> bool:
        """保存用户状态"""
        local_success = self.local_cache.save_data('user_states', user_states)
        cloud_success = False
        if self.mongodb:
            cloud_success = self.mongodb.save_data('user_states', user_states)
        return local_success or cloud_success
    
    def load_user_states(self) -> Dict[str, Any]:
        """加载用户状态"""
        if self.mongodb:
            data = self.mongodb.load_data('user_states')
            if data:
                self.local_cache.save_data('user_states', data)
                return data
        return self.local_cache.load_data('user_states')
    
    def save_user_history(self, user_history: Dict[str, Any]) -> bool:
        """保存用户历史"""
        local_success = self.local_cache.save_data('user_history', user_history)
        cloud_success = False
        if self.mongodb:
            cloud_success = self.mongodb.save_data('user_history', user_history)
        return local_success or cloud_success
    
    def load_user_history(self) -> Dict[str, Any]:
        """加载用户历史"""
        if self.mongodb:
            data = self.mongodb.load_data('user_history')
            if data:
                self.local_cache.save_data('user_history', data)
                return data
        return self.local_cache.load_data('user_history')
    
    def save_running_tasks(self, running_tasks: Dict[str, Any]) -> bool:
        """保存运行中的任务"""
        local_success = self.local_cache.save_data('running_tasks', running_tasks)
        cloud_success = False
        if self.mongodb:
            cloud_success = self.mongodb.save_data('running_tasks', running_tasks)
        return local_success or cloud_success
    
    def load_running_tasks(self) -> Dict[str, Any]:
        """加载运行中的任务"""
        if self.mongodb:
            data = self.mongodb.load_data('running_tasks')
            if data:
                self.local_cache.save_data('running_tasks', data)
                return data
        return self.local_cache.load_data('running_tasks')
    
    def get_storage_status(self) -> Dict[str, Any]:
        """获取存储状态"""
        status = {
            'bot_id': self.bot_id,
            'storage_type': self.config.storage_type,
            'local_cache': self.local_cache.get_cache_info(),
            'cloud_storage': {
                'mongodb': 'available' if self.mongodb else 'not_configured',
                'supabase': 'not_configured',  # 待实现
                'gdrive': 'not_configured'     # 待实现
            }
        }
        return status
    
    def close(self):
        """关闭所有连接"""
        if self.mongodb:
            self.mongodb.close()

# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 测试云存储管理器
    manager = CloudStorageManager('test_bot')
    
    # 测试数据
    test_configs = {
        'user123': {
            'channel_pairs': [
                {'source': '@test_source', 'target': '@test_target'}
            ],
            'filters': {'remove_links': True}
        }
    }
    
    # 保存测试数据
    success = manager.save_user_configs(test_configs)
    print(f"保存用户配置: {'成功' if success else '失败'}")
    
    # 加载测试数据
    loaded_configs = manager.load_user_configs()
    print(f"加载用户配置: {len(loaded_configs)} 个用户")
    
    # 获取存储状态
    status = manager.get_storage_status()
    print(f"存储状态: {json.dumps(status, indent=2, ensure_ascii=False)}")
    
    # 关闭连接
    manager.close()
