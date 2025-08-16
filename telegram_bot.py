#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用python-telegram-bot的Telegram机器人
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 从环境变量获取配置
def get_config():
    """从环境变量获取配置"""
    logger.info("🔧 正在读取环境变量配置...")
    
    bot_token = os.getenv('BOT_TOKEN')
    
    if not bot_token:
        logger.error("❌ 缺少环境变量: BOT_TOKEN")
        return None
    else:
        logger.info(f"✅ BOT_TOKEN: {'*' * (len(bot_token) - 4) + bot_token[-4:] if len(bot_token) > 4 else '***'}")
    
    return bot_token

# 获取配置
bot_token = get_config()
if not bot_token:
    logger.error("❌ 配置获取失败")
    exit(1)

# 命令处理器
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """启动命令"""
    user_id = update.effective_user.id
    logger.info(f"📱 收到 /start 命令，来自用户 {user_id}")
    
    try:
        await update.message.reply_text("🚀 python-telegram-bot机器人启动成功！")
        logger.info("✅ /start 命令响应成功")
    except Exception as e:
        logger.error(f"❌ /start 命令响应失败: {e}")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ping测试"""
    user_id = update.effective_user.id
    logger.info(f"🏓 收到 /ping 命令，来自用户 {user_id}")
    
    try:
        await update.message.reply_text("🏓 Pong! 机器人工作正常！")
        logger.info("✅ /ping 命令响应成功")
    except Exception as e:
        logger.error(f"❌ /ping 命令响应失败: {e}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """状态命令"""
    user_id = update.effective_user.id
    logger.info(f"📊 收到 /status 命令，来自用户 {user_id}")
    
    try:
        await update.message.reply_text("📊 机器人状态：正常运行中！")
        logger.info("✅ /status 命令响应成功")
    except Exception as e:
        logger.error(f"❌ /status 命令响应失败: {e}")

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """测试命令"""
    user_id = update.effective_user.id
    logger.info(f"🧪 收到 /test 命令，来自用户 {user_id}")
    
    try:
        await update.message.reply_text("🧪 测试命令响应正常！")
        logger.info("✅ /test 命令响应成功")
    except Exception as e:
        logger.error(f"❌ /test 命令响应失败: {e}")

# 处理所有文本消息
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理所有文本消息"""
    if update.message.text and not update.message.text.startswith('/'):
        user_id = update.effective_user.id
        text = update.message.text[:50]
        logger.info(f"💬 收到文本消息: {text}... 来自用户 {user_id}")
        
        try:
            await update.message.reply_text("👋 收到您的消息！python-telegram-bot机器人工作正常！")
            logger.info("✅ 文本消息响应成功")
        except Exception as e:
            logger.error(f"❌ 文本消息响应失败: {e}")

# 主函数
async def main():
    """主函数"""
    logger.info("🚀 开始启动python-telegram-bot机器人...")
    
    try:
        # 创建应用
        logger.info("🤖 正在创建Telegram应用...")
        application = Application.builder().token(bot_token).build()
        
        # 添加命令处理器
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("ping", ping_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("test", test_command))
        
        # 添加消息处理器
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        logger.info("✅ 机器人配置完成！")
        logger.info("🌐 python-telegram-bot机器人部署成功！")
        logger.info("⏳ 进入空闲状态，等待消息...")
        logger.info("💡 请发送 /start 命令测试机器人")
        
        # 启动机器人
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"❌ 启动失败: {e}")
        import traceback
        logger.error(f"❌ 详细错误: {traceback.format_exc()}")
        return False
    
    return True

if __name__ == "__main__":
    logger.info("🎯 python-telegram-bot机器人程序开始...")
    
    try:
        # 直接运行主函数，不使用asyncio.run()
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(main())
        if success:
            logger.info("✅ python-telegram-bot机器人运行完成")
        else:
            logger.error("❌ python-telegram-bot机器人运行失败")
    except KeyboardInterrupt:
        logger.info("🛑 收到中断信号")
    except Exception as e:
        logger.error(f"❌ 主程序异常: {e}")
        import traceback
        logger.error(f"❌ 详细错误: {traceback.format_exc()}")
    finally:
        try:
            loop.close()
        except:
            pass
    
    logger.info("👋 python-telegram-bot机器人程序结束")
