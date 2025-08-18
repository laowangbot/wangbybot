import json
import logging
import os
from typing import Dict, Any, Optional

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
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """初始化Firebase连接"""
        if not FIREBASE_AVAILABLE:
            return
        
        try:
            # 检查是否已经初始化
            if not firebase_admin._apps:
                # 方式1: 使用环境变量中的服务账户密钥
                if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
                    cred = credentials.ApplicationDefault()
                    firebase_admin.initialize_app(cred)
                # 方式2: 使用服务账户密钥文件
                elif os.path.exists('serviceAccountKey.json'):
                    cred = credentials.Certificate('serviceAccountKey.json')
                    firebase_admin.initialize_app(cred)
                # 方式3: 使用环境变量中的JSON字符串
                elif os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY'):
                    service_account_info = json.loads(os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY'))
                    cred = credentials.Certificate(service_account_info)
                    firebase_admin.initialize_app(cred)
                else:
                    logging.warning("未找到Firebase服务账户密钥，将使用本地存储")
                    return
            
            self.db = firestore.client()
            # 获取项目ID
            app = firebase_admin.get_app()
            self.project_id = app.project_id
            logging.info(f"Firebase已连接，项目ID: {self.project_id}")
            
        except Exception as e:
            logging.error(f"Firebase初始化失败: {e}")
            self.db = None
    
    def is_available(self) -> bool:
        """检查Firebase是否可用"""
        return self.db is not None
    
    def save_configs(self, user_configs: Dict[str, Any]) -> bool:
        """保存用户配置到Firebase"""
        if not self.is_available():
            return False
        
        try:
            doc_ref = self.db.collection('bot_configs').document(self.bot_id)
            doc_ref.set({
                'user_configs': user_configs,
                'last_updated': firestore.SERVER_TIMESTAMP
            })
            logging.info(f"用户配置已保存到Firebase，共 {len(user_configs)} 个用户")
            return True
        except Exception as e:
            logging.error(f"Firebase保存失败: {e}")
            return False
    
    def load_configs(self) -> Optional[Dict[str, Any]]:
        """从Firebase加载用户配置"""
        if not self.is_available():
            return None
        
        try:
            doc_ref = self.db.collection('bot_configs').document(self.bot_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                user_configs = data.get('user_configs', {})
                logging.info(f"从Firebase加载用户配置成功，共 {len(user_configs)} 个用户")
                return user_configs
            else:
                logging.info("Firebase中没有找到配置数据")
                return {}
        except Exception as e:
            logging.error(f"Firebase加载失败: {e}")
            return None

# 全局实例
_firebase_storage = None

def get_firebase_storage(bot_id: str) -> FirebaseStorage:
    """获取Firebase存储实例"""
    global _firebase_storage
    if _firebase_storage is None:
        _firebase_storage = FirebaseStorage(bot_id)
    return _firebase_storage

def save_configs_to_firebase(bot_id: str, user_configs: Dict[str, Any]) -> bool:
    """保存配置到Firebase"""
    storage = get_firebase_storage(bot_id)
    return storage.save_configs(user_configs)

def load_configs_from_firebase(bot_id: str) -> Optional[Dict[str, Any]]:
    """从Firebase加载配置"""
    storage = get_firebase_storage(bot_id)
    return storage.load_configs()