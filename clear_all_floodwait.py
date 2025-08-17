#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清除所有用户FloodWait限制工具
"""

import json
import os
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)

def clear_all_floodwait_limits():
    """清除所有用户的FloodWait限制"""
    print("🧹 清除所有用户FloodWait限制工具")
    print("=" * 60)
    
    # 需要清理的文件列表
    files_to_clear = [
        "config_files/running_tasks.json",
        "rate_limit_config.json",
        "performance_stats.json",
        "performance_metrics_20250814.json",
        "performance_optimization.json"
    ]
    
    # 需要清理的目录
    dirs_to_clear = [
        "logs",
        "temp_files"
    ]
    
    cleared_count = 0
    total_files = 0
    
    print("📋 开始清理FloodWait相关文件...")
    
    # 清理指定文件
    for file_path in files_to_clear:
        if os.path.exists(file_path):
            try:
                # 备份原文件
                backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"  📁 已备份: {backup_path}")
                
                # 清理文件内容
                if file_path.endswith('.json'):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        # 清理FloodWait相关数据
                        cleared = clear_floodwait_from_json(data, file_path)
                        if cleared:
                            cleared_count += 1
                            print(f"  ✅ 已清理: {file_path}")
                        else:
                            print(f"  ℹ️  无需清理: {file_path}")
                        
                        # 保存清理后的数据
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                            
                    except json.JSONDecodeError:
                        print(f"  ⚠️  JSON格式错误，跳过: {file_path}")
                else:
                    # 非JSON文件，清空内容
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("")
                    cleared_count += 1
                    print(f"  ✅ 已清空: {file_path}")
                
                total_files += 1
                
            except Exception as e:
                print(f"  ❌ 清理失败: {file_path} - {e}")
        else:
            print(f"  ℹ️  文件不存在: {file_path}")
    
    # 清理日志目录
    print("\n📁 清理日志目录...")
    for dir_path in dirs_to_clear:
        if os.path.exists(dir_path):
            try:
                # 列出目录中的文件
                files = os.listdir(dir_path)
                log_files = [f for f in files if f.endswith('.log') or 'floodwait' in f.lower()]
                
                if log_files:
                    for log_file in log_files:
                        file_path = os.path.join(dir_path, log_file)
                        try:
                            # 备份日志文件
                            backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                            
                            with open(backup_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            
                            # 清空日志文件
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write("")
                            
                            cleared_count += 1
                            print(f"  ✅ 已清理日志: {file_path}")
                            
                        except Exception as e:
                            print(f"  ❌ 清理日志失败: {file_path} - {e}")
                else:
                    print(f"  ℹ️  目录中无日志文件: {dir_path}")
                    
            except Exception as e:
                print(f"  ❌ 访问目录失败: {dir_path} - {e}")
    
    # 清理内存中的FloodWait数据
    print("\n🧠 清理内存中的FloodWait数据...")
    
    # 检查是否有flood_wait_manager相关的全局变量
    try:
        # 尝试导入并清理flood_wait_manager
        import sys
        if 'flood_wait_manager' in sys.modules:
            flood_wait_manager = sys.modules['flood_wait_manager']
            if hasattr(flood_wait_manager, 'flood_wait_times'):
                flood_wait_manager.flood_wait_times.clear()
                print("  ✅ 已清理flood_wait_manager中的等待时间")
            if hasattr(flood_wait_manager, 'user_flood_wait_times'):
                flood_wait_manager.user_flood_wait_times.clear()
                print("  ✅ 已清理flood_wait_manager中的用户等待时间")
    except Exception as e:
        print(f"  ℹ️  无法清理内存中的flood_wait_manager: {e}")
    
    # 显示清理结果
    print("\n📊 清理结果汇总:")
    print("=" * 60)
    print(f"✅ 成功清理文件: {cleared_count} 个")
    print(f"📁 处理文件总数: {total_files} 个")
    print(f"🧹 清理完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if cleared_count > 0:
        print("\n🎉 FloodWait限制清理完成！")
        print("💡 建议:")
        print("   - 重启机器人以确保所有限制被清除")
        print("   - 检查机器人是否恢复正常运行")
        print("   - 监控是否还有新的FloodWait限制")
    else:
        print("\nℹ️ 没有找到需要清理的FloodWait数据")
    
    return cleared_count > 0

def clear_floodwait_from_json(data, file_path):
    """从JSON数据中清理FloodWait相关信息"""
    cleared = False
    
    if isinstance(data, dict):
        # 清理字典中的FloodWait数据
        keys_to_remove = []
        for key, value in data.items():
            if isinstance(value, dict):
                # 递归清理嵌套字典
                if clear_floodwait_from_dict(value):
                    cleared = True
            elif isinstance(value, list):
                # 清理列表中的FloodWait数据
                if clear_floodwait_from_list(value):
                    cleared = True
            elif is_floodwait_key(key):
                # 直接删除FloodWait相关的键
                keys_to_remove.append(key)
                cleared = True
        
        # 删除标记的键
        for key in keys_to_remove:
            del data[key]
            
    elif isinstance(data, list):
        # 清理列表中的FloodWait数据
        if clear_floodwait_from_list(data):
            cleared = True
    
    return cleared

def clear_floodwait_from_dict(data_dict):
    """清理字典中的FloodWait数据"""
    cleared = False
    keys_to_remove = []
    
    for key, value in data_dict.items():
        if isinstance(value, dict):
            if clear_floodwait_from_dict(value):
                cleared = True
        elif isinstance(value, list):
            if clear_floodwait_from_list(value):
                cleared = True
        elif is_floodwait_key(key):
            keys_to_remove.append(key)
            cleared = True
    
    # 删除标记的键
    for key in keys_to_remove:
        del data_dict[key]
    
    return cleared

def clear_floodwait_from_list(data_list):
    """清理列表中的FloodWait数据"""
    cleared = False
    
    for i, item in enumerate(data_list):
        if isinstance(item, dict):
            if clear_floodwait_from_dict(item):
                cleared = True
        elif isinstance(item, list):
            if clear_floodwait_from_list(item):
                cleared = True
    
    return cleared

def is_floodwait_key(key):
    """判断是否为FloodWait相关的键"""
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

def show_manual_cleanup_instructions():
    """显示手动清理说明"""
    print("\n📚 手动清理FloodWait限制说明:")
    print("=" * 60)
    
    print("🔧 如果自动清理不完整，可以手动执行以下操作:")
    print("\n1. 停止机器人")
    print("   - 按 Ctrl+C 停止运行中的机器人")
    print("   - 确保所有Python进程都已终止")
    
    print("\n2. 删除会话文件")
    print("   - 删除 *.session 文件")
    print("   - 删除 *.session-journal 文件")
    
    print("\n3. 清理配置文件")
    print("   - 备份 config_files/user_configs.json")
    print("   - 删除或清空 rate_limit_config.json")
    print("   - 清理 performance_*.json 文件")
    
    print("\n4. 重启机器人")
    print("   - 重新运行 start_bot.py")
    print("   - 机器人将重新建立连接")
    
    print("\n⚠️ 注意事项:")
    print("   - 清理后机器人需要重新登录")
    print("   - 所有运行中的任务将被中断")
    print("   - 建议在机器人空闲时执行清理")

if __name__ == "__main__":
    print("🚀 FloodWait限制清理工具")
    print("=" * 60)
    print("💡 功能:")
    print("   - 清除所有用户的FloodWait等待时间")
    print("   - 清理相关配置文件和日志")
    print("   - 重置机器人API限制状态")
    print("\n" + "=" * 60)
    
    # 确认操作
    confirm = input("⚠️ 此操作将清除所有FloodWait限制，是否继续？(y/N): ").strip().lower()
    
    if confirm in ['y', 'yes', '是']:
        # 执行清理
        success = clear_all_floodwait_limits()
        
        if success:
            print("\n✅ 清理完成！")
        else:
            print("\n❌ 清理失败或无需清理")
        
        # 显示手动清理说明
        show_manual_cleanup_instructions()
    else:
        print("\n❌ 操作已取消")
    
    print("\n" + "=" * 60)
    print("💡 清理完成！")






