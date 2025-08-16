#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础版Telegram机器人 - 使用最基础的Pyrogram语法
"""

import os
import asyncio
import logging
from pyrogram import Client, filters

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
    
    config = {
        'api_id': os.getenv('API_ID'),
        'api_hash': os.getenv('API_HASH'),
        'bot_token': os.getenv('BOT_TOKEN')
    }
    
    # 检查配置
    for key, value in config.items():
        if not value:
            logger.error(f"❌ 缺少环境变量: {key}")
            return None
        else:
            logger.info(f"✅ {key}: {'*' * (len(value) - 4) + value[-4:] if len(value) > 4 else '***'}")
    
    return config

# 获取配置
config = get_config()
if not config:
    logger.error("❌ 配置获取失败")
    exit(1)

# 创建客户端
logger.info("🤖 正在创建Pyrogram客户端...")
app = Client(
    "basic_bot",
    api_id=config['api_id'],
    api_hash=config['api_hash'],
    bot_token=config['bot_token']
)

# 基础消息处理器 - 使用最简单的语法
@app.on_message(filters.command("start"))
async def start_command(client, message):
    """启动命令"""
    logger.info(f"📱 收到 /start 命令，来自用户 {message.from_user.id}")
    
    try:
        await message.reply_text("🚀 基础版机器人启动成功！")
        logger.info("✅ /start 命令响应成功")
    except Exception as e:
        logger.error(f"❌ /start 命令响应失败: {e}")

@app.on_message(filters.command("test"))
async def test_command(client, message):
    """测试命令"""
    logger.info(f"🧪 收到 /test 命令，来自用户 {message.from_user.id}")
    
    try:
        await message.reply_text("🧪 测试命令响应正常！")
        logger.info("✅ /test 命令响应成功")
    except Exception as e:
        logger.error(f"❌ /test 命令响应失败: {e}")

# 处理所有消息 - 使用最基础的过滤器
@app.on_message(filters.all)
async def handle_all(client, message):
    """处理所有消息"""
    if message.text and not message.text.startswith('/'):
        logger.info(f"💬 收到普通消息: {message.text[:50]}... 来自用户 {message.from_user.id}")
        
        try:
            await message.reply_text("👋 收到您的消息！基础版机器人工作正常！")
            logger.info("✅ 普通消息响应成功")
        except Exception as e:
            logger.error(f"❌ 普通消息响应失败: {e}")

# 启动函数
async def main():
    """主函数"""
    logger.info("🚀 开始启动基础版机器人...")
    
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
        
        logger.info("🌐 基础版机器人部署成功！")
        logger.info("⏳ 进入空闲状态，等待消息...")
        logger.info("💡 请发送 /start 或 /test 命令测试机器人")
        
        # 保持运行 - 使用简单的循环
        while True:
            await asyncio.sleep(3)
            logger.info("💓 机器人心跳 - 正在运行中...")
        
    except Exception as e:
        logger.error(f"❌ 启动失败: {e}")
        import traceback
        logger.error(f"❌ 详细错误: {traceback.format_exc()}")
        return False
    
    finally:
        logger.info("🛑 正在停止机器人...")
        try:
            await app.stop()
            logger.info("🛑 机器人已停止")
        except Exception as e:
            logger.error(f"❌ 停止机器人时出错: {e}")
    
    return True

if __name__ == "__main__":
    logger.info("🎯 基础版机器人程序开始...")
    
    try:
        # 运行主函数
        success = asyncio.run(main())
        if success:
            logger.info("✅ 基础版机器人运行完成")
        else:
            logger.error("❌ 基础版机器人运行失败")
    except KeyboardInterrupt:
        logger.info("🛑 收到中断信号")
    except Exception as e:
        logger.error(f"❌ 主程序异常: {e}")
        import traceback
        logger.error(f"❌ 详细错误: {traceback.format_exc()}")
    
    logger.info("👋 基础版机器人程序结束")
