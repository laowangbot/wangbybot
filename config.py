#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云部署配置文件 - 使用环境变量
"""

import os

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 如果没有安装 python-dotenv，跳过
    pass

# 从环境变量获取配置
def get_env_var(var_name, default=None):
    """获取环境变量"""
    value = os.getenv(var_name, default)
    if value is None:
        raise ValueError(f"缺少必需的环境变量: {var_name}")
    return value

# Telegram API 配置
API_ID = get_env_var('API_ID')
API_HASH = get_env_var('API_HASH')
BOT_TOKEN = get_env_var('BOT_TOKEN')

# 机器人配置
BOT_NAME = "老湿姬2.0专版"
BOT_VERSION = "纯新引擎版本"

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "[%(asctime)s] - %(levelname)s - %(message)s"

# 其他配置
MAX_RETRIES = 3
RETRY_DELAY = 5

print(f"✅ 配置加载成功: {BOT_NAME} v{BOT_VERSION}")
print(f"✅ API_ID: {API_ID[:4]}****{API_ID[-4:] if len(API_ID) > 8 else '***'}")
print(f"✅ API_HASH: {API_HASH[:8]}****{API_HASH[-8:] if len(API_HASH) > 16 else '***'}")
print(f"✅ BOT_TOKEN: {BOT_TOKEN[:4]}****{BOT_TOKEN[-4:] if len(BOT_TOKEN) > 8 else '***'}")

