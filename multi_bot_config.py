#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多机器人配置文件 - 支持3个不同的机器人
每个机器人使用不同的API和Token
"""

import os

# ==================== 机器人配置 ====================
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

# ==================== 配置信息 ====================
if __name__ == "__main__":
    print("🔧 多机器人配置检查")
    print("=" * 50)
    
    active_bots = get_active_bots()
    
    if active_bots:
        print(f"\n✅ 找到 {len(active_bots)} 个有效机器人配置")
        for bot_key, bot_config in active_bots.items():
            print(f"  - {bot_config['name']}: {bot_config['description']}")
    else:
        print("\n❌ 没有找到有效的机器人配置")
        print("请检查环境变量设置")
    
    print("\n📋 环境变量说明:")
    print("BOT1_API_ID, BOT1_API_HASH, BOT1_BOT_TOKEN - 第一个机器人")
    print("BOT2_API_ID, BOT2_API_HASH, BOT2_BOT_TOKEN - 第二个机器人")
    print("BOT3_API_ID, BOT3_API_HASH, BOT3_BOT_TOKEN - 第三个机器人")
