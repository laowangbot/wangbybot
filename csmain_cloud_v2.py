#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram搬运机器人 - 云部署版本 V2
更稳定的版本，添加更多日志和错误处理
"""

import os
import asyncio
import logging
import time
import signal
import sys
from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait, BadRequest

# 配置日志 - 更详细的格式
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot_cloud.log')
    ]
)

logger = logging.getLogger(__name__)

# 从环境变量获取配置
def get_config():
    """从环境变量获取配置"""
    logger.info("🔧 正在读取环境变量配置...")
    
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
        else:
            logger.info(f"✅ {key}: {'*' * (len(value) - 4) + value[-4:] if len(value) > 4 else '***'}")
    
    if missing:
        logger.error(f"❌ 缺少必要的环境变量: {', '.join(missing)}")
        logger.error("请在Render中设置以下环境变量:")
        logger.error("- API_ID")
        logger.error("- API_HASH") 
        logger.error("- BOT_TOKEN")
        sys.exit(1)
    
    logger.info("✅ 所有环境变量配置完成")
    return config

# 获取配置
config = get_config()

# 创建客户端
logger.info("🤖 正在创建Pyrogram客户端...")
app = Client(
    "csbybot_cloud_v2",
    api_id=config['api_id'],
    api_hash=config['api_hash'],
    bot_token=config['bot_token']
)

# 简单的机器人功能
@app.on_message(filters.command("start"))
async def start_command(client, message):
    """启动命令"""
    logger.info(f"📱 收到 /start 命令，来自用户 {message.from_user.id}")
    try:
        await message.reply_text(
            "🚀 **老湿姬2.0云部署版启动成功！**\n\n"
            "✅ 机器人已成功部署到云服务\n"
            "✅ 24小时稳定运行\n"
            "✅ 支持多用户并发使用\n\n"
            "🔧 当前状态: 正常运行\n"
            "🌐 部署平台: Render\n"
            "⏰ 启动时间: " + time.strftime("%Y-%m-%d %H:%M:%S")
        )
        logger.info("✅ /start 命令响应成功")
    except Exception as e:
        logger.error(f"❌ /start 命令响应失败: {e}")
        await message.reply_text("❌ 响应失败，请稍后重试")

@app.on_message(filters.command("status"))
async def status_command(client, message):
    """状态检查命令"""
    logger.info(f"📊 收到 /status 命令，来自用户 {message.from_user.id}")
    try:
        await message.reply_text(
            "📊 **机器人状态报告**\n\n"
            "🟢 状态: 正常运行\n"
            "🌐 平台: Render云服务\n"
            "⏰ 运行时间: 持续运行中\n"
            "👥 用户: 支持多用户\n\n"
            "🎉 云部署成功！机器人现在可以24小时运行了！"
        )
        logger.info("✅ /status 命令响应成功")
    except Exception as e:
        logger.error(f"❌ /status 命令响应失败: {e}")
        await message.reply_text("❌ 状态查询失败，请稍后重试")

@app.on_message(filters.command("help"))
async def help_command(client, message):
    """帮助命令"""
    logger.info(f"❓ 收到 /help 命令，来自用户 {message.from_user.id}")
    try:
        help_text = """
🤖 **老湿姬2.0云部署版 - 帮助信息**

📋 **可用命令:**
/start - 启动机器人
/status - 查看状态
/help - 显示此帮助信息
/ping - 测试响应

🔧 **功能特点:**
✅ 云服务部署，24小时运行
✅ 自动重启和恢复
✅ 支持多用户并发
✅ 稳定可靠

🌐 **部署信息:**
平台: Render
状态: 正常运行
版本: 2.0云部署版 V2

💡 **提示:** 机器人已成功部署到云服务，无需本地运行！
"""
        await message.reply_text(help_text)
        logger.info("✅ /help 命令响应成功")
    except Exception as e:
        logger.error(f"❌ /help 命令响应失败: {e}")
        await message.reply_text("❌ 帮助信息获取失败，请稍后重试")

@app.on_message(filters.command("ping"))
async def ping_command(client, message):
    """ping测试命令"""
    logger.info(f"🏓 收到 /ping 命令，来自用户 {message.from_user.id}")
    try:
        start_time = time.time()
        reply = await message.reply_text("🏓 Pong!")
        end_time = time.time()
        latency = (end_time - start_time) * 1000
        
        await reply.edit_text(f"🏓 **Pong!**\n\n⏱️ 响应时间: {latency:.1f}ms\n🌐 云服务运行正常")
        logger.info(f"✅ /ping 命令响应成功，延迟: {latency:.1f}ms")
    except Exception as e:
        logger.error(f"❌ /ping 命令响应失败: {e}")
        await message.reply_text("❌ Ping测试失败，请稍后重试")

# 错误处理
@app.on_message(filters.all)
async def handle_all_messages(client, message):
    """处理所有其他消息"""
    if message.text and not message.text.startswith('/'):
        logger.info(f"💬 收到普通消息: {message.text[:50]}... 来自用户 {message.from_user.id}")
        try:
            await message.reply_text(
                "👋 收到您的消息！\n\n"
                "使用 /help 查看可用命令\n"
                "使用 /status 查看机器人状态\n"
                "使用 /ping 测试响应速度"
            )
            logger.info("✅ 普通消息响应成功")
        except Exception as e:
            logger.error(f"❌ 普通消息响应失败: {e}")

# 启动函数
async def main():
    """主函数"""
    logger.info("🚀 正在启动老湿姬2.0云部署版 V2...")
    
    try:
        # 启动机器人
        logger.info("🔌 正在连接Telegram...")
        await app.start()
        logger.info("✅ 机器人启动成功！")
        
        # 获取机器人信息
        me = await app.get_me()
        logger.info(f"🤖 机器人用户名: @{me.username}")
        logger.info(f"🤖 机器人ID: {me.id}")
        logger.info(f"🤖 机器人名称: {me.first_name}")
        
        logger.info("🌐 云部署成功，机器人现在24小时运行！")
        logger.info("⏳ 进入空闲状态，等待消息...")
        
        # 保持运行
        await idle()
        
    except Exception as e:
        logger.error(f"❌ 启动失败: {e}")
        logger.error(f"❌ 错误类型: {type(e).__name__}")
        import traceback
        logger.error(f"❌ 详细错误: {traceback.format_exc()}")
        sys.exit(1)
    
    finally:
        # 停止机器人
        logger.info("🛑 正在停止机器人...")
        try:
            await app.stop()
            logger.info("🛑 机器人已停止")
        except Exception as e:
            logger.error(f"❌ 停止机器人时出错: {e}")

# 信号处理
def signal_handler(signum, frame):
    """信号处理器"""
    logger.info(f"🛑 收到停止信号 {signum}，正在关闭机器人...")
    sys.exit(0)

if __name__ == "__main__":
    logger.info("🎯 程序开始执行...")
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("📡 信号处理器已注册")
    
    try:
        # 运行主函数
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 收到键盘中断信号")
    except Exception as e:
        logger.error(f"❌ 主程序异常: {e}")
        import traceback
        logger.error(f"❌ 详细错误: {traceback.format_exc()}")
        sys.exit(1)
    
    logger.info("👋 程序结束")
