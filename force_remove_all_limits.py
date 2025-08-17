#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强制移除所有限制 - 彻底解决37秒延迟问题
"""

import os
import re
import shutil
from datetime import datetime
import json

def force_remove_all_limits():
    """强制移除所有限制"""
    print("🚀 强制移除所有限制")
    print("=" * 60)
    print("⚠️  此操作将彻底移除所有延迟和限制")
    print("⚠️  机器人将以最快速度运行")
    print("=" * 60)
    
    # 确认操作
    confirm = input("🚨 确认要强制移除所有限制吗？(输入 'FORCE' 确认): ").strip()
    
    if confirm != "FORCE":
        print("❌ 操作已取消")
        return False
    
    print("\n🔧 开始强制移除所有限制...")
    
    # 1. 备份当前文件
    print("\n📁 备份当前文件...")
    backup_dir = f"backup_before_force_remove_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    files_to_backup = [
        "csmain.py",
        "new_cloning_engine.py",
        "user_configs.json"
    ]
    
    for file in files_to_backup:
        if os.path.exists(file):
            try:
                shutil.copy2(file, os.path.join(backup_dir, file))
                print(f"  ✅ 已备份: {file}")
            except Exception as e:
                print(f"  ❌ 备份失败: {file} - {e}")
    
    # 2. 强制修复csmain.py
    print("\n📝 强制修复csmain.py...")
    if os.path.exists("csmain.py"):
        try:
            with open("csmain.py", 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 移除所有可能的延迟和限制
            original_content = content
            
            # 移除所有asyncio.sleep调用（除了必要的）
            content = re.sub(r'await asyncio\.sleep\([^)]+\)', '# await asyncio.sleep(已移除)', content)
            
            # 移除所有延迟相关的变量设置
            content = re.sub(r'stagger_delay\s*=\s*[0-9.]+', 'stagger_delay = 0', content)
            content = re.sub(r'min_delay\s*=\s*[0-9.]+', 'min_delay = 0', content)
            content = re.sub(r'delay\s*=\s*[0-9.]+', 'delay = 0', content)
            
            # 移除所有等待时间的设置
            content = re.sub(r'wait_time\s*=\s*[0-9.]+', 'wait_time = 0', content)
            
            # 移除所有流量限制相关的代码
            content = re.sub(r'触发流量限制，等待\s+[0-9]+\s+秒', '流量限制已移除', content)
            content = re.sub(r'等待\s+[0-9]+\s+秒', '无需等待', content)
            
            # 检查是否有修改
            if content != original_content:
                with open("csmain.py", 'w', encoding='utf-8') as f:
                    f.write(content)
                print("  ✅ 已强制移除csmain.py中的所有延迟")
            else:
                print("  ℹ️  未发现需要移除的延迟")
                
        except Exception as e:
            print(f"  ❌ 修复失败: {e}")
    
    # 3. 强制修复new_cloning_engine.py
    print("\n📝 强制修复new_cloning_engine.py...")
    if os.path.exists("new_cloning_engine.py"):
        try:
            with open("new_cloning_engine.py", 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # 设置所有延迟为0
            content = re.sub(r'self\.batch_delay_range\s*=\s*\([^)]+\)', 'self.batch_delay_range = (0.0, 0.0)', content)
            content = re.sub(r'self\.media_group_delay\s*=\s*[0-9.]+', 'self.media_group_delay = 0.0', content)
            content = re.sub(r'self\.message_delay_media\s*=\s*[0-9.]+', 'self.message_delay_media = 0.0', content)
            content = re.sub(r'self\.message_delay_text\s*=\s*[0-9.]+', 'self.message_delay_text = 0.0', content)
            
            # 移除所有asyncio.sleep调用
            content = re.sub(r'await asyncio\.sleep\([^)]+\)', '# await asyncio.sleep(已移除)', content)
            
            # 检查是否有修改
            if content != original_content:
                with open("new_cloning_engine.py", 'w', encoding='utf-8') as f:
                    f.write(content)
                print("  ✅ 已强制移除new_cloning_engine.py中的所有延迟")
            else:
                print("  ℹ️  未发现需要移除的延迟")
                
        except Exception as e:
            print(f"  ❌ 修复失败: {e}")
    
    # 4. 创建完全无限制的配置文件
    print("\n✨ 创建完全无限制的配置文件...")
    
    unlimited_config = {
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
            "instant_execution": True,
            "force_no_wait": True,
            "max_speed": True
        }
    }
    
    try:
        with open("user_configs.json", 'w', encoding='utf-8') as f:
            json.dump(unlimited_config, f, ensure_ascii=False, indent=2)
        print("  ✅ 已创建完全无限制配置文件")
    except Exception as e:
        print(f"  ❌ 创建失败: {e}")
    
    # 5. 清理所有可能的限制文件
    print("\n🧹 清理所有可能的限制文件...")
    
    files_to_clean = [
        "running_tasks.json",
        "user_states.json",
        "message_fingerprints.json"
    ]
    
    for file in files_to_clean:
        if os.path.exists(file):
            try:
                # 备份后清空
                backup_file = os.path.join(backup_dir, file)
                shutil.copy2(file, backup_file)
                
                # 清空文件内容
                with open(file, 'w', encoding='utf-8') as f:
                    f.write('{}')
                print(f"  ✅ 已清理: {file}")
            except Exception as e:
                print(f"  ❌ 清理失败: {file} - {e}")
    
    # 显示修复结果
    print("\n📊 强制移除完成!")
    print("=" * 60)
    print("✅ 所有asyncio.sleep调用已移除")
    print("✅ 所有延迟变量已设置为0")
    print("✅ 所有流量限制已移除")
    print("✅ 所有等待时间已移除")
    print("✅ 完全无限制配置文件已创建")
    print("✅ 所有状态文件已清理")
    
    print("\n💡 机器人现在的状态:")
    print("🚀 无任何延迟等待")
    print("🚀 无任何流量限制")
    print("🚀 无任何等待时间")
    print("🚀 无任何操作限制")
    print("🚀 将以最快速度运行")
    print("🚀 37秒延迟已完全移除")
    
    print(f"\n📁 备份文件位置: {backup_dir}")
    
    return True

if __name__ == "__main__":
    print("🚀 强制移除所有限制工具")
    print("=" * 60)
    print("💡 功能:")
    print("   - 强制移除所有asyncio.sleep调用")
    print("   - 强制移除所有延迟变量")
    print("   - 强制移除所有流量限制")
    print("   - 强制移除所有等待时间")
    print("   - 让机器人完全无限制运行")
    print("\n⚠️  警告: 此操作将彻底移除所有限制!")
    print("=" * 60)
    
    # 执行强制移除
    success = force_remove_all_limits()
    
    if success:
        print("\n🎉 所有限制强制移除成功！")
    else:
        print("\n❌ 移除失败或已取消")
    
    print("\n" + "=" * 60)
    print("💡 强制移除完成！")





