import os
import json
import time
import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

try:
    from github_backup_manager import GitHubBackupManager
    GITHUB_BACKUP_AVAILABLE = True
except ImportError:
    GITHUB_BACKUP_AVAILABLE = False
    logging.warning("GitHub备份模块未找到，将使用本地备份")

class MemoryStorageManager:
    """内存存储管理器 - 解决Render持久化问题"""
    
    def __init__(self, bot_id: str, backup_interval: int = 300):
        self.bot_id = bot_id
        self.backup_interval = backup_interval  # 5分钟备份一次
        
        # 内存存储
        self.user_configs = {}
        self.user_states = {}
        self.user_history = {}
        self.user_login = {}
        self.running_tasks = {}
        
        # 备份状态
        self.last_backup = {}
        self.backup_lock = threading.Lock()
        
        # 初始化GitHub备份
        self.github_backup = None
        if GITHUB_BACKUP_AVAILABLE:
            self._init_github_backup()
        
        # 启动自动备份线程
        self._start_backup_thread()
        
        logging.info(f"[{bot_id}] 内存存储管理器已初始化")
    
    def _init_github_backup(self):
        """初始化GitHub备份"""
        try:
            repo_owner = os.getenv("GITHUB_REPO_OWNER", "laowangbot")
            repo_name = os.getenv("GITHUB_REPO_NAME", "wangbybot")
            token = os.getenv("GITHUB_TOKEN", "")
            
            if token:
                self.github_backup = GitHubBackupManager(repo_owner, repo_name, token)
                logging.info(f"[{self.bot_id}] GitHub备份已启用")
            else:
                logging.warning(f"[{self.bot_id}] GITHUB_TOKEN未设置，GitHub备份已禁用")
                
        except Exception as e:
            logging.error(f"[{self.bot_id}] GitHub备份初始化失败: {e}")
    
    def _start_backup_thread(self):
        """启动自动备份线程"""
        def backup_worker():
            while True:
                try:
                    time.sleep(self.backup_interval)
                    self._auto_backup_all()
                except Exception as e:
                    logging.error(f"[{self.bot_id}] 自动备份异常: {e}")
                    time.sleep(60)  # 出错后等待1分钟再试
        
        backup_thread = threading.Thread(target=backup_worker, daemon=True)
        backup_thread.start()
        logging.info(f"[{self.bot_id}] 自动备份线程已启动，间隔: {self.backup_interval}秒")
    
    def _auto_backup_all(self):
        """自动备份所有配置"""
        try:
            current_time = time.time()
            
            # 检查是否需要备份
            for config_type in ['user_configs', 'user_states', 'user_history', 'user_login', 'running_tasks']:
                if self._should_backup(config_type, current_time):
                    self._backup_config(config_type)
                    
        except Exception as e:
            logging.error(f"[{self.bot_id}] 自动备份失败: {e}")
    
    def _should_backup(self, config_type: str, current_time: float) -> bool:
        """检查是否需要备份"""
        last_backup_time = self.last_backup.get(config_type, 0)
        return (current_time - last_backup_time) >= self.backup_interval
    
    def _backup_config(self, config_type: str):
        """备份指定类型的配置"""
        try:
            with self.backup_lock:
                config_data = getattr(self, config_type, {})
                if not config_data:
                    return
                
                filename = f"backups/{self.bot_id}_{config_type}.json"
                
                # 尝试GitHub备份
                if self.github_backup:
                    success = self.github_backup.backup_config(config_data, filename)
                    if success:
                        self.last_backup[config_type] = time.time()
                        logging.info(f"[{self.bot_id}] {config_type} 已备份到GitHub")
                        return
                
                # 本地备份作为备选
                self._local_backup(config_type, config_data)
                self.last_backup[config_type] = time.time()
                
        except Exception as e:
            logging.error(f"[{self.bot_id}] 备份 {config_type} 失败: {e}")
    
    def _local_backup(self, config_type: str, config_data: Dict):
        """本地备份"""
        try:
            backup_dir = f"backups/{self.bot_id}"
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_file = f"{backup_dir}/{config_type}.json"
            with open(backup_file, "w", encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            logging.info(f"[{self.bot_id}] {config_type} 已备份到本地: {backup_file}")
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 本地备份失败: {e}")
    
    def restore_from_backup(self, config_type: str) -> bool:
        """从备份恢复配置"""
        try:
            if self.github_backup:
                filename = f"backups/{self.bot_id}_{config_type}.json"
                restored_data = self.github_backup.restore_config(filename)
                
                if restored_data:
                    setattr(self, config_type, restored_data)
                    logging.info(f"[{self.bot_id}] {config_type} 已从GitHub恢复")
                    return True
            
            # 尝试本地恢复
            return self._local_restore(config_type)
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 恢复 {config_type} 失败: {e}")
            return False
    
    def _local_restore(self, config_type: str) -> bool:
        """从本地备份恢复"""
        try:
            backup_file = f"backups/{self.bot_id}/{config_type}.json"
            if os.path.exists(backup_file):
                with open(backup_file, "r", encoding='utf-8') as f:
                    restored_data = json.load(f)
                
                setattr(self, config_type, restored_data)
                logging.info(f"[{self.bot_id}] {config_type} 已从本地恢复: {backup_file}")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 本地恢复失败: {e}")
            return False
    
    def get_config(self, config_type: str) -> Dict:
        """获取配置"""
        return getattr(self, config_type, {})
    
    def set_config(self, config_type: str, data: Dict):
        """设置配置"""
        setattr(self, config_type, data)
        # 立即备份
        self._backup_config(config_type)
    
    def update_config(self, config_type: str, key: str, value: Any):
        """更新配置中的特定键值"""
        config = getattr(self, config_type, {})
        config[key] = value
        setattr(self, config_type, config)
        # 立即备份
        self._backup_config(config_type)
    
    def get_backup_status(self) -> Dict:
        """获取备份状态"""
        status = {
            "github_backup_enabled": self.github_backup is not None,
            "last_backup": {},
            "backup_interval": self.backup_interval
        }
        
        for config_type in ['user_configs', 'user_states', 'user_history', 'user_login', 'running_tasks']:
            last_time = self.last_backup.get(config_type, 0)
            if last_time > 0:
                status["last_backup"][config_type] = datetime.fromtimestamp(last_time).strftime('%Y-%m-%d %H:%M:%S')
            else:
                status["last_backup"][config_type] = "从未备份"
        
        return status
    
    def force_backup_all(self):
        """强制备份所有配置"""
        try:
            logging.info(f"[{self.bot_id}] 开始强制备份所有配置...")
            
            for config_type in ['user_configs', 'user_states', 'user_history', 'user_login', 'running_tasks']:
                self._backup_config(config_type)
            
            logging.info(f"[{self.bot_id}] 强制备份完成")
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 强制备份失败: {e}")
    
    def restore_all_from_backup(self):
        """从备份恢复所有配置"""
        try:
            logging.info(f"[{self.bot_id}] 开始从备份恢复所有配置...")
            
            restored_count = 0
            for config_type in ['user_configs', 'user_states', 'user_history', 'user_login', 'running_tasks']:
                if self.restore_from_backup(config_type):
                    restored_count += 1
            
            logging.info(f"[{self.bot_id}] 恢复完成，成功恢复 {restored_count}/5 个配置")
            return restored_count
            
        except Exception as e:
            logging.error(f"[{self.bot_id}] 恢复失败: {e}")
            return 0

# 使用示例
if __name__ == "__main__":
    # 测试内存存储管理器
    storage = MemoryStorageManager("test_bot", backup_interval=60)
    
    # 设置测试数据
    storage.set_config("user_configs", {"test_user": {"setting": "value"}})
    
    # 等待备份
    time.sleep(70)
    
    # 检查状态
    status = storage.get_backup_status()
    print("备份状态:", json.dumps(status, indent=2, ensure_ascii=False))
