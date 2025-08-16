#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多机器人支持版本 - 老湿姬2.0专版
"""

import os
import time
import asyncio
import re
import logging
import uuid
import json
import random
import signal
import sys
from datetime import datetime
from collections import defaultdict
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from pyrogram.enums import ChatType
from pyrogram.errors.exceptions import BadRequest, FloodWait
from urllib.parse import urlparse

# ==================== 多机器人配置 ====================
def get_bot_config():
    """获取机器人配置"""
    # 从环境变量获取机器人标识
    bot_id = os.environ.get('BOT_ID', 'bot1')
    bot_name = os.environ.get('BOT_NAME', f'老湿姬{bot_id}')
    bot_version = os.environ.get('BOT_VERSION', '多机器人版本')
    
    # 从环境变量获取Telegram配置
    api_id = os.environ.get('API_ID')
    api_hash = os.environ.get('API_HASH')
    bot_token = os.environ.get('BOT_TOKEN')
    
    if not all([api_id, api_hash, bot_token]):
        raise ValueError("缺少必需的环境变量: API_ID, API_HASH, BOT_TOKEN")
    
    return {
        'bot_id': bot_id,
        'bot_name': bot_name,
        'bot_version': bot_version,
        'api_id': api_id,
        'api_hash': api_hash,
        'bot_token': bot_token
    }

# 获取配置
config = get_bot_config()
print(f"🤖 启动机器人: {config['bot_name']} - {config['bot_version']}")
print(f"🔑 机器人ID: {config['bot_id']}")

# ==================== 端口绑定功能 ====================
def start_port_server():
    """启动端口服务器，用于Render Web Service"""
    try:
        import socket
        import http.server
        import socketserver
        
        class SimpleHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                response = """
                <html>
                <head><title>多机器人服务</title></head>
                <body>
                <h1>🤖 {bot_name} - {bot_version}</h1>
                <p>机器人ID: {bot_id}</p>
                <p>状态：正常运行中</p>
                <p>时间：{current_time}</p>
                </body>
                </html>
                """.format(
                    bot_name=config['bot_name'],
                    bot_version=config['bot_version'],
                    bot_id=config['bot_id'],
                    current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                self.wfile.write(response.encode())
            
            def log_message(self, format, *args):
                # 禁用HTTP访问日志
                pass
        
        # 绑定到Render分配的端口
        port = int(os.environ.get('PORT', 8080))
        
        with socketserver.TCPServer(("", port), SimpleHandler) as httpd:
            print(f"🌐 端口服务器启动成功，监听端口 {port}")
            httpd.serve_forever()
    
    except Exception as e:
        print(f"⚠️ 端口服务器启动失败: {e}")

# 在后台启动端口服务器
import threading
port_thread = threading.Thread(target=start_port_server, daemon=True)
port_thread.start()

# ==================== 心跳机制 ====================
def start_heartbeat():
    """启动心跳机制，防止Render 15分钟自动停止"""
    import requests
    import time
    
    while True:
        try:
            # 获取当前服务URL
            service_url = os.environ.get('RENDER_EXTERNAL_URL')
            if service_url:
                # 向自己的服务发送请求，保持活跃
                response = requests.get(f"{service_url}/", timeout=10)
                print(f"💓 [{config['bot_id']}] 心跳请求成功: {response.status_code}")
            else:
                print(f"💓 [{config['bot_id']}] 心跳机制运行中（无外部URL）")
        except Exception as e:
            print(f"💓 [{config['bot_id']}] 心跳请求失败: {e}")
        
        # 每10分钟发送一次心跳
        time.sleep(600)

# 启动心跳线程
heartbeat_thread = threading.Thread(target=start_heartbeat, daemon=True)
heartbeat_thread.start()
print(f"💓 [{config['bot_id']}] 心跳机制已启动，每10分钟发送一次请求")

# ==================== 机器人主程序 ====================
async def main():
    """主函数"""
    print(f"🚀 开始启动 {config['bot_name']}...")
    
    try:
        # 创建客户端
        app = Client(
            f"{config['bot_id']}_session",
            api_id=config['api_id'],
            api_hash=config['api_hash'],
            bot_token=config['bot_token']
        )
        
        # 启动机器人（带FloodWait处理）
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"🔄 [{config['bot_id']}] 尝试启动机器人 (第{retry_count + 1}次)...")
                await app.start()
                print(f"✅ [{config['bot_id']}] 机器人启动成功！")
                break
            except Exception as e:
                retry_count += 1
                if "FLOOD_WAIT" in str(e):
                    # 提取等待时间
                    import re
                    wait_match = re.search(r'wait of (\d+) seconds', str(e))
                    if wait_match:
                        wait_seconds = int(wait_match.group(1))
                        wait_minutes = wait_seconds // 60
                        print(f"⏰ [{config['bot_id']}] 遇到FloodWait，需要等待 {wait_minutes} 分钟 ({wait_seconds} 秒)")
                        print(f"🔄 [{config['bot_id']}] 等待中...")
                        await asyncio.sleep(wait_seconds + 10)  # 多等10秒确保安全
                        continue
                    else:
                        print(f"⚠️ [{config['bot_id']}] FloodWait时间未知，等待5分钟")
                        await asyncio.sleep(300)
                        continue
                elif retry_count < max_retries:
                    print(f"⚠️ [{config['bot_id']}] 启动失败，{retry_count}秒后重试: {e}")
                    await asyncio.sleep(retry_count * 10)
                    continue
                else:
                    raise e
        
        # 获取机器人信息
        me = await app.get_me()
        print(f"✅ {config['bot_name']} 启动成功！")
        print(f"🤖 机器人用户名: @{me.username}")
        print(f"🤖 机器人ID: {me.id}")
        print(f"🤖 机器人名称: {me.first_name}")
        print(f"🌐 多机器人部署成功，{config['bot_name']} 现在24小时运行！")
        print(f"⏳ 进入空闲状态，等待消息...")
        
        # 保持运行 - 使用更可靠的方式
        print(f"🔄 [{config['bot_id']}] 进入无限循环，保持机器人运行...")
        try:
            while True:
                try:
                    await asyncio.sleep(60)  # 每分钟检查一次
                    # 可以在这里添加健康检查
                    print(f"💚 [{config['bot_id']}] 机器人运行中...")
                except KeyboardInterrupt:
                    print(f"🛑 [{config['bot_id']}] 收到中断信号")
                    break
                except Exception as e:
                    print(f"⚠️ [{config['bot_id']}] 循环中出错: {e}")
                    await asyncio.sleep(5)  # 出错后等待5秒继续
        except Exception as e:
            print(f"❌ [{config['bot_id']}] 运行循环出错: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        print(f"❌ 详细错误: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print(f"🎯 {config['bot_name']} 程序开始...")
    
    try:
        # 运行主函数
        success = asyncio.run(main())
        if success:
            print(f"✅ {config['bot_name']} 运行完成")
        else:
            print(f"❌ {config['bot_name']} 运行失败")
    except KeyboardInterrupt:
        print(f"🛑 {config['bot_name']} 收到中断信号")
    except Exception as e:
        print(f"❌ {config['bot_name']} 主程序异常: {e}")
        import traceback
        print(f"❌ 详细错误: {traceback.format_exc()}")
    
    print(f"👋 {config['bot_name']} 程序结束")
