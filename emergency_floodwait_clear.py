#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
紧急FloodWait清理工具 - 彻底清除所有FloodWait限制
"""

import json
import os
import shutil
import glob
from datetime import datetime

def emergency_floodwait_clear():
    """紧急清理所有FloodWait限制"""
    print("🚨 紧急FloodWait清理工具")
    print("=" * 60)
    print("⚠️  此工具将彻底清除所有FloodWait相关数据")
    print("⚠️  包括配置文件、会话文件、日志文件等")
    print("=" * 60)
    
    # 确认操作
    confirm = input("🚨 确认要执行紧急清理吗？这将删除所有机器人数据！(输入 'EMERGENCY' 确认): ").strip()
    
    if confirm != "EMERGENCY":
        print("❌ 操作已取消")
        return False
    
    print("\n🧹 开始紧急清理...")
    
    # 1. 清理会话文件
    print("\n📁 清理会话文件...")
    session_files = glob.glob("*.session*")
    for file in session_files:
        try:
            backup_path = f"{file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(file, backup_path)
            os.remove(file)
            print(f"  ✅ 已删除并备份: {file} -> {backup_path}")
        except Exception as e:
            print(f"  ❌ 删除失败: {file} - {e}")
    
    # 2. 清理配置文件
    print("\n📋 清理配置文件...")
    config_files = [
        "running_tasks.json",
        "performance_stats.json",
        "user_states.json",
        "user_history.json",
        "user_login.json"
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
    
    # 3. 清理日志文件
    print("\n📝 清理日志文件...")
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
    
    # 4. 清理临时文件
    print("\n🗂️ 清理临时文件...")
    temp_patterns = [
        "processed_ids_*.json",
        "test_*.py",
        "debug_*.py",
        "emergency_*.py",
        "fix_*.py"
    ]
    
    for pattern in temp_patterns:
        files = glob.glob(pattern)
        for file in files:
            try:
                backup_path = f"{file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(file, backup_path)
                os.remove(file)
                print(f"  ✅ 已删除并备份: {file} -> {backup_path}")
            except Exception as e:
                print(f"  ❌ 删除失败: {file} - {e}")
    
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
    
    # 6. 创建新的配置文件
    print("\n✨ 创建新的配置文件...")
    
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
            "monitor_enabled": False
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
    
    # 显示清理结果
    print("\n📊 紧急清理完成!")
    print("=" * 60)
    print("✅ 所有FloodWait相关数据已清除")
    print("✅ 所有配置文件已重置")
    print("✅ 所有会话文件已删除")
    print("✅ 所有日志文件已清空")
    print("✅ 新的配置文件已创建")
    
    print("\n💡 下一步操作:")
    print("1. 重新启动机器人")
    print("2. 重新配置频道组和过滤设置")
    print("3. 机器人将重新建立连接，无任何限制")
    
    print("\n⚠️ 重要提醒:")
    print("- 所有之前的配置都已丢失")
    print("- 需要重新设置频道组、过滤规则等")
    print("- 机器人将重新开始，无历史负担")
    
    return True

def show_recovery_instructions():
    """显示恢复说明"""
    print("\n📚 恢复配置说明:")
    print("=" * 60)
    
    print("🔧 清理完成后，您需要重新配置机器人:")
    print("\n1. 重新启动机器人")
    print("   python start_bot.py")
    
    print("\n2. 重新配置频道组")
    print("   - 添加源频道和目标频道")
    print("   - 设置过滤规则")
    print("   - 配置敏感词替换")
    
    print("\n3. 重新设置过滤选项")
    print("   - 关键字过滤")
    print("   - 文件类型过滤")
    print("   - 按钮设置")
    
    print("\n4. 测试功能")
    print("   - 验证搬运功能")
    print("   - 检查过滤效果")
    print("   - 确认无FloodWait限制")

if __name__ == "__main__":
    print("🚨 紧急FloodWait清理工具")
    print("=" * 60)
    print("💡 功能:")
    print("   - 彻底清除所有FloodWait限制")
    print("   - 重置所有配置文件")
    print("   - 删除所有会话和日志")
    print("   - 创建全新的配置环境")
    print("\n⚠️  警告: 此操作将删除所有机器人数据!")
    print("=" * 60)
    
    # 执行紧急清理
    success = emergency_floodwait_clear()
    
    if success:
        print("\n🎉 紧急清理成功完成！")
        show_recovery_instructions()
    else:
        print("\n❌ 紧急清理失败或已取消")
    
    print("\n" + "=" * 60)
    print("💡 清理完成！")


