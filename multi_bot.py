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

# ==================== 配置管理 ====================
# 全局变量
user_configs = {}  # 存储每个用户的配置，包括频道组和功能设定
logged_in_users = {}  # 存储已登录用户的信息
pending_logins = {}  # 存储等待登录的用户状态
login_attempts = {}  # 存储登录尝试记录

# 用户凭据（这里应该从环境变量或配置文件读取）
USER_CREDENTIALS = {
    "demo": "demo123",
    "admin": "admin123"
}

# 管理员用户名列表
ADMIN_USERNAMES = ["admin"]

def save_user_configs():
    """保存用户配置到文件"""
    try:
        with open(f"user_configs_{config['bot_id']}.json", "w", encoding='utf-8') as f:
            json.dump(user_configs, f, ensure_ascii=False, indent=4)
        print(f"✅ [{config['bot_id']}] 用户配置已保存")
    except Exception as e:
        print(f"❌ [{config['bot_id']}] 保存用户配置失败: {e}")

def load_user_configs():
    """从文件加载用户配置"""
    global user_configs
    try:
        config_file = f"user_configs_{config['bot_id']}.json"
        if os.path.exists(config_file):
            with open(config_file, "r", encoding='utf-8') as f:
                user_configs = json.load(f)
            print(f"✅ [{config['bot_id']}] 用户配置已加载")
        else:
            print(f"ℹ️ [{config['bot_id']}] 用户配置文件不存在，将创建新配置")
    except Exception as e:
        print(f"❌ [{config['bot_id']}] 加载用户配置失败: {e}")
        user_configs = {}

def login_user(user_id, username):
    """记录用户登录"""
    logged_in_users[user_id] = {
        "username": username,
        "login_time": time.time(),
        "is_admin": username in ADMIN_USERNAMES
    }
    save_user_configs()

def is_user_logged_in(user_id):
    """检查用户是否已登录"""
    return user_id in logged_in_users

def can_attempt_login(user_id):
    """检查用户是否可以尝试登录（锁定功能已禁用）"""
    # 锁定功能已禁用，所有用户都可以尝试登录
    return True

def record_login_attempt(user_id, success=False):
    """记录登录尝试（锁定功能已禁用）"""
    user_id_str = str(user_id)
    current_time = time.time()
    
    if user_id_str not in login_attempts:
        login_attempts[user_id_str] = {"attempts": 0, "locked_until": 0}
    
    attempt_data = login_attempts[user_id_str]
    
    if success:
        # 登录成功，重置尝试次数
        attempt_data["attempts"] = 0
        attempt_data["locked_until"] = 0
    else:
        # 登录失败，但不锁定账户
        attempt_data["attempts"] += 1
        # 锁定功能已禁用
    
    save_user_configs()

async def show_login_screen(message):
    """显示登录界面"""
    user_id = message.from_user.id
    
    # 锁定检查已禁用，直接显示登录界面
    
    # 检查是否有失败记录
    attempts_info = ""
    user_id_str = str(user_id)
    if user_id_str in login_attempts:
        attempts = login_attempts[user_id_str].get("attempts", 0)
        if attempts > 0:
            attempts_info = f"\n⚠️ 登录失败次数：{attempts}/3"
    
    await message.reply_text(
        f"🔐 **{config['bot_name']} 访问验证**\n\n"
        f"请按以下格式输入登录信息：{attempts_info}\n"
        f"格式：`用户名:密码`\n"
        f"例如：`demo:demo123`\n\n"
        f"💡 如需获取账号，请联系管理员",
        parse_mode="Markdown"
    )
    
    # 标记用户正在等待输入用户名
    pending_logins[user_id] = {"waiting_for_username": True}

async def handle_username_input(message):
    """处理用户名:密码输入"""
    user_id = message.from_user.id
    login_input = message.text.strip()
    
    # 清除等待状态
    pending_logins.pop(user_id, None)
    
    if not can_attempt_login(user_id):
        await show_login_screen(message)
        return
    
    # 验证输入格式：用户名:密码
    if ":" not in login_input:
        # 格式错误
        await message.reply_text(
            f"❌ **格式错误**\n\n"
            f"请使用正确格式：`用户名:密码`\n"
            f"例如：`demo:demo123`\n\n"
            f"请重新输入："
        )
        pending_logins[user_id] = {"waiting_for_username": True}
        return
    
    try:
        username, password = login_input.split(":", 1)
        username = username.strip()
        password = password.strip()
    except ValueError:
        await message.reply_text(
            f"❌ **格式错误**\n\n"
            f"请使用正确格式：`用户名:密码`\n"
            f"请重新输入："
        )
        pending_logins[user_id] = {"waiting_for_username": True}
        return
    
    # 验证用户名和密码
    if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
        # 登录成功
        login_user(user_id, username)
        record_login_attempt(user_id, success=True)
        
        is_admin = username in ADMIN_USERNAMES
        admin_text = "\n👑 您拥有管理员权限" if is_admin else ""
        
        await message.reply_text(
            f"✅ **登录成功**\n\n"
            f"欢迎，{username}！{admin_text}\n"
            f"您现在可以使用机器人的所有功能。\n\n"
            f"💡 使用 /config 查看配置，/logout 退出登录",
            parse_mode="Markdown"
        )
    else:
        # 登录失败
        record_login_attempt(user_id, success=False)
        
        user_id_str = str(user_id)
        attempts = login_attempts[user_id_str].get("attempts", 0)
        
        remaining_attempts = 3 - attempts
        await message.reply_text(
            f"❌ **登录失败**\n\n"
            f"用户名或密码错误。\n"
            f"剩余尝试次数：{remaining_attempts}\n\n"
            f"请重新输入（格式：`用户名:密码`）："
        )
        pending_logins[user_id] = {"waiting_for_username": True}

# ==================== 机器人主程序 ====================
async def main():
    """主函数"""
    print(f"🚀 开始启动 {config['bot_name']}...")
    
    # 加载用户配置
    load_user_configs()
    
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
        
        # 添加消息处理器
        @app.on_message(filters.command("start"))
        async def start_command(client, message):
            """处理 /start 命令"""
            try:
                await message.reply_text(
                    f"🤖 **{config['bot_name']}** 启动成功！\n\n"
                    f"🔑 机器人ID: `{config['bot_id']}`\n"
                    f"🌐 状态: 正常运行中\n"
                    f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"💡 这是一个多机器人系统中的搬运机器人！",
                    parse_mode="Markdown"
                )
                print(f"💬 [{config['bot_id']}] 收到 /start 命令，来自用户 {message.from_user.id}")
            except Exception as e:
                print(f"❌ [{config['bot_id']}] 处理 /start 命令时出错: {e}")
        
        @app.on_message(filters.command("status"))
        async def status_command(client, message):
            """处理 /status 命令"""
            try:
                await message.reply_text(
                    f"📊 **{config['bot_name']} 状态报告**\n\n"
                    f"🔑 机器人ID: `{config['bot_id']}`\n"
                    f"🌐 服务状态: 正常运行\n"
                    f"💓 心跳状态: 活跃\n"
                    f"⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"✅ 机器人运行正常！",
                    parse_mode="Markdown"
                )
                print(f"💬 [{config['bot_id']}] 收到 /status 命令，来自用户 {message.from_user.id}")
            except Exception as e:
                print(f"❌ [{config['bot_id']}] 处理 /status 命令时出错: {e}")
        
        @app.on_message(filters.command("login"))
        async def login_command(client, message):
            """处理 /login 命令"""
            try:
                if is_user_logged_in(message.from_user.id):
                    await message.reply_text(
                        f"ℹ️ **您已经登录**\n\n"
                        f"用户名: {logged_in_users[message.from_user.id]['username']}\n"
                        f"登录时间: {datetime.fromtimestamp(logged_in_users[message.from_user.id]['login_time']).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"💡 如需重新登录，请先使用 /logout 命令",
                        parse_mode="Markdown"
                    )
                else:
                    await show_login_screen(message)
                print(f"💬 [{config['bot_id']}] 收到 /login 命令，来自用户 {message.from_user.id}")
            except Exception as e:
                print(f"❌ [{config['bot_id']}] 处理 /login 命令时出错: {e}")
        
        @app.on_message(filters.command("logout"))
        async def logout_command(client, message):
            """处理 /logout 命令"""
            try:
                user_id = message.from_user.id
                if user_id in logged_in_users:
                    username = logged_in_users[user_id]['username']
                    del logged_in_users[user_id]
                    save_user_configs()
                    await message.reply_text(
                        f"✅ **已退出登录**\n\n"
                        f"再见，{username}！\n"
                        f"如需重新使用机器人，请发送 /login 命令",
                        parse_mode="Markdown"
                    )
                else:
                    await message.reply_text(
                        f"ℹ️ **您尚未登录**\n\n"
                        f"请先使用 /login 命令登录",
                        parse_mode="Markdown"
                    )
                print(f"💬 [{config['bot_id']}] 收到 /logout 命令，来自用户 {message.from_user.id}")
            except Exception as e:
                print(f"❌ [{config['bot_id']}] 处理 /logout 命令时出错: {e}")
        
        @app.on_message(filters.command("config"))
        async def config_command(client, message):
            """处理 /config 命令"""
            try:
                user_id = message.from_user.id
                if not is_user_logged_in(user_id):
                    await message.reply_text(
                        f"❌ **请先登录**\n\n"
                        f"请使用 /login 命令登录后再查看配置",
                        parse_mode="Markdown"
                    )
                    return
                
                user_config = user_configs.get(str(user_id), {})
                channel_pairs = user_config.get("channel_pairs", [])
                
                config_text = f"📊 **{config['bot_name']} 配置信息**\n\n"
                config_text += f"🔑 机器人ID: `{config['bot_id']}`\n"
                config_text += f"👤 用户名: {logged_in_users[user_id]['username']}\n"
                config_text += f"📡 频道组数量: {len(channel_pairs)}\n\n"
                
                if channel_pairs:
                    config_text += "📋 **频道组列表：**\n"
                    for i, pair in enumerate(channel_pairs):
                        source = pair.get("source", "未设置")
                        target = pair.get("target", "未设置")
                        enabled = "✅" if pair.get("enabled", True) else "❌"
                        config_text += f"{i+1}. {enabled} 源: {source} → 目标: {target}\n"
                else:
                    config_text += "📋 **暂无频道组配置**\n"
                
                config_text += f"\n⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                await message.reply_text(config_text, parse_mode="Markdown")
                print(f"💬 [{config['bot_id']}] 收到 /config 命令，来自用户 {message.from_user.id}")
            except Exception as e:
                print(f"❌ [{config['bot_id']}] 处理 /config 命令时出错: {e}")
        
        # 处理文本消息（用于登录）
        @app.on_message(filters.text & ~filters.command)
        async def handle_text_message(client, message):
            """处理文本消息"""
            try:
                user_id = message.from_user.id
                
                # 检查是否正在等待登录输入
                if user_id in pending_logins and pending_logins[user_id].get("waiting_for_username"):
                    await handle_username_input(message)
                    return
                
                # 如果用户已登录，可以处理其他文本消息
                if is_user_logged_in(user_id):
                    await message.reply_text(
                        f"💬 **收到消息**\n\n"
                        f"您已登录，可以使用以下命令：\n"
                        f"• /config - 查看配置\n"
                        f"• /status - 查看状态\n"
                        f"• /logout - 退出登录\n\n"
                        f"💡 更多功能正在开发中...",
                        parse_mode="Markdown"
                    )
                else:
                    await message.reply_text(
                        f"ℹ️ **请先登录**\n\n"
                        f"请使用 /login 命令登录后使用机器人功能",
                        parse_mode="Markdown"
                    )
                
                print(f"💬 [{config['bot_id']}] 收到文本消息，来自用户 {message.from_user.id}")
            except Exception as e:
                print(f"❌ [{config['bot_id']}] 处理文本消息时出错: {e}")
        
        print(f"✅ 消息处理器已设置完成！")
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
