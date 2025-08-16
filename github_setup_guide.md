# GitHub仓库设置指南

## 🎯 目标
将csbybot项目上传到GitHub，为云部署做准备

## 📋 步骤详解

### 步骤1：创建GitHub仓库
1. 访问 [GitHub.com](https://github.com/)
2. 点击右上角 "+" 号，选择 "New repository"
3. 填写仓库信息：
   - Repository name: `csbybot` 或 `telegram-clone-bot`
   - Description: `Telegram消息搬运机器人`
   - 选择 Public（公开）或 Private（私有）
   - 不要勾选 "Add a README file"
   - 不要勾选 "Add .gitignore"
   - 不要勾选 "Choose a license"
4. 点击 "Create repository"

### 步骤2：初始化本地Git仓库
在csbybot文件夹中执行以下命令：

```bash
# 进入项目目录
cd csbybot

# 初始化Git仓库
git init

# 添加所有文件到暂存区
git add .

# 创建第一次提交
git commit -m "初始提交：Telegram搬运机器人"

# 添加远程仓库
git remote add origin https://github.com/你的用户名/csbybot.git

# 推送到GitHub
git push -u origin main
```

### 步骤3：创建.gitignore文件
创建 `.gitignore` 文件，排除不需要上传的文件：

```gitignore
# Python
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

# 会话文件
*.session
*.session-journal

# 配置文件（包含敏感信息）
config.py
user_*.json
*.session*

# 备份文件
备份/
*.backup*

# 系统文件
.DS_Store
Thumbs.db

# IDE文件
.vscode/
.idea/
*.swp
*.swo
```

### 步骤4：推送更新
每次修改代码后：

```bash
git add .
git commit -m "更新描述"
git push
```

## ⚠️ 重要提醒

### 1. 敏感信息保护
- **不要上传** `config.py` 文件（包含API密钥）
- **不要上传** `*.session` 文件（包含登录信息）
- **不要上传** `user_*.json` 文件（包含用户数据）

### 2. 环境变量设置
在云部署时，通过环境变量设置：
- `API_ID`
- `API_HASH`
- `BOT_TOKEN`

### 3. 文件结构
确保以下文件被上传：
- `csmain.py` - 主程序
- `requirements.txt` - 依赖包
- `Procfile` - 启动命令
- `runtime.txt` - Python版本
- `.gitignore` - Git忽略文件

## 🔧 快速设置脚本

运行以下命令快速设置：

```bash
# 创建.gitignore文件
echo "# Python缓存文件" > .gitignore
echo "__pycache__/" >> .gitignore
echo "*.py[cod]" >> .gitignore
echo "*.log" >> .gitignore
echo "*.session*" >> .gitignore
echo "config.py" >> .gitignore
echo "user_*.json" >> .gitignore

# 初始化Git
git init
git add .
git commit -m "初始提交：Telegram搬运机器人"
```

## 📊 上传状态检查

上传完成后，检查：
1. GitHub仓库是否包含所有必要文件
2. 敏感文件是否被正确排除
3. 代码是否可以正常访问

---

**设置时间**: 2025-08-17  
**状态**: 待设置  
**下一步**: 云部署
