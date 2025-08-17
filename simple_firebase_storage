#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的Firebase存储模块 - 专门用于存储用户配置文件
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logging.warning("Firebase依赖未安装，将使用本地存储")

class SimpleFirebaseStorage:
    """简化的Firebase存储类"""
    
    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.db = None
        self.project_id = os.getenv('FIREBASE_PROJECT_ID', 'bybot-142d8')
        self.init_firebase()
    
    def init_firebase(self):
        """初始化Firebase连接"""
        if not FIREBASE_AVAILABLE:
            logging.warning(f"[{self.bot_id}] Firebase依赖未安装，使用本地存储")
            return
        
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
            
            # 初始化Firestore客户端
            self.db = firestore.client()
            logging.info(f"[{self.bot_id}] Firebase客户端初始化成功")
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] Firebase初始化失败: {e}")
            self.db = None
    
    def save_user_configs(self, user_configs: Dict[str, Any]) -> bool:
        """保存用户配置到Firebase"""
        if not self.db:
            logging.warning(f"[{self.bot_id}] Firebase未初始化，使用本地存储")
            return False
        
        try:
            # 保存到Firebase
            doc_ref = self.db.collection('bot_configs').document(self.bot_id)
            doc_ref.set({
                'bot_id': self.bot_id,
                'user_configs': user_configs,
                'updated_at': firestore.SERVER_TIMESTAMP,
                'config_count': len(user_configs)
            }, merge=True)
            
            logging.info(f"[{self.bot_id}] 用户配置已保存到Firebase，共 {len(user_configs)} 个用户")
            return True
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 保存用户配置到Firebase失败: {e}")
            return False
    
    def load_user_configs(self) -> Dict[str, Any]:
        """从Firebase加载用户配置"""
        if not self.db:
            logging.warning(f"[{self.bot_id}] Firebase未初始化，使用本地存储")
            return {}
        
        try:
            doc_ref = self.db.collection('bot_configs').document(self.bot_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                user_configs = data.get('user_configs', {})
                config_count = data.get('config_count', 0)
                logging.info(f"[{self.bot_id}] 从Firebase加载用户配置成功，共 {config_count} 个用户")
                return user_configs
            else:
                logging.info(f"[{self.bot_id}] Firebase中未找到用户配置")
                return {}
                
        except Exception as e:
            logging.error(f"[{self.bot_id}] 从Firebase加载用户配置失败: {e}")
            return {}
    
    def save_single_user_config(self, user_id: int, config: Dict[str, Any]) -> bool:
        """保存单个用户配置"""
        if not self.db:
            return False
        
        try:
            # 先加载现有配置
            existing_configs = self.load_user_configs()
            
            # 更新指定用户的配置
            existing_configs[str(user_id)] = config
            
            # 保存回Firebase
            return self.save_user_configs(existing_configs)
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 保存单个用户配置失败: {e}")
            return False
    
    def get_single_user_config(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取单个用户配置"""
        if not self.db:
            return None
        
        try:
            all_configs = self.load_user_configs()
            return all_configs.get(str(user_id))
        except Exception as e:
            logging.error(f"[{self.bot_id}] 获取单个用户配置失败: {e}")
            return None
    
    def is_available(self) -> bool:
        """检查Firebase是否可用"""
        return self.db is not None
    
    def get_status(self) -> Dict[str, Any]:
        """获取存储状态"""
        return {
            'bot_id': self.bot_id,
            'firebase_available': self.is_available(),
            'project_id': self.project_id,
            'last_check': datetime.now().isoformat()
        }

# 全局存储实例
_firebase_storage = None

def get_firebase_storage(bot_id: str) -> SimpleFirebaseStorage:
    """获取Firebase存储实例"""
    global _firebase_storage
    if _firebase_storage is None:
        _firebase_storage = SimpleFirebaseStorage(bot_id)
    return _firebase_storage

def save_configs_to_firebase(bot_id: str, user_configs: Dict[str, Any]) -> bool:
    """保存配置到Firebase的便捷函数"""
    storage = get_firebase_storage(bot_id)
    return storage.save_user_configs(user_configs)

def load_configs_from_firebase(bot_id: str) -> Dict[str, Any]:
    """从Firebase加载配置的便捷函数"""
    storage = get_firebase_storage(bot_id)
    return storage.load_user_configs()

def save_single_user_to_firebase(bot_id: str, user_id: int, config: Dict[str, Any]) -> bool:
    """保存单个用户配置到Firebase的便捷函数"""
    storage = get_firebase_storage(bot_id)
    return storage.save_single_user_config(user_id, config)

def load_single_user_from_firebase(bot_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    """从Firebase加载单个用户配置的便捷函数"""
    storage = get_firebase_storage(bot_id)
    return storage.get_single_user_config(user_id)
