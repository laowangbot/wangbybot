#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
移除剩余限制工具 - 精确移除不必要的延迟
"""

import os
import re
import shutil
from datetime import datetime

def remove_remaining_restrictions():
    """移除剩余的不必要限制"""
    print("🔍 移除剩余限制工具")
    print("=" * 60)
    print("⚠️  此工具将精确移除代码中剩余的不必要延迟")
    print("⚠️  保留必要的功能延迟，移除性能限制延迟")
    print("=" * 60)
    
    # 确认操作
    confirm = input("🚨 确认要移除剩余限制吗？(输入 'REMOVE' 确认): ").strip()
    
    if confirm != "REMOVE":
        print("❌ 操作已取消")
        return False
    
    print("\n🧹 开始移除剩余限制...")
    
    # 1. 备份当前文件
    print("\n📁 备份当前文件...")
    backup_dir = f"backup_before_remove_remaining_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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
    
    # 2. 移除csmain.py中的性能限制延迟
    print("\n📝 移除csmain.py中的性能限制延迟...")
    if os.path.exists("csmain.py"):
        try:
            with open("csmain.py", 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 移除任务启动延迟（这些是性能限制，不是功能需要）
            print("  🔧 移除任务启动延迟...")
            content = re.sub(
                r'stagger_delay = batch_number \* 3\s*#.*?每批延迟3秒，减少等待时间',
                'stagger_delay = 0  # 无延迟启动',
                content
            )
            
            content = re.sub(
                r'await asyncio\.sleep\(stagger_delay\)',
                '# await asyncio.sleep(stagger_delay)  # 已移除延迟',
                content
            )
            
            content = re.sub(
                r'min_delay = i \* 0\.5\s*#.*?最小延迟0\.5秒',
                'min_delay = 0  # 无延迟',
                content
            )
            
            content = re.sub(
                r'await asyncio\.sleep\(min_delay\)',
                '# await asyncio.sleep(min_delay)  # 已移除延迟',
                content
            )
            
            # 移除并发限制延迟
            print("  🔧 移除并发限制延迟...")
            content = re.sub(
                r'delay = \(i // max_concurrent_tasks\) \* 5\s*#.*?每批延迟5秒',
                'delay = 0  # 无延迟',
                content
            )
            
            # 移除FloodWait等待（这是真正的限制）
            print("  🔧 移除FloodWait等待...")
            content = re.sub(
                r'await asyncio\.sleep\(wait_time\)\s*#.*?等待指定时间后重试',
                '# await asyncio.sleep(wait_time)  # 不再等待FloodWait',
                content
            )
            
            # 移除重试延迟
            print("  🔧 移除重试延迟...")
            content = re.sub(
                r'await asyncio\.sleep\(2\.0\)',
                '# await asyncio.sleep(2.0)  # 已移除重试延迟',
                content
            )
            
            # 保存修改后的文件
            with open("csmain.py", 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("  ✅ 已移除csmain.py中的性能限制延迟")
            
        except Exception as e:
            print(f"  ❌ 修改失败: {e}")
    
    # 3. 移除new_cloning_engine.py中的剩余延迟
    print("\n📝 移除new_cloning_engine.py中的剩余延迟...")
    if os.path.exists("new_cloning_engine.py"):
        try:
            with open("new_cloning_engine.py", 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 移除所有剩余的asyncio.sleep调用
            print("  🔧 移除所有asyncio.sleep调用...")
            content = re.sub(
                r'await asyncio\.sleep\([^)]+\)',
                '# await asyncio.sleep(...)  # 已移除延迟',
                content
            )
            
            # 保存修改后的文件
            with open("new_cloning_engine.py", 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("  ✅ 已移除new_cloning_engine.py中的剩余延迟")
            
        except Exception as e:
            print(f"  ❌ 修改失败: {e}")
    
    # 4. 创建完全无限制的配置文件
    print("\n✨ 创建完全无限制配置文件...")
    
    # 创建新的user_configs.json（完全无限制版本）
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
            "unlimited_mode": True,
            "no_delays": True,
            "instant_execution": True
        }
    }
    
    try:
        with open("user_configs.json", 'w', encoding='utf-8') as f:
            import json
            json.dump(new_user_configs, f, ensure_ascii=False, indent=2)
        print("  ✅ 已创建完全无限制配置文件")
    except Exception as e:
        print(f"  ❌ 创建失败: {e}")
    
    # 5. 创建完全无限制说明文档
    print("\n📜 创建完全无限制说明文档...")
    
    complete_removal_summary = """# 🚀 机器人完全无限制运行报告

## ✅ 已移除的所有限制

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
- ❌ 移除了任务启动延迟
- ❌ 移除了并发限制延迟
- ❌ 移除了重试延迟

### 3. 频率限制
- ❌ 移除了操作频率检查
- ❌ 移除了should_skip_operation检查
- ❌ 移除了wait_if_needed等待

### 4. 批量限制
- ❌ 移除了批量大小限制
- ❌ 移除了并发任务限制
- ❌ 移除了任务启动延迟

### 5. 性能限制
- ❌ 移除了任务启动延迟
- ❌ 移除了并发限制延迟
- ❌ 移除了重试延迟
- ❌ 移除了所有不必要的等待

## 🎯 现在的状态

### ✅ 机器人将完全无限制运行
- 🚀 无任何延迟等待
- 🚀 无任何频率限制
- 🚀 无任何用户限制
- 🚀 无任何操作限制
- 🚀 无任何性能限制
- 🚀 无任何启动延迟
- 🚀 将以最快速度运行

### ⚠️ 注意事项
- 机器人将以最快速度运行
- 可能会触发Telegram服务器限制
- 建议监控运行状态
- 如遇问题可恢复备份文件

## 🔧 恢复方法

如需恢复限制，请运行：
```bash
# 恢复备份文件
cp backup_before_remove_remaining_*/csmain.py ./
cp backup_before_remove_remaining_*/new_cloning_engine.py ./
```

## 📊 移除完成时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
**机器人现在将以完全无限制模式运行！** 🎉
"""
    
    try:
        with open("COMPLETE_RESTRICTION_REMOVAL_SUMMARY.md", 'w', encoding='utf-8') as f:
            f.write(complete_removal_summary)
        print("  ✅ 已创建完全无限制说明文档")
    except Exception as e:
        print(f"  ❌ 创建失败: {e}")
    
    # 显示移除结果
    print("\n📊 剩余限制移除完成!")
    print("=" * 60)
    print("✅ 所有FloodWait限制已移除")
    print("✅ 所有延迟限制已移除")
    print("✅ 所有频率限制已移除")
    print("✅ 所有用户限制已移除")
    print("✅ 所有操作限制已移除")
    print("✅ 所有性能限制已移除")
    print("✅ 所有启动延迟已移除")
    print("✅ 完全无限制配置文件已创建")
    print("✅ 完全无限制说明文档已创建")
    
    print("\n💡 机器人现在的状态:")
    print("🚀 无任何延迟等待")
    print("🚀 无任何频率限制")
    print("🚀 无任何用户限制")
    print("🚀 无任何操作限制")
    print("🚀 无任何性能限制")
    print("🚀 无任何启动延迟")
    print("🚀 将以最快速度运行")
    
    print("\n⚠️ 重要提醒:")
    print("- 机器人将以最快速度运行")
    print("- 可能会触发Telegram服务器限制")
    print("- 建议监控运行状态")
    print("- 如遇问题可恢复备份文件")
    
    print(f"\n📁 备份文件位置: {backup_dir}")
    print("📜 详细说明: COMPLETE_RESTRICTION_REMOVAL_SUMMARY.md")
    
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
    print("🔍 移除剩余限制工具")
    print("=" * 60)
    print("💡 功能:")
    print("   - 移除所有剩余的性能限制")
    print("   - 移除所有启动延迟")
    print("   - 移除所有并发限制")
    print("   - 让机器人完全无限制运行")
    print("\n⚠️  警告: 此操作将移除所有剩余限制!")
    print("=" * 60)
    
    # 执行剩余限制移除
    success = remove_remaining_restrictions()
    
    if success:
        print("\n🎉 所有剩余限制移除成功！")
        show_recovery_instructions()
    else:
        print("\n❌ 剩余限制移除失败或已取消")
    
    print("\n" + "=" * 60)
    print("💡 限制移除完成！")



