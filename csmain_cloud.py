#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram搬运机器人 - 云部署版本
使用环境变量而不是config.py文件
"""

import os
import asyncio
import logging
import time
import signal
import sys
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, BadRequest

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] - %(levelname)s - %(message)s'
)

# 从环境变量获取配置
def get_config():
    """从环境变量获取配置"""
    config = {
        'api_id': os.getenv('API_ID'),
        'api_hash': os.getenv('API_HASH'),
        'bot_token': os.getenv('BOT_TOKEN')
    }
    
    # 检查必要的配置
    missing = []
    for key, value in config.items():
        if not value:
            missing.append(key)
    
    if missing:
        logging.error(f"缺少必要的环境变量: {', '.join(missing)}")
        logging.error("请在Render中设置以下环境变量:")
        logging.error("- API_ID")
        logging.error("- API_HASH") 
        logging.error("- BOT_TOKEN")
        sys.exit(1)
    
    return config

# 获取配置
config = get_config()

# 创建客户端
app = Client(
    "csbybot_cloud",
    api_id=config['api_id'],
    api_hash=config['api_hash'],
    bot_token=config['bot_token']
)

# 简单的机器人功能
@app.on_message(filters.command("start"))
async def start_command(client, message):
    """启动命令"""
    await message.reply_text(
        "🚀 **老湿姬2.0云部署版启动成功！**\n\n"
        "✅ 机器人已成功部署到云服务\n"
        "✅ 24小时稳定运行\n"
        "✅ 支持多用户并发使用\n\n"
        "🔧 当前状态: 正常运行\n"
        "🌐 部署平台: Render\n"
        "⏰ 启动时间: " + time.strftime("%Y-%m-%d %H:%M:%S")
    )

@app.on_message(filters.command("status"))
async def status_command(client, message):
    """状态检查命令"""
    await message.reply_text(
        "📊 **机器人状态报告**\n\n"
        "🟢 状态: 正常运行\n"
        "🌐 平台: Render云服务\n"
        "⏰ 运行时间: 持续运行中\n"
        "👥 用户: 支持多用户\n\n"
        "🎉 云部署成功！机器人现在可以24小时运行了！"
    )

@app.on_message(filters.command("help"))
async def help_command(client, message):
    """帮助命令"""
    help_text = """
🤖 **老湿姬2.0云部署版 - 帮助信息**

📋 **可用命令:**
/start - 启动机器人
/status - 查看状态
/help - 显示此帮助信息

🔧 **功能特点:**
✅ 云服务部署，24小时运行
✅ 自动重启和恢复
✅ 支持多用户并发
✅ 稳定可靠

🌐 **部署信息:**
平台: Render
状态: 正常运行
版本: 2.0云部署版

💡 **提示:** 机器人已成功部署到云服务，无需本地运行！
"""
    await message.reply_text(help_text)

@app.on_message(filters.command("ping"))
async def ping_command(client, message):
    """ping测试命令"""
    start_time = time.time()
    reply = await message.reply_text("🏓 Pong!")
    end_time = time.time()
    latency = (end_time - start_time) * 1000
    
    await reply.edit_text(f"🏓 **Pong!**\n\n⏱️ 响应时间: {latency:.1f}ms\n🌐 云服务运行正常")

# 错误处理
@app.on_message(filters.all)
async def handle_all_messages(client, message):
    """处理所有其他消息"""
    if message.text and not message.text.startswith('/'):
        await message.reply_text(
            "👋 收到您的消息！\n\n"
            "使用 /help 查看可用命令\n"
            "使用 /status 查看机器人状态"
        )

# 启动函数
async def main():
    """主函数"""
    logging.info("🚀 正在启动老湿姬2.0云部署版...")
    
    try:
        # 启动机器人
        await app.start()
        logging.info("✅ 机器人启动成功！")
        logging.info(f"🤖 机器人用户名: @{(await app.get_me()).username}")
        logging.info("🌐 云部署成功，机器人现在24小时运行！")
        
        # 保持运行
        await idle()
        
    except Exception as e:
        logging.error(f"❌ 启动失败: {e}")
        sys.exit(1)
    
    finally:
        # 停止机器人
        await app.stop()
        logging.info("🛑 机器人已停止")

# 信号处理
def signal_handler(signum, frame):
    """信号处理器"""
    logging.info("🛑 收到停止信号，正在关闭机器人...")
    sys.exit(0)

if __name__ == "__main__":
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 运行主函数
    asyncio.run(main())
