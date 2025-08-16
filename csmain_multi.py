# ==================== 代码版本确认 ====================
print("正在运行老湿姬2.0专版 - 多机器人版本...")

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
import threading
from datetime import datetime
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from pyrogram.enums import ChatType
from pyrogram.errors.exceptions import BadRequest, FloodWait
from urllib.parse import urlparse

# ==================== 多机器人配置 ====================
BOTS_CONFIG = {
    'bot1': {
        'name': '老湿姬2.0专版-1号',
        'api_id': os.getenv('BOT1_API_ID'),
        'api_hash': os.getenv('BOT1_API_HASH'),
        'bot_token': os.getenv('BOT1_BOT_TOKEN'),
        'description': '第一个机器人实例'
    },
    'bot2': {
        'name': '老湿姬2.0专版-2号',
        'api_id': os.getenv('BOT2_API_ID'),
        'api_hash': os.getenv('BOT2_API_HASH'),
        'bot_token': os.getenv('BOT2_BOT_TOKEN'),
        'description': '第二个机器人实例'
    },
    'bot3': {
        'name': '老湿姬2.0专版-3号',
        'api_id': os.getenv('BOT3_API_ID'),
        'api_hash': os.getenv('BOT3_API_HASH'),
        'bot_token': os.getenv('BOT3_BOT_TOKEN'),
        'description': '第三个机器人实例'
    }
}

# ==================== 配置验证 ====================
def validate_bot_config(bot_key):
    """验证机器人配置是否完整"""
    bot_config = BOTS_CONFIG.get(bot_key)
    if not bot_config:
        return False, f"机器人 {bot_key} 配置不存在"
    
    required_fields = ['api_id', 'api_hash', 'bot_token']
    missing_fields = []
    
    for field in required_fields:
        if not bot_config.get(field):
            missing_fields.append(field)
    
    if missing_fields:
        return False, f"机器人 {bot_key} 缺少字段: {', '.join(missing_fields)}"
    
    return True, "配置验证通过"

def get_active_bots():
    """获取所有配置完整的机器人"""
    active_bots = {}
    
    for bot_key, bot_config in BOTS_CONFIG.items():
        is_valid, message = validate_bot_config(bot_key)
        if is_valid:
            active_bots[bot_key] = bot_config
            print(f"✅ {bot_config['name']}: {message}")
        else:
            print(f"❌ {bot_config['name']}: {message}")
    
    return active_bots

# ==================== 端口服务器 ====================
def start_port_server():
    """启动端口服务器，用于Render Web Service"""
    try:
        import http.server
        import socketserver
        
        class SimpleHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                active_bots = get_active_bots()
                bot_count = len(active_bots)
                
                response = f"""
                <html>
                <head>
                    <title>老湿姬2.0专版 - 多机器人系统</title>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f0f0f0; }}
                        .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        .status {{ color: #28a745; font-weight: bold; }}
                        .time {{ color: #6c757d; }}
                        .bots {{ margin-top: 20px; }}
                        .bot-item {{ margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🤖 老湿姬2.0专版 - 多机器人系统</h1>
                        <p class="status">状态：正常运行中</p>
                        <p class="time">启动时间：{current_time}</p>
                        <div class="bots">
                            <h3>机器人状态：</h3>
                            <p>✅ 系统已启动，{bot_count} 个机器人正在运行</p>
                            <div class="bot-list">
                """
                
                for bot_key, bot_config in active_bots.items():
                    response += f"""
                                <div class="bot-item">
                                    <strong>{bot_config['name']}</strong><br>
                                    <small>{bot_config['description']}</small>
                                </div>
                    """
                
                response += """
                            </div>
                        </div>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(response.encode('utf-8'))
            
            def log_message(self, format, *args):
                pass
        
        port = int(os.environ.get('PORT', 8080))
        print(f"🌐 启动端口服务器，监听端口 {port}")
        
        with socketserver.TCPServer(("", port), SimpleHandler) as httpd:
            print(f"✅ 端口服务器启动成功，端口 {port}")
            httpd.serve_forever()
    
    except Exception as e:
        print(f"❌ 端口服务器启动失败: {e}")

# ==================== FloodWait管理器 ====================
class FloodWaitManager:
    def __init__(self):
        self.flood_wait_times = {}  # 记录每个操作的等待时间
        self.last_operation_time = {}  # 记录每个操作的最后执行时间
        self.operation_delays = {  # 不同操作的延迟配置（已最小化）
            'edit_message': 0.5,    # 编辑消息间隔0.5秒
            'send_message': 0.3,    # 发送消息间隔0.3秒
            'delete_message': 0.2,  # 删除消息间隔0.2秒
            'forward_message': 0.4, # 转发消息间隔0.4秒
            'pin_message': 1.0,     # 置顶消息间隔1.0秒
            'unpin_message': 1.0,   # 取消置顶间隔1.0秒
            'restrict_chat_member': 2.0, # 限制成员间隔2.0秒
            'promote_chat_member': 2.0,  # 提升成员间隔2.0秒
            'set_chat_photo': 3.0,       # 设置头像间隔3.0秒
            'delete_chat_photo': 2.0,    # 删除头像间隔2.0秒
            'set_chat_title': 2.0,       # 设置标题间隔2.0秒
            'set_chat_description': 2.0, # 设置描述间隔2.0秒
            'pin_chat_message': 1.0,     # 置顶聊天消息间隔1.0秒
            'unpin_chat_message': 1.0,   # 取消置顶聊天消息间隔1.0秒
            'get_chat_members': 1.0,     # 获取成员列表间隔1.0秒
            'get_chat_history': 0.5,     # 获取聊天历史间隔0.5秒
            'search_messages': 0.5,      # 搜索消息间隔0.5秒
            'get_media_group': 0.3,      # 获取媒体组间隔0.3秒
            'download_media': 0.2,       # 下载媒体间隔0.2秒
            'upload_media': 1.0,         # 上传媒体间隔1.0秒
            'create_invite_link': 5.0,   # 创建邀请链接间隔5.0秒
            'export_chat_invite_link': 5.0, # 导出邀请链接间隔5.0秒
            'revoke_chat_invite_link': 3.0, # 撤销邀请链接间隔3.0秒
            'get_chat_invite_link': 1.0,    # 获取邀请链接间隔1.0秒
            'get_chat_invite_link_count': 1.0, # 获取邀请链接数量间隔1.0秒
            'get_chat_invite_link_members': 1.0, # 获取邀请链接成员间隔1.0秒
            'edit_chat_invite_link': 3.0,    # 编辑邀请链接间隔3.0秒
            'delete_chat_invite_link': 3.0,  # 删除邀请链接间隔3.0秒
            'get_chat_administrators': 1.0,  # 获取管理员间隔1.0秒
            'get_chat_member': 0.5,          # 获取成员信息间隔0.5秒
            'get_chat_members_count': 0.5,   # 获取成员数量间隔0.5秒
            'get_chat_online_count': 0.5,    # 获取在线成员数量间隔0.5秒
            'get_chat_history': 0.5,         # 获取聊天历史间隔0.5秒
            'get_chat_history_count': 0.5,   # 获取聊天历史数量间隔0.5秒
            'get_chat_history_from': 0.5,    # 从指定位置获取聊天历史间隔0.5秒
            'get_chat_history_until': 0.5,   # 获取到指定位置的聊天历史间隔0.5秒
            'get_chat_history_around': 0.5,  # 获取指定消息周围的聊天历史间隔0.5秒
            'get_chat_history_search': 0.5,  # 搜索聊天历史间隔0.5秒
            'get_chat_history_filter': 0.5,  # 过滤聊天历史间隔0.5秒
            'get_chat_history_reverse': 0.5, # 反向获取聊天历史间隔0.5秒
            'get_chat_history_limit': 0.5,   # 限制聊天历史数量间隔0.5秒
            'get_chat_history_offset': 0.5,  # 偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_id': 0.5, # 从指定ID偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_date': 0.5, # 从指定日期偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_message': 0.5, # 从指定消息偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_chat': 0.5, # 从指定聊天偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_user': 0.5, # 从指定用户偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_bot': 0.5, # 从指定机器人偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_channel': 0.5, # 从指定频道偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_supergroup': 0.5, # 从指定超级群组偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_group': 0.5, # 从指定群组偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_private': 0.5, # 从指定私聊偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_secret': 0.5, # 从指定秘密聊天偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_bot': 0.5, # 从指定机器人偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_channel': 0.5, # 从指定频道偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_supergroup': 0.5, # 从指定超级群组偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_group': 0.5, # 从指定群组偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_private': 0.5, # 从指定私聊偏移获取聊天历史间隔0.5秒
            'get_chat_history_offset_secret': 0.5, # 从指定秘密聊天偏移获取聊天历史间隔0.5秒
        }
    
    def should_wait(self, operation_type):
        """检查是否需要等待"""
        if operation_type not in self.last_operation_time:
            return False
        
        last_time = self.last_operation_time[operation_type]
        delay = self.operation_delays.get(operation_type, 1.0)
        
        if time.time() - last_time < delay:
            return True
        
        return False
    
    def record_operation(self, operation_type):
        """记录操作时间"""
        self.last_operation_time[operation_type] = time.time()
    
    def get_wait_time(self, operation_type):
        """获取需要等待的时间"""
        if operation_type not in self.last_operation_time:
            return 0
        
        last_time = self.last_operation_time[operation_type]
        delay = self.operation_delays.get(operation_type, 1.0)
        elapsed = time.time() - last_time
        
        if elapsed < delay:
            return delay - elapsed
        
        return 0

# ==================== 机器人管理器 ====================
class BotManager:
    def __init__(self, bot_key, bot_config):
        self.bot_key = bot_key
        self.bot_config = bot_config
        self.app = None
        self.is_running = False
        self.flood_wait_manager = FloodWaitManager()
        
    async def start_bot(self):
        """启动单个机器人"""
        try:
            print(f"🚀 正在启动 {self.bot_config['name']}...")
            
            # 创建机器人客户端
            self.app = Client(
                f"csbybot_{self.bot_key}",
                api_id=self.bot_config['api_id'],
                api_hash=self.bot_config['api_hash'],
                bot_token=self.bot_config['bot_token']
            )
            
            # 启动机器人
            await self.app.start()
            self.is_running = True
            print(f"✅ {self.bot_config['name']} 启动成功！")
            
            # 设置机器人功能
            await self.setup_bot_functions()
            
            # 保持运行
            await self.app.idle()
            
        except Exception as e:
            self.is_running = False
            print(f"❌ {self.bot_config['name']} 启动失败: {e}")
            
    async def setup_bot_functions(self):
        """设置机器人功能"""
        try:
            # 这里可以添加您原有的机器人功能代码
            # 例如：消息处理、命令处理等
            
            @self.app.on_message(filters.command("start"))
            async def start_command(client, message):
                await message.reply_text(f"🤖 您好！我是 {self.bot_config['name']}\n\n{self.bot_config['description']}")
            
            @self.app.on_message(filters.command("help"))
            async def help_command(client, message):
                help_text = f"""
🤖 {self.bot_config['name']} 帮助信息

可用命令：
/start - 开始使用
/help - 显示帮助
/status - 显示状态
/info - 显示机器人信息

{self.bot_config['description']}
                """
                await message.reply_text(help_text)
            
            @self.app.on_message(filters.command("status"))
            async def status_command(client, message):
                status_text = f"""
🤖 {self.bot_config['name']} 状态

✅ 状态：正常运行
🕐 启动时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
📊 机器人ID：{self.bot_key}
🔑 API状态：正常
                """
                await message.reply_text(status_text)
            
            @self.app.on_message(filters.command("info"))
            async def info_command(client, message):
                info_text = f"""
🤖 {self.bot_config['name']} 信息

📝 名称：{self.bot_config['name']}
📋 描述：{self.bot_config['description']}
🆔 机器人ID：{self.bot_config['bot_token'][:10]}...
🔑 API ID：{self.bot_config['api_id']}
⏰ 运行时间：正常运行中
                """
                await message.reply_text(info_text)
            
            print(f"✅ {self.bot_config['name']} 功能设置完成")
            
        except Exception as e:
            print(f"❌ {self.bot_config['name']} 功能设置失败: {e}")
            
    async def stop_bot(self):
        """停止机器人"""
        if self.app and self.is_running:
            try:
                await self.app.stop()
                self.is_running = False
                print(f"🛑 {self.bot_config['name']} 已停止")
            except Exception as e:
                print(f"❌ 停止 {self.bot_config['name']} 时出错: {e}")

# ==================== 多机器人管理器 ====================
class MultiBotManager:
    def __init__(self):
        self.bot_managers = {}
        self.running_tasks = []
        
    def add_bot(self, bot_key, bot_config):
        """添加机器人"""
        bot_manager = BotManager(bot_key, bot_config)
        self.bot_managers[bot_key] = bot_manager
        print(f"➕ 已添加机器人: {bot_config['name']}")
        
    async def start_all_bots(self):
        """启动所有机器人"""
        if not self.bot_managers:
            print("⚠️ 没有配置机器人")
            return
            
        print(f"🚀 开始启动 {len(self.bot_managers)} 个机器人...")
        
        # 为每个机器人创建任务
        for bot_key, bot_manager in self.bot_managers.items():
            task = asyncio.create_task(bot_manager.start_bot())
            self.running_tasks.append(task)
            
        # 等待所有机器人启动
        try:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
        except Exception as e:
            print(f"❌ 机器人运行出错: {e}")
            
    async def stop_all_bots(self):
        """停止所有机器人"""
        print("🛑 正在停止所有机器人...")
        
        for bot_manager in self.bot_managers.values():
            await bot_manager.stop_bot()
            
        # 取消所有运行中的任务
        for task in self.running_tasks:
            if not task.done():
                task.cancel()
                
        print("✅ 所有机器人已停止")

# ==================== 主程序 ====================
async def main():
    """主程序"""
    try:
        print("🔧 多机器人系统启动中...")
        
        # 检查环境变量
        active_bots = get_active_bots()
        if not active_bots:
            print("❌ 没有找到有效的机器人配置")
            print("请检查环境变量设置")
            return
            
        # 创建多机器人管理器
        multi_bot_manager = MultiBotManager()
        
        # 添加所有有效的机器人
        for bot_key, bot_config in active_bots.items():
            multi_bot_manager.add_bot(bot_key, bot_config)
            
        # 启动端口服务器（后台线程）
        port_thread = threading.Thread(target=start_port_server, daemon=True)
        port_thread.start()
        print("✅ 端口服务器线程已启动")
        
        # 等待端口服务器启动
        await asyncio.sleep(2)
        
        # 启动所有机器人
        await multi_bot_manager.start_all_bots()
        
    except KeyboardInterrupt:
        print("⚠️ 收到中断信号，正在关闭...")
    except Exception as e:
        print(f"❌ 程序运行出错: {e}")
        print("详细错误信息:", exc_info=True)
    finally:
        print("👋 程序已退出")

# ==================== 启动端口服务器 ====================
# 在后台启动端口服务器
port_thread = threading.Thread(target=start_port_server, daemon=True)
port_thread.start()

if __name__ == "__main__":
    # 运行主程序
    asyncio.run(main())
