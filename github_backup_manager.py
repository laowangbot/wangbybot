import os
import json
import time
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional

class GitHubBackupManager:
    """GitHub配置备份管理器"""
    
    def __init__(self, repo_owner: str, repo_name: str, token: str, branch: str = "main"):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.token = token
        self.branch = branch
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
    def backup_config(self, config_data: Dict[str, Any], filename: str) -> bool:
        """备份配置到GitHub"""
        try:
            # 获取文件SHA（如果存在）
            file_sha = self._get_file_sha(filename)
            
            # 准备提交数据
            content = json.dumps(config_data, ensure_ascii=False, indent=2)
            commit_message = f"🤖 机器人配置自动备份 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # 创建或更新文件
            if file_sha:
                # 更新现有文件
                response = requests.put(
                    f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/{filename}",
                    headers=self.headers,
                    json={
                        "message": commit_message,
                        "content": content.encode('utf-8').decode('latin-1'),
                        "sha": file_sha,
                        "branch": self.branch
                    }
                )
            else:
                # 创建新文件
                response = requests.put(
                    f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/{filename}",
                    headers=self.headers,
                    json={
                        "message": commit_message,
                        "content": content.encode('utf-8').decode('latin-1'),
                        "branch": self.branch
                    }
                )
            
            if response.status_code in [200, 201]:
                logging.info(f"✅ 配置已成功备份到GitHub: {filename}")
                return True
            else:
                logging.error(f"❌ GitHub备份失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logging.error(f"❌ GitHub备份异常: {e}")
            return False
    
    def restore_config(self, filename: str) -> Optional[Dict[str, Any]]:
        """从GitHub恢复配置"""
        try:
            response = requests.get(
                f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/{filename}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                content = response.json()["content"]
                # GitHub返回的是base64编码的内容
                import base64
                decoded_content = base64.b64decode(content).decode('utf-8')
                config_data = json.loads(decoded_content)
                logging.info(f"✅ 配置已从GitHub恢复: {filename}")
                return config_data
            else:
                logging.warning(f"⚠️ 配置文件不存在: {filename}")
                return None
                
        except Exception as e:
            logging.error(f"❌ GitHub恢复异常: {e}")
            return None
    
    def _get_file_sha(self, filename: str) -> Optional[str]:
        """获取文件的SHA值"""
        try:
            response = requests.get(
                f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/{filename}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()["sha"]
            return None
            
        except Exception:
            return None
    
    def list_backups(self) -> list:
        """列出所有备份文件"""
        try:
            response = requests.get(
                f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/backups",
                headers=self.headers
            )
            
            if response.status_code == 200:
                files = response.json()
                return [f["name"] for f in files if f["type"] == "file"]
            return []
            
        except Exception as e:
            logging.error(f"❌ 获取备份列表失败: {e}")
            return []

# 使用示例
if __name__ == "__main__":
    # 从环境变量获取GitHub配置
    repo_owner = os.getenv("GITHUB_REPO_OWNER", "laowangbot")
    repo_name = os.getenv("GITHUB_REPO_NAME", "wangbybot")
    token = os.getenv("GITHUB_TOKEN", "")
    
    if not token:
        print("❌ 请设置GITHUB_TOKEN环境变量")
        exit(1)
    
    backup_manager = GitHubBackupManager(repo_owner, repo_name, token)
    
    # 测试备份
    test_config = {
        "test": "data",
        "timestamp": datetime.now().isoformat()
    }
    
    success = backup_manager.backup_config(test_config, "test_config.json")
    if success:
        print("✅ 测试备份成功")
        
        # 测试恢复
        restored = backup_manager.restore_config("test_config.json")
        if restored:
            print("✅ 测试恢复成功")
            print(f"恢复的数据: {restored}")
    else:
        print("❌ 测试备份失败")
