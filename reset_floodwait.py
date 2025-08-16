#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FloodWait重置脚本
"""

import json
import os

def reset_floodwait():
    """重置所有FloodWait限制"""
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
    """清理数据中的FloodWait相关信息"""
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

if __name__ == "__main__":
    reset_floodwait()
