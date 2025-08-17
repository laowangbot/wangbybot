#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
权限检查和修复工具
"""

import json
import os

def check_permission_errors():
    """检查权限错误状态"""
    print("🔍 检查权限错误状态...")
    
    # 检查配置文件中的频道对
    config_file = "config_files/user_configs.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                configs = json.load(f)
            
            print(f"📁 发现配置文件: {config_file}")
            
            for user_id, config in configs.items():
                channel_pairs = config.get("channel_pairs", [])
                if channel_pairs:
                    print(f"\n👤 用户 {user_id}:")
                    for i, pair in enumerate(channel_pairs):
                        source = pair.get('source', '未知')
                        target = pair.get('target', '未知')
                        enabled = pair.get('enabled', True)
                        status = "✅ 启用" if enabled else "❌ 禁用"
                        print(f"   {i+1}. {source} -> {target} ({status})")
        except Exception as e:
            print(f"❌ 读取配置文件失败: {e}")
    else:
        print(f"📁 配置文件不存在: {config_file}")

def analyze_permission_issues():
    """分析权限问题"""
    print("\n🔍 分析权限问题...")
    
    print("🚨 常见权限问题:")
    print("1. 机器人被踢出频道")
    print("2. 机器人权限不足")
    print("3. 频道设置为私有")
    print("4. 频道管理员限制")
    
    print("\n💡 解决方案:")
    print("1. 重新邀请机器人到频道")
    print("2. 检查机器人权限设置")
    print("3. 确保机器人有发送消息权限")
    print("4. 联系频道管理员")

def create_permission_fix_script():
    """创建权限修复脚本"""
    print("\n🔧 创建权限修复脚本...")
    
    script_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
权限修复脚本
"""

async def fix_channel_permissions(client, target_channel):
    """修复频道权限问题"""
    try:
        # 检查机器人状态
        chat_member = await client.get_chat_member(chat_id=target_channel, user_id="me")
        
        if chat_member.status == 'left':
            print(f"❌ 机器人已离开频道 {target_channel}")
            return False
        elif chat_member.status == 'kicked':
            print(f"❌ 机器人被踢出频道 {target_channel}")
            return False
        elif chat_member.status == 'restricted':
            if not chat_member.can_post_messages:
                print(f"❌ 机器人在频道 {target_channel} 没有发送消息权限")
                return False
            else:
                print(f"✅ 机器人在频道 {target_channel} 权限正常")
                return True
        else:
            print(f"✅ 机器人在频道 {target_channel} 状态正常: {chat_member.status}")
            return True
            
    except Exception as e:
        print(f"❌ 检查频道权限失败: {e}")
        return False

async def check_all_channels(client, configs):
    """检查所有频道权限"""
    print("🔍 检查所有频道权限...")
    
    for user_id, config in configs.items():
        channel_pairs = config.get("channel_pairs", [])
        if channel_pairs:
            print(f"\\n👤 用户 {user_id}:")
            for i, pair in enumerate(channel_pairs):
                target = pair.get('target')
                if target:
                    print(f"  {i+1}. 检查频道 {target}")
                    await fix_channel_permissions(client, target)
'''
    
    with open("fix_permissions.py", "w", encoding="utf-8") as f:
        f.write(script_content)
    
    print("✅ 权限修复脚本已创建: fix_permissions.py")

def show_permission_guide():
    """显示权限修复指南"""
    print("\n📚 权限修复指南:")
    print("=" * 60)
    
    print("1. 🔑 重新邀请机器人")
    print("   - 在目标频道中发送 /start")
    print("   - 或者手动邀请机器人")
    
    print("\n2. ⚙️ 检查机器人权限")
    print("   - 确保机器人是频道成员")
    print("   - 检查是否有发送消息权限")
    print("   - 验证是否有媒体发送权限")
    
    print("\n3. 🚫 常见限制")
    print("   - 私有频道需要邀请链接")
    print("   - 某些频道禁止机器人")
    print("   - 管理员可能设置了限制")
    
    print("\n4. 🔧 技术解决方案")
    print("   - 使用权限检查脚本")
    print("   - 自动跳过权限不足的频道")
    print("   - 记录权限错误避免重复尝试")

if __name__ == "__main__":
    print("🔐 权限检查和修复工具")
    print("=" * 60)
    
    check_permission_errors()
    analyze_permission_issues()
    create_permission_fix_script()
    show_permission_guide()
    
    print("\n" + "=" * 60)
    print("💡 建议:")
    print("   1. 检查机器人是否仍在目标频道中")
    print("   2. 重新邀请机器人到频道")
    print("   3. 确保机器人有足够权限")
    print("   4. 使用权限修复脚本自动检查")







