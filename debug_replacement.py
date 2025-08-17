#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试敏感词替换保存问题
"""

import json
import os

def simulate_add_replacement():
    """模拟添加敏感词替换的完整流程"""
    print("🧪 模拟添加敏感词替换流程...")
    
    # 模拟当前的用户配置
    user_configs = {
        "994678447": {
            "replacement_words": {}
        }
    }
    
    print(f"📋 初始配置: {json.dumps(user_configs, ensure_ascii=False, indent=2)}")
    
    try:
        # 模拟 add_replacement 函数的逻辑
        user_id = "994678447"
        replacements_text = "敏感词1->替换词1,敏感词2->替换词2"
        
        print(f"📝 输入文本: {replacements_text}")
        
        # 解析替换规则
        replacement_dict = {}
        items = replacements_text.split(',')
        for item in items:
            if '->' in item:
                old, new = item.split('->', 1)
                replacement_dict[old.strip()] = new.strip()
        
        print(f"🔍 解析结果: {replacement_dict}")
        
        # 更新配置
        config = user_configs.setdefault(user_id, {})
        current_replacements = config.setdefault("replacement_words", {})
        current_replacements.update(replacement_dict)
        
        print(f"📋 更新后配置: {json.dumps(user_configs, ensure_ascii=False, indent=2)}")
        
        # 模拟保存
        with open("debug_user_configs.json", "w", encoding='utf-8') as f:
            json.dump(user_configs, f, ensure_ascii=False, indent=4)
        print("✅ 配置保存成功")
        
        # 验证保存结果
        with open("debug_user_configs.json", "r", encoding='utf-8') as f:
            saved_configs = json.load(f)
        print(f"📋 保存后读取: {json.dumps(saved_configs, ensure_ascii=False, indent=2)}")
        
        # 清理测试文件
        os.remove("debug_user_configs.json")
        print("✅ 测试文件清理完成")
        
    except Exception as e:
        print(f"❌ 模拟失败: {e}")
        import traceback
        traceback.print_exc()

def check_file_permissions():
    """检查文件权限"""
    print("\n🔐 检查文件权限...")
    
    try:
        # 尝试写入测试文件
        test_content = {"test": "data"}
        with open("test_permissions.json", "w", encoding='utf-8') as f:
            json.dump(test_content, f, ensure_ascii=False, indent=2)
        print("✅ 文件写入权限正常")
        
        # 尝试读取测试文件
        with open("test_permissions.json", "r", encoding='utf-8') as f:
            loaded_content = json.load(f)
        print("✅ 文件读取权限正常")
        
        # 尝试修改测试文件
        with open("test_permissions.json", "w", encoding='utf-8') as f:
            json.dump({"test": "modified"}, f, ensure_ascii=False, indent=2)
        print("✅ 文件修改权限正常")
        
        # 清理测试文件
        os.remove("test_permissions.json")
        print("✅ 文件删除权限正常")
        
    except Exception as e:
        print(f"❌ 权限检查失败: {e}")

def check_current_config_integrity():
    """检查当前配置文件的完整性"""
    print("\n🔍 检查当前配置文件完整性...")
    
    try:
        if os.path.exists("user_configs.json"):
            file_size = os.path.getsize("user_configs.json")
            print(f"📁 配置文件大小: {file_size} 字节")
            
            if file_size == 0:
                print("❌ 配置文件为空")
                return
            
            with open("user_configs.json", "r", encoding='utf-8') as f:
                content = f.read()
                print(f"📄 文件内容长度: {len(content)} 字符")
                print(f"📄 文件内容: {repr(content)}")
                
                if content.strip():
                    configs = json.loads(content)
                    print(f"✅ JSON 解析成功，包含 {len(configs)} 个用户")
                    
                    for user_id, config in configs.items():
                        print(f"   用户 {user_id}:")
                        for key, value in config.items():
                            print(f"     {key}: {type(value)} = {value}")
                else:
                    print("❌ 文件内容为空字符串")
        else:
            print("❌ 配置文件不存在")
            
    except Exception as e:
        print(f"❌ 完整性检查失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simulate_add_replacement()
    check_file_permissions()
    check_current_config_integrity()







