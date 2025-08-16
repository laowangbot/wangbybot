#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多机器人启动器 - 同时启动多个机器人实例
支持Render部署和错误处理
"""

import os
import sys
import time
import asyncio
import logging
import threading
from datetime import datetime
from multi_bot_config import get_active_bots, validate_bot_config

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('multi_bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

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
                response = f"""
                <html>
                <head>
                    <title>多机器人系统</title>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f0f0f0; }}
                        .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        .status {{ color: #28a745; font-weight: bold; }}
                        .time {{ color: #6c757d; }}
                        .bots {{ margin-top: 20px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🤖 多机器人系统</h1>
                        <p class="status">状态：正常运行中</p>
                        <p class="time">启动时间：{current_time}</p>
                        <div class="bots">
                            <h3>机器人状态：</h3>
                            <p>✅ 系统已启动，机器人正在运行</p>
                        </div>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(response.encode('utf-8'))
            
            def log_message(self, format, *args):
                pass
        
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"🌐 启动端口服务器，监听端口 {port}")
        
        with socketserver.TCPServer(("", port), SimpleHandler) as httpd:
            logger.info(f"✅ 端口服务器启动成功，端口 {port}")
            httpd.serve_forever()
    
    except Exception as e:
        logger.error(f"❌ 端口服务器启动失败: {e}")

# ==================== 单个机器人管理器 ====================
class BotManager:
    def __init__(self, bot_key, bot_config):
        self.bot_key = bot_key
        self.bot_config = bot_config
        self.app = None
        self.is_running = False
        self.last_error = None
        
    async def start_bot(self):
        """启动单个机器人"""
        try:
            logger.info(f"🚀 正在启动 {self.bot_config['name']}...")
            
            from pyrogram import Client
            
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
            logger.info(f"✅ {self.bot_config['name']} 启动成功！")
            
            # 保持运行
            await self.app.idle()
            
        except Exception as e:
            self.last_error = str(e)
            self.is_running = False
            logger.error(f"❌ {self.bot_config['name']} 启动失败: {e}")
            
    async def stop_bot(self):
        """停止机器人"""
        if self.app and self.is_running:
            try:
                await self.app.stop()
                self.is_running = False
                logger.info(f"🛑 {self.bot_config['name']} 已停止")
            except Exception as e:
                logger.error(f"❌ 停止 {self.bot_config['name']} 时出错: {e}")

# ==================== 多机器人管理器 ====================
class MultiBotManager:
    def __init__(self):
        self.bot_managers = {}
        self.running_tasks = []
        
    def add_bot(self, bot_key, bot_config):
        """添加机器人"""
        bot_manager = BotManager(bot_key, bot_config)
        self.bot_managers[bot_key] = bot_manager
        logger.info(f"➕ 已添加机器人: {bot_config['name']}")
        
    async def start_all_bots(self):
        """启动所有机器人"""
        if not self.bot_managers:
            logger.warning("⚠️ 没有配置机器人")
            return
            
        logger.info(f"🚀 开始启动 {len(self.bot_managers)} 个机器人...")
        
        # 为每个机器人创建任务
        for bot_key, bot_manager in self.bot_managers.items():
            task = asyncio.create_task(bot_manager.start_bot())
            self.running_tasks.append(task)
            
        # 等待所有机器人启动
        try:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"❌ 机器人运行出错: {e}")
            
    async def stop_all_bots(self):
        """停止所有机器人"""
        logger.info("🛑 正在停止所有机器人...")
        
        for bot_manager in self.bot_managers.values():
            await bot_manager.stop_bot()
            
        # 取消所有运行中的任务
        for task in self.running_tasks:
            if not task.done():
                task.cancel()
                
        logger.info("✅ 所有机器人已停止")

# ==================== 主程序 ====================
async def main():
    """主程序"""
    try:
        logger.info("🔧 多机器人系统启动中...")
        
        # 检查环境变量
        active_bots = get_active_bots()
        if not active_bots:
            logger.error("❌ 没有找到有效的机器人配置")
            logger.error("请检查环境变量设置")
            return
            
        # 创建多机器人管理器
        multi_bot_manager = MultiBotManager()
        
        # 添加所有有效的机器人
        for bot_key, bot_config in active_bots.items():
            multi_bot_manager.add_bot(bot_key, bot_config)
            
        # 启动端口服务器（后台线程）
        port_thread = threading.Thread(target=start_port_server, daemon=True)
        port_thread.start()
        logger.info("✅ 端口服务器线程已启动")
        
        # 等待端口服务器启动
        await asyncio.sleep(2)
        
        # 启动所有机器人
        await multi_bot_manager.start_all_bots()
        
    except KeyboardInterrupt:
        logger.info("⚠️ 收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"❌ 程序运行出错: {e}")
        logger.error("详细错误信息:", exc_info=True)
    finally:
        logger.info("👋 程序已退出")

if __name__ == "__main__":
    # 运行主程序
    asyncio.run(main())
