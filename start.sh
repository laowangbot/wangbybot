#!/bin/bash
# Render启动脚本

echo "🚀 启动Telegram机器人..."

# 确保持久化目录存在
mkdir -p /opt/render/project/src/data
mkdir -p /opt/render/project/src/backup

# 设置权限
chmod 755 /opt/render/project/src/data
chmod 755 /opt/render/project/src/backup

# 启动机器人
python csmain.py
