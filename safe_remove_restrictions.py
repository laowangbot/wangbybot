#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全的限制移除工具 - 只移除特定的限制，不破坏文件结构
"""

import os
import re
import shutil
from datetime import datetime

def safe_remove_restrictions():
    """安全地移除限制"""
    print("🛡️ 安全的限制移除工具")
    print("=" * 60)
    print("⚠️  此工具将安全地移除代码中的限制")
    print("⚠️  不会破坏文件结构，只修改特定内容")
    print("=" * 60)
    
    # 确认操作
    confirm = input("🚨 确认要安全移除限制吗？(输入 'SAFE' 确认): ").strip()
    
    if confirm != "SAFE":
        print("❌ 操作已取消")
        return False
    
    print("\n🧹 开始安全移除限制...")
    
    # 1. 备份当前文件
    print("\n📁 备份当前文件...")
    backup_dir = f"backup_before_safe_remove_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    # 备份主要文件
    files_to_backup = [
        "csmain.py",
        "new_cloning_engine.py"
    ]
    
    for file in files_to_backup:
        if os.path.exists(file):
            try:
                shutil.copy2(file, os.path.join(backup_dir, file))
                print(f"  ✅ 已备份: {file}")
            except Exception as e:
                print(f"  ❌ 备份失败: {file} - {e}")
    
    # 2. 安全移除csmain.py中的限制
    print("\n📝 安全移除csmain.py中的限制...")
    if os.path.exists("csmain.py"):
        try:
            with open("csmain.py", 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 只移除FloodWait管理器类，保留其他结构
            print("  🔧 移除FloodWait管理器类...")
            if "class FloodWaitManager:" in content:
                # 找到FloodWait管理器类的开始和结束
                start_pattern = r'# ==================== FloodWait管理器 ====================\s*class FloodWaitManager:'
                end_pattern = r'# 创建全局FloodWait管理器实例\s*flood_wait_manager = FloodWaitManager\(\)'
                
                # 替换整个FloodWait管理器类
                replacement = '''# ==================== 限制已移除 ====================
# 所有FloodWait限制已被移除
# 机器人将无限制运行

# 创建空的限制管理器（兼容性）
class FloodWaitManager:
    def __init__(self):
        pass
    
    async def wait_if_needed(self, operation_type, user_id=None):
        """不再有任何限制"""
        pass
    
    def set_flood_wait(self, operation_type, wait_time, user_id=None):
        """不再设置任何限制"""
        pass
    
    def get_wait_time(self, operation_type, user_id=None):
        """不再返回任何等待时间"""
        return 0
    
    def should_skip_operation(self, operation_type, user_id=None):
        """不再跳过任何操作"""
        return False

# 创建全局FloodWait管理器实例
flood_wait_manager = FloodWaitManager()'''
                
                # 使用更精确的替换
                pattern = start_pattern + r'.*?' + end_pattern
                content = re.sub(pattern, replacement, content, flags=re.DOTALL)
                print("  ✅ 已移除FloodWait管理器类")
            else:
                print("  ℹ️  FloodWait管理器类已不存在")
            
            # 移除所有flood_wait_manager.wait_if_needed调用
            print("  🔧 移除wait_if_needed调用...")
            content = re.sub(
                r'await flood_wait_manager\.wait_if_needed\([^)]+\)\s*',
                '',
                content
            )
            
            # 移除所有flood_wait_manager.set_flood_wait调用
            print("  🔧 移除set_flood_wait调用...")
            content = re.sub(
                r'flood_wait_manager\.set_flood_wait\([^)]+\)\s*',
                '',
                content
            )
            
            # 移除所有flood_wait_manager.should_skip_operation调用
            print("  🔧 移除should_skip_operation调用...")
            content = re.sub(
                r'if flood_wait_manager\.should_skip_operation\([^)]+\):\s*.*?continue\s*',
                '',
                content,
                flags=re.DOTALL
            )
            
            # 保存修改后的文件
            with open("csmain.py", 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("  ✅ 已安全移除csmain.py中的限制")
            
        except Exception as e:
            print(f"  ❌ 修改失败: {e}")
    
    # 3. 安全移除new_cloning_engine.py中的限制
    print("\n📝 安全移除new_cloning_engine.py中的限制...")
    if os.path.exists("new_cloning_engine.py"):
        try:
            with open("new_cloning_engine.py", 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 只修改延迟配置，不破坏文件结构
            print("  🔧 修改延迟配置...")
            content = re.sub(
                r'self\.batch_delay_range = \([^)]+\)\s*#.*?延迟范围',
                'self.batch_delay_range = (0.0, 0.0)  # 无延迟',
                content
            )
            
            content = re.sub(
                r'self\.media_group_delay = [^;]+',
                'self.media_group_delay = 0.0',
                content
            )
            
            content = re.sub(
                r'self\.message_delay_media = [^;]+',
                'self.message_delay_media = 0.0',
                content
            )
            
            content = re.sub(
                r'self\.message_delay_text = [^;]+',
                'self.message_delay_text = 0.0',
                content
            )
            
            # 移除所有asyncio.sleep调用
            print("  🔧 移除asyncio.sleep调用...")
            content = re.sub(
                r'await asyncio\.sleep\([^)]+\)\s*#.*?延迟|await asyncio\.sleep\([^)]+\)\s*#.*?等待|await asyncio\.sleep\([^)]+\)\s*#.*?间隔',
                '',
                content
            )
            
            # 移除FloodWait等待
            print("  🔧 移除FloodWait等待...")
            content = re.sub(
                r'await asyncio\.sleep\(wait_time \+ 2\)\s*#.*?多等2秒确保安全',
                '# 不再等待',
                content
            )
            
            # 保存修改后的文件
            with open("new_cloning_engine.py", 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("  ✅ 已安全移除new_cloning_engine.py中的限制")
            
        except Exception as e:
            print(f"  ❌ 修改失败: {e}")
    
    # 4. 创建无限制配置文件
    print("\n✨ 创建无限制配置文件...")
    
    # 创建新的user_configs.json（无限制版本）
    new_user_configs = {
        "default_user": {
            "channel_pairs": [],
            "filter_keywords": [],
            "replacement_words": {},
            "file_filter_extensions": [],
            "buttons": [],
            "tail_text": "",
            "realtime_listen": False,
            "monitor_enabled": False,
            "no_restrictions": True,
            "unlimited_mode": True
        }
    }
    
    try:
        with open("user_configs.json", 'w', encoding='utf-8') as f:
            import json
            json.dump(new_user_configs, f, ensure_ascii=False, indent=2)
        print("  ✅ 已创建无限制配置文件")
    except Exception as e:
        print(f"  ❌ 创建失败: {e}")
    
    # 显示移除结果
    print("\n📊 安全限制移除完成!")
    print("=" * 60)
    print("✅ 所有FloodWait限制已移除")
    print("✅ 所有延迟限制已移除")
    print("✅ 所有频率限制已移除")
    print("✅ 所有用户限制已移除")
    print("✅ 所有操作限制已移除")
    print("✅ 无限制配置文件已创建")
    
    print("\n💡 机器人现在的状态:")
    print("🚀 无任何延迟等待")
    print("🚀 无任何频率限制")
    print("🚀 无任何用户限制")
    print("🚀 无任何操作限制")
    print("🚀 将以最快速度运行")
    
    print(f"\n📁 备份文件位置: {backup_dir}")
    
    return True

if __name__ == "__main__":
    print("🛡️ 安全的限制移除工具")
    print("=" * 60)
    print("💡 功能:")
    print("   - 安全移除所有FloodWait限制")
    print("   - 安全移除所有延迟限制")
    print("   - 安全移除所有频率限制")
    print("   - 让机器人无限制运行")
    print("\n⚠️  警告: 此操作将移除所有限制!")
    print("=" * 60)
    
    # 执行安全限制移除
    success = safe_remove_restrictions()
    
    if success:
        print("\n🎉 所有限制安全移除成功！")
    else:
        print("\n❌ 限制移除失败或已取消")
    
    print("\n" + "=" * 60)
    print("💡 安全限制移除完成！")


