import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logging.warning("Firebase模块未安装，将使用本地存储")

class FirebaseStorage:
    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.db = None
        self.project_id = None
        self.collection_name = f'bot_configs_{bot_id}'  # 每个机器人独立集合
        self.backup_collection = f'bot_configs_backup_{bot_id}'  # 独立备份集合
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """初始化Firebase连接"""
        if not FIREBASE_AVAILABLE:
            return
        
        try:
            # 检查是否已经初始化（支持多机器人共享Firebase实例）
            app_name = f'bot_{self.bot_id}'
            
            try:
                # 尝试获取已存在的应用实例
                app = firebase_admin.get_app(app_name)
                logging.info(f"使用已存在的Firebase应用实例: {app_name}")
            except ValueError:
                # 应用不存在，创建新的
                firebase_credentials = os.getenv('FIREBASE_CREDENTIALS')
                if firebase_credentials:
                    try:
                        service_account_info = json.loads(firebase_credentials)
                        cred = credentials.Certificate(service_account_info)
                        app = firebase_admin.initialize_app(cred, name=app_name)
                        logging.info(f"创建新的Firebase应用实例: {app_name}")
                    except json.JSONDecodeError as e:
                        logging.error(f"Firebase凭据JSON解析失败: {e}")
                        return
                else:
                    logging.warning(f"未找到FIREBASE_CREDENTIALS环境变量 (bot_id: {self.bot_id})")
                    return
            
            self.db = firestore.client(app)
            self.project_id = os.getenv('FIREBASE_PROJECT_ID', 'unknown')
            logging.info(f"[{self.bot_id}] Firebase已连接，项目ID: {self.project_id}")
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] Firebase初始化失败: {e}")
            self.db = None
    
    def is_available(self) -> bool:
        """检查Firebase是否可用"""
        return self.db is not None
    
    def save_configs(self, user_configs: Dict[str, Any]) -> bool:
        """保存用户配置到Firebase（机器人独立存储）"""
        if not self.is_available():
            return False
        
        try:
            doc_ref = self.db.collection(self.collection_name).document('current')
            doc_ref.set({
                'user_configs': user_configs,
                'last_updated': firestore.SERVER_TIMESTAMP,
                'bot_id': self.bot_id,
                'config_count': len(user_configs)
            })
            logging.info(f"[{self.bot_id}] 用户配置已保存到Firebase，共 {len(user_configs)} 个用户")
            
            # 自动创建备份
            self._create_auto_backup(user_configs)
            return True
        except Exception as e:
            logging.error(f"[{self.bot_id}] Firebase保存失败: {e}")
            return False
    
    def load_configs(self) -> Optional[Dict[str, Any]]:
        """从Firebase加载用户配置（机器人独立存储）"""
        if not self.is_available():
            return None
        
        try:
            doc_ref = self.db.collection(self.collection_name).document('current')
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                user_configs = data.get('user_configs', {})
                logging.info(f"[{self.bot_id}] 从Firebase加载用户配置成功，共 {len(user_configs)} 个用户")
                return user_configs
            else:
                logging.info(f"[{self.bot_id}] Firebase中没有找到配置数据")
                return {}
        except Exception as e:
            logging.error(f"[{self.bot_id}] Firebase加载失败: {e}")
            return None
    
    def _create_auto_backup(self, user_configs: Dict[str, Any]) -> bool:
        """自动创建配置备份"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_doc = f"backup_{timestamp}"
            
            doc_ref = self.db.collection(self.backup_collection).document(backup_doc)
            doc_ref.set({
                'user_configs': user_configs,
                'backup_time': firestore.SERVER_TIMESTAMP,
                'bot_id': self.bot_id,
                'config_count': len(user_configs)
            })
            logging.debug(f"[{self.bot_id}] 自动备份已创建: {backup_doc}")
            
            # 清理旧备份（保留最近10个）
            self._cleanup_old_backups()
            return True
        except Exception as e:
            logging.error(f"[{self.bot_id}] 自动备份失败: {e}")
            return False
    
    def _cleanup_old_backups(self):
        """清理旧备份，保留最近10个"""
        try:
            backups = self.db.collection(self.backup_collection).order_by('backup_time', direction=firestore.Query.DESCENDING).limit(15).get()
            
            if len(backups) > 10:
                # 删除超过10个的旧备份
                for backup in backups[10:]:
                    backup.reference.delete()
                    logging.debug(f"[{self.bot_id}] 已删除旧备份: {backup.id}")
        except Exception as e:
            logging.error(f"[{self.bot_id}] 清理旧备份失败: {e}")
    
    def get_backup_list(self) -> list:
        """获取备份列表"""
        if not self.is_available():
            return []
        
        try:
            backups = self.db.collection(self.backup_collection).order_by('backup_time', direction=firestore.Query.DESCENDING).limit(10).get()
            
            backup_list = []
            for backup in backups:
                data = backup.to_dict()
                backup_list.append({
                    'id': backup.id,
                    'backup_time': data.get('backup_time'),
                    'config_count': data.get('config_count', 0)
                })
            
            return backup_list
        except Exception as e:
            logging.error(f"[{self.bot_id}] 获取备份列表失败: {e}")
            return []

# 全局实例字典（支持多机器人）
_firebase_storage_instances = {}

def get_firebase_storage(bot_id: str) -> FirebaseStorage:
    """获取Firebase存储实例（支持多机器人）"""
    global _firebase_storage_instances
    if bot_id not in _firebase_storage_instances:
        _firebase_storage_instances[bot_id] = FirebaseStorage(bot_id)
    return _firebase_storage_instances[bot_id]

def save_configs_to_firebase(bot_id: str, user_configs: Dict[str, Any]) -> bool:
    """保存配置到Firebase"""
    storage = get_firebase_storage(bot_id)
    return storage.save_configs(user_configs)

def load_configs_from_firebase(bot_id: str) -> Optional[Dict[str, Any]]:
    """从Firebase加载配置"""
    storage = get_firebase_storage(bot_id)
    return storage.load_configs()