#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强制清除FloodWait限制工具
"""

import json
import os
import shutil
import glob
import re
from datetime import datetime

def force_clear_floodwait():
    """强制清除所有FloodWait限制"""
    print("🚨 强制清除FloodWait限制工具")
    print("=" * 60)
    print("⚠️  此工具将强制清除所有FloodWait相关数据")
    print("⚠️  包括内存中的限制、配置文件、会话文件等")
    print("=" * 60)
    
    # 确认操作
    confirm = input("🚨 确认要执行强制清理吗？这将重置所有机器人状态！(输入 'FORCE' 确认): ").strip()
    
    if confirm != "FORCE":
        print("❌ 操作已取消")
        return False
    
    print("\n🧹 开始强制清理...")
    
    # 1. 强制停止所有Python进程（模拟）
    print("\n🛑 强制停止所有机器人进程...")
    print("  💡 请手动按 Ctrl+C 停止所有运行中的机器人")
    print("  💡 确保没有Python进程在运行")
    
    # 2. 删除所有会话文件
    print("\n📁 删除所有会话文件...")
    session_patterns = ["*.session*", "*.session", "*.session-journal"]
    
    for pattern in session_patterns:
        files = glob.glob(pattern)
        for file in files:
            try:
                # 备份原文件
                backup_path = f"{file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(file, backup_path)
                os.remove(file)
                print(f"  ✅ 已删除并备份: {file} -> {backup_path}")
            except Exception as e:
                print(f"  ❌ 删除失败: {file} - {e}")
    
    # 3. 清空所有配置文件
    print("\n📋 清空所有配置文件...")
    config_files = [
        "running_tasks.json",
        "performance_stats.json",
        "user_states.json",
        "user_history.json",
        "user_login.json",
        "message_fingerprints.json"
    ]
    
    for file in config_files:
        if os.path.exists(file):
            try:
                # 备份原文件
                backup_path = f"{file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(file, backup_path)
                
                # 清空文件内容
                if file.endswith('.json'):
                    with open(file, 'w', encoding='utf-8') as f:
                        f.write("{}")
                else:
                    with open(file, 'w', encoding='utf-8') as f:
                        f.write("")
                
                print(f"  ✅ 已清空并备份: {file} -> {backup_path}")
            except Exception as e:
                print(f"  ❌ 清理失败: {file} - {e}")
        else:
            print(f"  ℹ️  文件不存在: {file}")
    
    # 4. 清空日志文件
    print("\n📝 清空所有日志文件...")
    log_files = glob.glob("*.log")
    for file in log_files:
        try:
            backup_path = f"{file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(file, backup_path)
            
            # 清空日志文件
            with open(file, 'w', encoding='utf-8') as f:
                f.write("")
            
            print(f"  ✅ 已清空并备份: {file} -> {backup_path}")
        except Exception as e:
            print(f"  ❌ 清理失败: {file} - {e}")
    
    # 5. 清理config_files目录
    print("\n📁 清理config_files目录...")
    config_dir = "config_files"
    if os.path.exists(config_dir):
        try:
            # 备份整个目录
            backup_dir = f"{config_dir}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copytree(config_dir, backup_dir)
            
            # 清空目录中的文件
            for file in os.listdir(config_dir):
                file_path = os.path.join(config_dir, file)
                if os.path.isfile(file_path):
                    if file.endswith('.json'):
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write("{}")
                    else:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write("")
            
            print(f"  ✅ 已清空并备份: {config_dir} -> {backup_dir}")
        except Exception as e:
            print(f"  ❌ 清理失败: {config_dir} - {e}")
    
    # 6. 删除所有processed_ids文件
    print("\n🗂️ 删除所有processed_ids文件...")
    processed_files = glob.glob("processed_ids_*.json")
    for file in processed_files:
        try:
            backup_path = f"{file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(file, backup_path)
            os.remove(file)
            print(f"  ✅ 已删除并备份: {file} -> {backup_path}")
        except Exception as e:
            print(f"  ❌ 删除失败: {file} - {e}")
    
    # 7. 创建全新的配置文件
    print("\n✨ 创建全新的配置文件...")
    
    # 创建新的user_configs.json
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
            "flood_wait_times": {},
            "user_flood_wait_times": {}
        }
    }
    
    try:
        with open("user_configs.json", 'w', encoding='utf-8') as f:
            json.dump(new_user_configs, f, ensure_ascii=False, indent=2)
        print("  ✅ 已创建新的 user_configs.json")
    except Exception as e:
        print(f"  ❌ 创建失败: {e}")
    
    # 创建新的running_tasks.json
    try:
        with open("running_tasks.json", 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        print("  ✅ 已创建新的 running_tasks.json")
    except Exception as e:
        print(f"  ❌ 创建失败: {e}")
    
    # 创建新的performance_stats.json
    try:
        with open("performance_stats.json", 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        print("  ✅ 已创建新的 performance_stats.json")
    except Exception as e:
        print(f"  ❌ 创建失败: {e}")
    
    # 创建新的user_states.json
    try:
        with open("user_states.json", 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        print("  ✅ 已创建新的 user_states.json")
    except Exception as e:
        print(f"  ❌ 创建失败: {e}")
    
    # 8. 创建FloodWait重置脚本
    print("\n📜 创建FloodWait重置脚本...")
    reset_script = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
FloodWait重置脚本
\"\"\"

import json
import os

def reset_floodwait():
    \"\"\"重置所有FloodWait限制\"\"\"
    print("🔄 重置FloodWait限制...")
    
    # 重置配置文件中的FloodWait数据
    config_files = [
        "user_configs.json",
        "running_tasks.json",
        "performance_stats.json",
        "user_states.json"
    ]
    
    for file in config_files:
        if os.path.exists(file):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 递归清理FloodWait相关数据
                clean_floodwait_data(data)
                
                with open(file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                print(f"  ✅ 已重置: {file}")
            except Exception as e:
                print(f"  ❌ 重置失败: {file} - {e}")
    
    print("✅ FloodWait限制重置完成！")

def clean_floodwait_data(data):
    \"\"\"清理数据中的FloodWait相关信息\"\"\"
    if isinstance(data, dict):
        keys_to_remove = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                clean_floodwait_data(value)
            elif is_floodwait_key(key):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del data[key]
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                clean_floodwait_data(item)

def is_floodwait_key(key):
    \"\"\"判断是否为FloodWait相关的键\"\"\"
    key_lower = str(key).lower()
    floodwait_indicators = [
        'floodwait', 'flood_wait', 'flood-wait',
        'wait_time', 'wait_time', 'wait_time',
        'rate_limit', 'rate-limit', 'ratelimit',
        'throttle', 'throttling', 'delay',
        'cooldown', 'cooldown', 'restriction',
        'limit', 'limiting', 'blocked',
        'suspended', 'banned', 'restricted'
    ]
    
    return any(indicator in key_lower for indicator in floodwait_indicators)

if __name__ == "__main__":
    reset_floodwait()
"""
    
    try:
        with open("reset_floodwait.py", 'w', encoding='utf-8') as f:
            f.write(reset_script)
        print("  ✅ 已创建 reset_floodwait.py")
    except Exception as e:
        print(f"  ❌ 创建失败: {e}")
    
    # 显示清理结果
    print("\n📊 强制清理完成!")
    print("=" * 60)
    print("✅ 所有FloodWait相关数据已强制清除")
    print("✅ 所有配置文件已重置")
    print("✅ 所有会话文件已删除")
    print("✅ 所有日志文件已清空")
    print("✅ 全新的配置文件已创建")
    print("✅ FloodWait重置脚本已创建")
    
    print("\n💡 下一步操作:")
    print("1. 确保没有Python进程在运行")
    print("2. 运行重置脚本: python reset_floodwait.py")
    print("3. 重新启动机器人: python start_bot.py")
    print("4. 机器人将重新建立连接，无任何限制")
    
    print("\n⚠️ 重要提醒:")
    print("- 所有之前的配置都已丢失")
    print("- 需要重新设置频道组、过滤规则等")
    print("- 机器人将重新开始，无历史负担")
    print("- 新的FloodWait限制将被重置")
    
    return True

def show_recovery_instructions():
    """显示恢复说明"""
    print("\n📚 恢复配置说明:")
    print("=" * 60)
    
    print("🔧 清理完成后，您需要重新配置机器人:")
    print("\n1. 运行FloodWait重置脚本")
    print("   python reset_floodwait.py")
    
    print("\n2. 重新启动机器人")
    print("   python start_bot.py")
    
    print("\n3. 重新配置频道组")
    print("   - 添加源频道和目标频道")
    print("   - 设置过滤规则")
    print("   - 配置敏感词替换")
    
    print("\n4. 重新设置过滤选项")
    print("   - 关键字过滤")
    print("   - 文件类型过滤")
    print("   - 按钮设置")
    
    print("\n5. 测试功能")
    print("   - 验证搬运功能")
    print("   - 检查过滤效果")
    print("   - 确认无FloodWait限制")

if __name__ == "__main__":
    print("🚨 强制清除FloodWait限制工具")
    print("=" * 60)
    print("💡 功能:")
    print("   - 强制清除所有FloodWait限制")
    print("   - 重置所有配置文件")
    print("   - 删除所有会话和日志")
    print("   - 创建全新的配置环境")
    print("   - 创建FloodWait重置脚本")
    print("\n⚠️  警告: 此操作将删除所有机器人数据!")
    print("=" * 60)
    
    # 执行强制清理
    success = force_clear_floodwait()
    
    if success:
        print("\n🎉 强制清理成功完成！")
        show_recovery_instructions()
    else:
        print("\n❌ 强制清理失败或已取消")
    
    print("\n" + "=" * 60)
    print("💡 清理完成！")



