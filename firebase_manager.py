#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firebase管理器 - 用于管理用户配置和任务数据的云存储
支持多机器人数据同步和持久化存储
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import AsyncClient

class FirebaseManager:
    """Firebase管理器"""
    
    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.db = None
        self.async_db = None
        self.project_id = os.getenv('FIREBASE_PROJECT_ID', 'csbybot-cloud-storage')
        self.init_firebase()
    
    def init_firebase(self):
        """初始化Firebase连接"""
        try:
            # 检查是否已经初始化
            if not firebase_admin._apps:
                # 从环境变量获取服务账号密钥
                firebase_creds = os.getenv('FIREBASE_CREDENTIALS')
                if firebase_creds:
                    cred_dict = json.loads(firebase_creds)
                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred, {
                        'projectId': self.project_id
                    })
                    logging.info(f"[{self.bot_id}] Firebase初始化成功")
                else:
                    logging.warning(f"[{self.bot_id}] 未找到FIREBASE_CREDENTIALS环境变量")
                    return
            
            # 初始化同步和异步客户端
            self.db = firestore.client()
            self.async_db = AsyncClient(project=self.project_id)
            logging.info(f"[{self.bot_id}] Firebase客户端初始化成功")
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] Firebase初始化失败: {e}")
            self.db = None
            self.async_db = None
    
    async def save_user_config(self, user_id: int, config: Dict[str, Any]) -> bool:
        """保存用户配置到Firebase"""
        if not self.db:
            logging.error(f"[{self.bot_id}] Firebase未初始化")
            return False
        
        try:
            doc_ref = self.db.collection('users').document(str(user_id))
            doc_ref.set({
                'bot_id': self.bot_id,
                'user_id': user_id,
                'config': config,
                'updated_at': firestore.SERVER_TIMESTAMP,
                'last_active': firestore.SERVER_TIMESTAMP
            }, merge=True)
            
            logging.info(f"[{self.bot_id}] 用户 {user_id} 配置保存成功")
            return True
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 保存用户配置失败: {e}")
            return False
    
    async def get_user_config(self, user_id: int) -> Optional[Dict[str, Any]]:
        """从Firebase获取用户配置"""
        if not self.db:
            logging.error(f"[{self.bot_id}] Firebase未初始化")
            return None
        
        try:
            doc_ref = self.db.collection('users').document(str(user_id))
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                logging.info(f"[{self.bot_id}] 用户 {user_id} 配置获取成功")
                return data.get('config', {})
            else:
                logging.info(f"[{self.bot_id}] 用户 {user_id} 配置不存在")
                return None
                
        except Exception as e:
            logging.error(f"[{self.bot_id}] 获取用户配置失败: {e}")
            return None
    
    async def save_task_status(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """保存任务状态到Firebase"""
        if not self.db:
            logging.error(f"[{self.bot_id}] Firebase未初始化")
            return False
        
        try:
            doc_ref = self.db.collection('tasks').document(task_id)
            doc_ref.set({
                'bot_id': self.bot_id,
                'task_id': task_id,
                'task_data': task_data,
                'updated_at': firestore.SERVER_TIMESTAMP,
                'status': 'running'
            }, merge=True)
            
            logging.info(f"[{self.bot_id}] 任务 {task_id} 状态保存成功")
            return True
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 保存任务状态失败: {e}")
            return False
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        if not self.db:
            logging.error(f"[{self.bot_id}] Firebase未初始化")
            return None
        
        try:
            doc_ref = self.db.collection('tasks').document(task_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                return data.get('task_data', {})
            return None
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 获取任务状态失败: {e}")
            return None
    
    async def update_bot_status(self, status_data: Dict[str, Any]) -> bool:
        """更新机器人状态"""
        if not self.db:
            logging.error(f"[{self.bot_id}] Firebase未初始化")
            return False
        
        try:
            doc_ref = self.db.collection('bots').document(self.bot_id)
            doc_ref.set({
                'bot_id': self.bot_id,
                'status': status_data,
                'updated_at': firestore.SERVER_TIMESTAMP,
                'is_online': True
            }, merge=True)
            
            logging.info(f"[{self.bot_id}] 机器人状态更新成功")
            return True
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 更新机器人状态失败: {e}")
            return False
    
    async def get_all_users(self) -> List[Dict[str, Any]]:
        """获取所有用户配置"""
        if not self.db:
            logging.error(f"[{self.bot_id}] Firebase未初始化")
            return []
        
        try:
            users_ref = self.db.collection('users')
            docs = users_ref.stream()
            
            users = []
            for doc in docs:
                user_data = doc.to_dict()
                users.append({
                    'user_id': user_data.get('user_id'),
                    'bot_id': user_data.get('bot_id'),
                    'config': user_data.get('config', {}),
                    'last_active': user_data.get('last_active')
                })
            
            logging.info(f"[{self.bot_id}] 获取到 {len(users)} 个用户")
            return users
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 获取所有用户失败: {e}")
            return []
    
    async def delete_user_config(self, user_id: int) -> bool:
        """删除用户配置"""
        if not self.db:
            logging.error(f"[{self.bot_id}] Firebase未初始化")
            return False
        
        try:
            doc_ref = self.db.collection('users').document(str(user_id))
            doc_ref.delete()
            
            logging.info(f"[{self.bot_id}] 用户 {user_id} 配置删除成功")
            return True
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 删除用户配置失败: {e}")
            return False
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取Firebase健康状态"""
        return {
            'is_connected': self.db is not None,
            'project_id': self.project_id,
            'bot_id': self.bot_id,
            'last_check': datetime.now().isoformat()
        }
    
    async def close(self):
        """关闭Firebase连接"""
        try:
            if self.async_db:
                await self.async_db.close()
            logging.info(f"[{self.bot_id}] Firebase连接已关闭")
        except Exception as e:
            logging.error(f"[{self.bot_id}] 关闭Firebase连接失败: {e}")

# 测试函数
async def test_firebase():
    """测试Firebase连接"""
    manager = FirebaseManager('test_bot')
    
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
    
    # 测试更新机器人状态
    status = await manager.update_bot_status({
        'version': '2.0',
        'uptime': '1小时',
        'memory_usage': '50MB'
    })
    print(f"更新机器人状态: {'成功' if status else '失败'}")
    
    await manager.close()

if __name__ == "__main__":
    # 设置环境变量进行测试
    os.environ['FIREBASE_CREDENTIALS'] = '{"type":"service_account","project_id":"test"}'
    os.environ['FIREBASE_PROJECT_ID'] = 'test-project'
    
    # 运行测试
    asyncio.run(test_firebase())
