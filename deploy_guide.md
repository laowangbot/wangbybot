# Telegram机器人免费云部署指南

## 🎯 部署目标
将机器人部署到免费云服务，实现24小时运行

## 📋 部署前准备

### 1. 代码准备
确保以下文件存在：
- `csmain.py` - 主程序文件
- `config.py` - 配置文件
- `requirements.txt` - 依赖包列表
- `Procfile` - 启动命令（Heroku用）
- `runtime.txt` - Python版本

### 2. 环境变量准备
需要设置以下环境变量：
```bash
# Telegram API配置
API_ID=你的API_ID
API_HASH=你的API_HASH
BOT_TOKEN=你的机器人Token

# 其他配置
DATABASE_URL=数据库连接（如果需要）
```

## 🚀 部署方案

### 方案1：Railway部署（推荐）

#### 步骤1：注册Railway
1. 访问 [Railway.app](https://railway.app/)
2. 使用GitHub账号登录
3. 创建新项目

#### 步骤2：连接GitHub
1. 选择"Deploy from GitHub repo"
2. 选择包含机器人代码的仓库
3. 授权访问

#### 步骤3：配置环境
1. 在项目设置中添加环境变量
2. 设置启动命令：`python csmain.py`
3. 选择Python环境

#### 步骤4：部署
1. 点击"Deploy Now"
2. 等待部署完成
3. 查看运行状态

### 方案2：Render部署

#### 步骤1：注册Render
1. 访问 [Render.com](https://render.com/)
2. 使用GitHub账号登录
3. 创建新Web Service

#### 步骤2：配置服务
1. 连接GitHub仓库
2. 选择Python环境
3. 设置启动命令：`python csmain.py`
4. 配置环境变量

#### 步骤3：部署
1. 点击"Create Web Service"
2. 等待部署完成
3. 监控运行状态

### 方案3：Heroku部署

#### 步骤1：安装Heroku CLI
```bash
# Windows
# 下载安装包：https://devcenter.heroku.com/articles/heroku-cli

# 验证安装
heroku --version
```

#### 步骤2：登录Heroku
```bash
heroku login
```

#### 步骤3：创建应用
```bash
# 在项目目录下
heroku create 你的应用名
```

#### 步骤4：设置环境变量
```bash
heroku config:set API_ID=你的API_ID
heroku config:set API_HASH=你的API_HASH
heroku config:set BOT_TOKEN=你的机器人Token
```

#### 步骤5：部署
```bash
git add .
git commit -m "准备部署"
git push heroku main
```

## 🔧 部署后配置

### 1. 监控运行状态
- 查看日志输出
- 监控资源使用情况
- 检查机器人响应

### 2. 设置自动重启
- 配置健康检查
- 设置自动重启策略
- 监控服务状态

### 3. 备份配置
- 保存环境变量
- 备份重要配置文件
- 记录部署步骤

## ⚠️ 注意事项

### 1. 免费额度限制
- Railway: 每月500小时
- Render: 每月750小时
- Heroku: 每月550小时（需要信用卡）

### 2. 性能考虑
- 免费版资源有限
- 避免高CPU/内存使用
- 优化代码性能

### 3. 数据持久化
- 免费版可能不支持持久存储
- 考虑使用外部数据库
- 定期备份重要数据

## 🆘 常见问题

### Q1: 部署后机器人不响应
**解决方案：**
1. 检查环境变量是否正确设置
2. 查看日志输出
3. 确认API密钥有效

### Q2: 服务自动停止
**解决方案：**
1. 检查免费额度是否用完
2. 配置健康检查
3. 设置自动重启

### Q3: 依赖包安装失败
**解决方案：**
1. 检查requirements.txt格式
2. 确认Python版本兼容性
3. 查看构建日志

## 📊 部署状态检查

### 健康检查脚本
```python
import requests
import time

def check_bot_status():
    """检查机器人状态"""
    try:
        # 发送测试消息
        # 检查响应时间
        # 验证功能正常
        pass
    except Exception as e:
        print(f"机器人状态异常: {e}")

# 定期检查
while True:
    check_bot_status()
    time.sleep(300)  # 5分钟检查一次
```

## 🎉 部署完成

部署成功后，您的机器人将：
- ✅ 24小时运行
- ✅ 自动重启
- ✅ 稳定运行
- ✅ 免费使用

---

**部署时间**: 2025-08-17  
**部署状态**: 待部署  
**推荐方案**: Railway  
**预计成本**: 免费
