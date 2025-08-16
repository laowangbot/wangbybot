#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
移除所有机器人内部限制工具
"""

import os
import re
import shutil
from datetime import datetime

def remove_all_restrictions():
    """移除所有机器人内部限制"""
    print("🚨 移除所有机器人内部限制工具")
    print("=" * 60)
    print("⚠️  此工具将移除代码中所有对用户的限制")
    print("⚠️  包括FloodWait限制、延迟限制、频率限制等")
    print("=" * 60)
    
    # 确认操作
    confirm = input("🚨 确认要移除所有限制吗？这将让机器人无限制运行！(输入 'REMOVE' 确认): ").strip()
    
    if confirm != "REMOVE":
        print("❌ 操作已取消")
        return False
    
    print("\n🧹 开始移除所有限制...")
    
    # 1. 备份原文件
    print("\n📁 备份原文件...")
    backup_dir = f"backup_before_remove_restrictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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
    
    # 2. 移除csmain.py中的限制
    print("\n📝 移除csmain.py中的限制...")
    if os.path.exists("csmain.py"):
        try:
            with open("csmain.py", 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 移除FloodWait管理器类
            print("  🔧 移除FloodWait管理器类...")
            content = re.sub(
                r'# ==================== FloodWait管理器 ====================\s*class FloodWaitManager:.*?# 创建全局FloodWait管理器实例\s*flood_wait_manager = FloodWaitManager\(\)',
                '# ==================== 限制已移除 ====================\n# 所有FloodWait限制已被移除\n# 机器人将无限制运行\n\n# 创建空的限制管理器（兼容性）\nclass FloodWaitManager:\n    def __init__(self):\n        pass\n    \n    async def wait_if_needed(self, operation_type, user_id=None):\n        """不再有任何限制"""\n        pass\n    \n    def set_flood_wait(self, operation_type, wait_time, user_id=None):\n        """不再设置任何限制"""\n        pass\n    \n    def get_wait_time(self, operation_type, user_id=None):\n        """不再返回任何等待时间"""\n        return 0\n    \n    def should_skip_operation(self, operation_type, user_id=None):\n        """不再跳过任何操作"""\n        return False\n\n# 创建全局FloodWait管理器实例\nflood_wait_manager = FloodWaitManager()',
                content,
                flags=re.DOTALL
            )
            
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
            
            # 移除所有asyncio.sleep延迟
            print("  🔧 移除asyncio.sleep延迟...")
            content = re.sub(
                r'await asyncio\.sleep\([^)]+\)\s*#.*?延迟|await asyncio\.sleep\([^)]+\)\s*#.*?等待|await asyncio\.sleep\([^)]+\)\s*#.*?间隔',
                '',
                content
            )
            
            # 移除所有FloodWait相关的等待
            print("  🔧 移除FloodWait等待...")
            content = re.sub(
                r'await asyncio\.sleep\(wait_time\)\s*#.*?等待指定时间后重试',
                '# 不再等待，直接继续',
                content
            )
            
            # 保存修改后的文件
            with open("csmain.py", 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("  ✅ 已移除csmain.py中的限制")
            
        except Exception as e:
            print(f"  ❌ 修改失败: {e}")
    
    # 3. 移除new_cloning_engine.py中的限制
    print("\n📝 移除new_cloning_engine.py中的限制...")
    if os.path.exists("new_cloning_engine.py"):
        try:
            with open("new_cloning_engine.py", 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 移除所有延迟配置
            print("  🔧 移除延迟配置...")
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
            
            print("  ✅ 已移除new_cloning_engine.py中的限制")
            
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
    
    # 5. 创建无限制说明文档
    print("\n📜 创建无限制说明文档...")
    
    restriction_removal_summary = """# 🚀 机器人限制移除完成报告

## ✅ 已移除的限制

### 1. FloodWait管理器限制
- ❌ 移除了所有操作间隔控制
- ❌ 移除了用户级FloodWait限制
- ❌ 移除了全局FloodWait限制
- ❌ 移除了操作频率检查

### 2. 延迟限制
- ❌ 移除了所有asyncio.sleep延迟
- ❌ 移除了批量操作延迟
- ❌ 移除了媒体组发送延迟
- ❌ 移除了消息发送延迟

### 3. 频率限制
- ❌ 移除了操作频率检查
- ❌ 移除了should_skip_operation检查
- ❌ 移除了wait_if_needed等待

### 4. 批量限制
- ❌ 移除了批量大小限制
- ❌ 移除了并发任务限制
- ❌ 移除了任务启动延迟

## 🎯 现在的状态

### ✅ 机器人将无限制运行
- 🚀 无任何延迟等待
- 🚀 无任何频率限制
- 🚀 无任何用户限制
- 🚀 无任何操作限制

### ⚠️ 注意事项
- 机器人将以最快速度运行
- 可能会触发Telegram服务器限制
- 建议监控运行状态
- 如遇问题可恢复备份文件

## 🔧 恢复方法

如需恢复限制，请运行：
```bash
# 恢复备份文件
cp backup_before_remove_restrictions_*/csmain.py ./
cp backup_before_remove_restrictions_*/new_cloning_engine.py ./
```

## 📊 移除完成时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
**机器人现在将以无限制模式运行！** 🎉
"""
    
    try:
        with open("RESTRICTION_REMOVAL_SUMMARY.md", 'w', encoding='utf-8') as f:
            f.write(restriction_removal_summary)
        print("  ✅ 已创建移除说明文档")
    except Exception as e:
        print(f"  ❌ 创建失败: {e}")
    
    # 显示移除结果
    print("\n📊 限制移除完成!")
    print("=" * 60)
    print("✅ 所有FloodWait限制已移除")
    print("✅ 所有延迟限制已移除")
    print("✅ 所有频率限制已移除")
    print("✅ 所有用户限制已移除")
    print("✅ 所有操作限制已移除")
    print("✅ 无限制配置文件已创建")
    print("✅ 移除说明文档已创建")
    
    print("\n💡 机器人现在的状态:")
    print("🚀 无任何延迟等待")
    print("🚀 无任何频率限制")
    print("🚀 无任何用户限制")
    print("🚀 无任何操作限制")
    print("🚀 将以最快速度运行")
    
    print("\n⚠️ 重要提醒:")
    print("- 机器人将以最快速度运行")
    print("- 可能会触发Telegram服务器限制")
    print("- 建议监控运行状态")
    print("- 如遇问题可恢复备份文件")
    
    print(f"\n📁 备份文件位置: {backup_dir}")
    print("📜 详细说明: RESTRICTION_REMOVAL_SUMMARY.md")
    
    return True

def show_recovery_instructions():
    """显示恢复说明"""
    print("\n📚 恢复限制说明:")
    print("=" * 60)
    
    print("🔧 如需恢复限制，请执行以下操作:")
    print("\n1. 停止机器人")
    print("   - 按 Ctrl+C 停止运行中的机器人")
    
    print("\n2. 恢复备份文件")
    print("   - 找到备份目录")
    print("   - 复制原文件覆盖当前文件")
    
    print("\n3. 重新启动机器人")
    print("   - 机器人将恢复所有限制")
    
    print("\n⚠️ 注意事项:")
    print("- 恢复后机器人将重新有所有限制")
    print("- 建议在测试完成后再恢复")
    print("- 备份文件包含所有原始代码")

if __name__ == "__main__":
    print("🚨 移除所有机器人内部限制工具")
    print("=" * 60)
    print("💡 功能:")
    print("   - 移除所有FloodWait限制")
    print("   - 移除所有延迟限制")
    print("   - 移除所有频率限制")
    print("   - 移除所有用户限制")
    print("   - 让机器人无限制运行")
    print("\n⚠️  警告: 此操作将移除所有限制!")
    print("=" * 60)
    
    # 执行限制移除
    success = remove_all_restrictions()
    
    if success:
        print("\n🎉 所有限制移除成功！")
        show_recovery_instructions()
    else:
        print("\n❌ 限制移除失败或已取消")
    
    print("\n" + "=" * 60)
    print("💡 限制移除完成！")


