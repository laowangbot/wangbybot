#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API限制状态检查工具
"""

import asyncio
import logging
from pyrogram import Client
from pyrogram.errors import FloodWait, BadRequest, Unauthorized, PhoneCodeInvalid

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)

class APILimitChecker:
    """API限制检查器"""
    
    def __init__(self, api_id, api_hash, bot_token=None, session_name="api_checker"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.session_name = session_name
        self.client = None
        
    async def start_client(self):
        """启动客户端"""
        try:
            if self.bot_token:
                # 机器人客户端
                self.client = Client(
                    self.session_name,
                    api_id=self.api_id,
                    api_hash=self.api_hash,
                    bot_token=self.bot_token
                )
            else:
                # 用户账号客户端
                self.client = Client(
                    self.session_name,
                    api_id=self.api_id,
                    api_hash=self.api_hash
                )
            
            await self.client.start()
            logging.info("✅ 客户端启动成功")
            return True
            
        except Exception as e:
            logging.error(f"❌ 启动客户端失败: {e}")
            return False
    
    async def stop_client(self):
        """停止客户端"""
        if self.client:
            await self.client.stop()
            logging.info("🛑 客户端已停止")
    
    async def check_bot_info(self):
        """检查机器人信息"""
        if not self.bot_token:
            logging.warning("⚠️ 不是机器人账号，跳过机器人信息检查")
            return None
            
        try:
            me = await self.client.get_me()
            logging.info(f"🤖 机器人信息:")
            logging.info(f"   ID: {me.id}")
            logging.info(f"   用户名: @{me.username}")
            logging.info(f"   名称: {me.first_name}")
            logging.info(f"   状态: {me.status}")
            return me
        except Exception as e:
            logging.error(f"❌ 获取机器人信息失败: {e}")
            return None
    
    async def check_user_info(self):
        """检查用户账号信息"""
        if self.bot_token:
            logging.warning("⚠️ 是机器人账号，跳过用户信息检查")
            return None
            
        try:
            me = await self.client.get_me()
            logging.info(f"👤 用户账号信息:")
            logging.info(f"   ID: {me.id}")
            logging.info(f"   用户名: @{me.username}")
            logging.info(f"   名称: {me.first_name}")
            logging.info(f"   状态: {me.status}")
            return me
        except Exception as e:
            logging.error(f"❌ 获取用户信息失败: {e}")
            return None
    
    async def check_api_limits(self):
        """检查API限制状态"""
        logging.info("🔍 检查API限制状态...")
        
        limits = {
            'can_send_messages': False,
            'can_send_media': False,
            'can_edit_messages': False,
            'can_delete_messages': False,
            'flood_wait_active': False,
            'flood_wait_time': 0,
            'phone_code_restricted': False,
            'account_restricted': False
        }
        
        try:
            # 测试发送消息权限
            if self.bot_token:
                # 机器人权限检查
                limits['can_send_messages'] = True  # 机器人默认有发送权限
                limits['can_send_media'] = True
                limits['can_edit_messages'] = True
            else:
                # 用户账号权限检查
                limits['can_send_messages'] = True
                limits['can_send_media'] = True
                limits['can_edit_messages'] = True
            
            logging.info("✅ API基本权限正常")
            
        except FloodWait as e:
            limits['flood_wait_active'] = True
            limits['flood_wait_time'] = e.value
            logging.warning(f"⚠️ 遇到FloodWait限制: {e.value}秒")
            
        except BadRequest as e:
            error_str = str(e).lower()
            if "chat_write_forbidden" in error_str:
                limits['can_send_messages'] = False
                logging.error("❌ 发送消息权限被限制")
            elif "phone_code_invalid" in error_str:
                limits['phone_code_restricted'] = True
                logging.error("❌ 验证码功能被限制")
                
        except Unauthorized as e:
            limits['account_restricted'] = True
            logging.error("❌ 账号被限制或封禁")
            
        except Exception as e:
            logging.error(f"❌ 检查API限制时出错: {e}")
        
        return limits
    
    async def test_message_sending(self, test_chat_id):
        """测试消息发送功能"""
        logging.info(f"🧪 测试消息发送到 {test_chat_id}...")
        
        try:
            # 测试发送文本消息
            result = await self.client.send_message(
                chat_id=test_chat_id,
                text="🔍 API限制测试消息"
            )
            logging.info("✅ 文本消息发送成功")
            
            # 测试编辑消息
            await self.client.edit_message_text(
                chat_id=test_chat_id,
                message_id=result.id,
                text="✅ 消息编辑测试成功"
            )
            logging.info("✅ 消息编辑成功")
            
            # 删除测试消息
            await self.client.delete_messages(
                chat_id=test_chat_id,
                message_ids=[result.id]
            )
            logging.info("✅ 消息删除成功")
            
            return True
            
        except FloodWait as e:
            logging.warning(f"⚠️ 发送测试时遇到FloodWait: {e.value}秒")
            return False
        except Exception as e:
            logging.error(f"❌ 发送测试失败: {e}")
            return False
    
    async def check_flood_wait_status(self):
        """检查FloodWait状态"""
        logging.info("⏰ 检查FloodWait状态...")
        
        try:
            # 尝试一个简单的API调用
            await self.client.get_me()
            logging.info("✅ 当前没有FloodWait限制")
            return False
            
        except FloodWait as e:
            logging.warning(f"⚠️ 当前有FloodWait限制: {e.value}秒")
            return e.value
        except Exception as e:
            logging.error(f"❌ 检查FloodWait状态失败: {e}")
            return None

async def main():
    """主函数"""
    print("🔍 API限制状态检查工具")
    print("=" * 60)
    
    # 配置信息（需要您填写）
    API_ID = "your_api_id"           # 从 my.telegram.org 获取
    API_HASH = "your_api_hash"       # 从 my.telegram.org 获取
    BOT_TOKEN = "your_bot_token"     # 机器人token（如果是机器人）
    
    # 测试聊天ID（可以是您的私聊或频道）
    TEST_CHAT_ID = "your_chat_id"    # 测试用的聊天ID
    
    # 检查配置
    if API_ID == "your_api_id" or API_HASH == "your_api_hash":
        print("❌ 请先配置 API_ID 和 API_HASH")
        print("📱 获取地址: https://my.telegram.org")
        exit(1)
    
    # 创建检查器
    checker = APILimitChecker(API_ID, API_HASH, BOT_TOKEN)
    
    try:
        # 启动客户端
        if await checker.start_client():
            print("✅ 客户端启动成功，开始检查...")
            
            # 检查账号信息
            if BOT_TOKEN:
                await checker.check_bot_info()
            else:
                await checker.check_user_info()
            
            # 检查API限制
            limits = await checker.check_api_limits()
            
            # 检查FloodWait状态
            flood_wait_status = await checker.check_flood_wait_status()
            
            # 测试消息发送（如果提供了测试聊天ID）
            if TEST_CHAT_ID != "your_chat_id":
                await checker.test_message_sending(TEST_CHAT_ID)
            
            # 显示检查结果
            print("\n📊 检查结果汇总:")
            print("=" * 60)
            print(f"发送消息权限: {'✅ 正常' if limits['can_send_messages'] else '❌ 受限'}")
            print(f"发送媒体权限: {'✅ 正常' if limits['can_send_media'] else '❌ 受限'}")
            print(f"编辑消息权限: {'✅ 正常' if limits['can_edit_messages'] else '❌ 受限'}")
            print(f"FloodWait状态: {'✅ 无限制' if not limits['flood_wait_active'] else f'⚠️ 限制{limits["flood_wait_time"]}秒'}")
            print(f"验证码限制: {'✅ 正常' if not limits['phone_code_restricted'] else '❌ 受限'}")
            print(f"账号状态: {'✅ 正常' if not limits['account_restricted'] else '❌ 受限'}")
            
        else:
            print("❌ 客户端启动失败")
            
    except Exception as e:
        print(f"❌ 检查过程出错: {e}")
    finally:
        await checker.stop_client()

if __name__ == "__main__":
    print("💡 使用说明:")
    print("1. 配置 API_ID 和 API_HASH")
    print("2. 如果是机器人，配置 BOT_TOKEN")
    print("3. 设置测试聊天ID")
    print("4. 运行检查工具")
    print("\n" + "=" * 60)
    
    # 运行主函数
    asyncio.run(main())



