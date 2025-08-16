#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub上传脚本 - 帮助用户快速上传csbybot项目到GitHub
"""

import os
import subprocess
import sys

class GitHubUploader:
    def __init__(self):
        self.project_dir = os.getcwd()
        self.git_initialized = False
        
    def check_git_installed(self):
        """检查Git是否已安装"""
        try:
            result = subprocess.run(['git', '--version'], 
                                  capture_output=True, text=True, check=True)
            print(f"✅ Git已安装: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Git未安装，请先安装Git")
            print("下载地址: https://git-scm.com/downloads")
            return False
    
    def check_git_status(self):
        """检查Git仓库状态"""
        try:
            # 检查是否已初始化
            if os.path.exists('.git'):
                print("✅ Git仓库已存在")
                self.git_initialized = True
                return True
            else:
                print("ℹ️ 未检测到Git仓库，需要初始化")
                return False
        except Exception as e:
            print(f"❌ 检查Git状态失败: {e}")
            return False
    
    def create_gitignore(self):
        """创建.gitignore文件"""
        print("📁 创建.gitignore文件...")
        
        gitignore_content = """# Python缓存文件
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/

# 日志文件
*.log
*.log.*
*.backup*

# 会话文件（包含敏感登录信息）
*.session
*.session-journal

# 配置文件（包含API密钥等敏感信息）
config.py
user_*.json
user_configs.json
user_history.json
user_login.json
user_states.json
running_tasks.json
message_fingerprints.json
performance_stats.json
processed_ids_*.json

# 备份文件夹
备份/

# 系统文件
.DS_Store
Thumbs.db
desktop.ini

# IDE文件
.vscode/
.idea/
*.swp
*.swp
*~

# 临时文件
*.tmp
*.temp
*.bak

# 环境变量文件
.env
.env.local
.env.production

# 测试文件
test_*.py
*_test.py

# 修复脚本（部署后可以删除）
fix_*.py
*_fix.py
*_fixed.py
enhanced_*.py
simple_*.py
quick_*.py
"""
        
        with open('.gitignore', 'w', encoding='utf-8') as f:
            f.write(gitignore_content)
        
        print("✅ .gitignore文件已创建")
    
    def init_git_repo(self):
        """初始化Git仓库"""
        print("🔧 初始化Git仓库...")
        
        try:
            # 初始化Git仓库
            subprocess.run(['git', 'init'], check=True)
            print("✅ Git仓库初始化成功")
            
            # 添加所有文件
            subprocess.run(['git', 'add', '.'], check=True)
            print("✅ 文件已添加到暂存区")
            
            # 创建第一次提交
            subprocess.run(['git', 'commit', '-m', '初始提交：Telegram搬运机器人'], check=True)
            print("✅ 初始提交创建成功")
            
            self.git_initialized = True
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Git操作失败: {e}")
            return False
    
    def add_remote_repo(self):
        """添加远程仓库"""
        print("🔗 添加远程仓库...")
        
        print("请输入您的GitHub仓库URL:")
        print("格式: https://github.com/用户名/仓库名.git")
        print("例如: https://github.com/yourname/csbybot.git")
        
        repo_url = input("GitHub仓库URL: ").strip()
        
        if not repo_url:
            print("❌ 未输入仓库URL")
            return False
        
        try:
            # 添加远程仓库
            subprocess.run(['git', 'remote', 'add', 'origin', repo_url], check=True)
            print("✅ 远程仓库添加成功")
            
            # 推送到GitHub
            print("🚀 推送到GitHub...")
            subprocess.run(['git', 'push', '-u', 'origin', 'main'], check=True)
            print("✅ 代码推送成功！")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 推送失败: {e}")
            print("请检查：")
            print("1. 仓库URL是否正确")
            print("2. 是否已创建GitHub仓库")
            print("3. 是否有推送权限")
            return False
    
    def show_upload_status(self):
        """显示上传状态"""
        print("\n📊 上传状态检查")
        print("=" * 30)
        
        if self.git_initialized:
            print("✅ Git仓库已初始化")
            print("✅ .gitignore文件已创建")
            print("✅ 敏感文件已被排除")
            
            # 检查远程仓库
            try:
                result = subprocess.run(['git', 'remote', '-v'], 
                                      capture_output=True, text=True, check=True)
                if 'origin' in result.stdout:
                    print("✅ 远程仓库已配置")
                else:
                    print("⚠️ 远程仓库未配置")
            except:
                print("⚠️ 无法检查远程仓库状态")
        else:
            print("❌ Git仓库未初始化")
        
        print("\n📋 下一步操作：")
        print("1. 在GitHub上创建仓库")
        print("2. 运行 'python github_upload.py' 完成上传")
        print("3. 使用云部署工具部署机器人")
    
    def run(self):
        """运行上传工具"""
        print("🚀 GitHub上传工具")
        print("=" * 50)
        
        # 检查Git是否安装
        if not self.check_git_installed():
            return
        
        # 检查Git状态
        self.check_git_status()
        
        # 创建.gitignore文件
        self.create_gitignore()
        
        # 如果Git未初始化，则初始化
        if not self.git_initialized:
            if not self.init_git_repo():
                print("❌ Git仓库初始化失败")
                return
        
        # 询问是否添加远程仓库
        print("\n是否现在添加远程仓库并推送代码？")
        choice = input("选择 (y/n): ").strip().lower()
        
        if choice in ['y', 'yes', '是']:
            if self.add_remote_repo():
                print("\n🎉 恭喜！代码已成功上传到GitHub")
                print("现在可以使用云部署工具部署机器人了")
            else:
                print("\n⚠️ 远程仓库配置失败，请稍后手动配置")
        else:
            print("\nℹ️ 已跳过远程仓库配置")
        
        # 显示状态
        self.show_upload_status()

def main():
    """主函数"""
    uploader = GitHubUploader()
    uploader.run()

if __name__ == "__main__":
    main()
