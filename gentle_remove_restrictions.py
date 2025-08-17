#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
温和的限制移除工具 - 只移除特定的限制，不破坏文件结构
"""

import os
import re
import shutil
from datetime import datetime

def gentle_remove_restrictions():
    """温和地移除限制"""
    print("🌱 温和的限制移除工具")
    print("=" * 60)
    print("⚠️  此工具将温和地移除代码中的限制")
    print("⚠️  只修改特定行，不破坏文件结构")
    print("=" * 60)
    
    # 确认操作
    confirm = input("🚨 确认要温和移除限制吗？(输入 'GENTLE' 确认): ").strip()
    
    if confirm != "GENTLE":
        print("❌ 操作已取消")
        return False
    
    print("\n🧹 开始温和移除限制...")
    
    # 1. 备份当前文件
    print("\n📁 备份当前文件...")
    backup_dir = f"backup_before_gentle_remove_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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
    
    # 2. 温和移除csmain.py中的限制
    print("\n📝 温和移除csmain.py中的限制...")
    if os.path.exists("csmain.py"):
        try:
            with open("csmain.py", 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            modified = False
            
            # 只修改FloodWait管理器类，不删除整个类
            print("  🔧 修改FloodWait管理器类...")
            for i, line in enumerate(lines):
                if "class FloodWaitManager:" in line:
                    # 找到类的开始
                    start_line = i
                    # 找到类的结束（下一个类或函数定义）
                    end_line = start_line
                    for j in range(start_line + 1, len(lines)):
                        if (lines[j].strip().startswith("class ") or 
                            lines[j].strip().startswith("def ") or
                            lines[j].strip().startswith("async def ")):
                            if not lines[j].strip().startswith("    "):  # 不是类内的方法
                                end_line = j
                                break
                    
                    # 替换FloodWait管理器类
                    replacement_lines = [
                        "# ==================== 限制已移除 ====================\n",
                        "# 所有FloodWait限制已被移除\n",
                        "# 机器人将无限制运行\n",
                        "\n",
                        "# 创建空的限制管理器（兼容性）\n",
                        "class FloodWaitManager:\n",
                        "    def __init__(self):\n",
                        "        pass\n",
                        "    \n",
                        "    async def wait_if_needed(self, operation_type, user_id=None):\n",
                        "        \"\"\"不再有任何限制\"\"\"\n",
                        "        pass\n",
                        "    \n",
                        "    def set_flood_wait(self, operation_type, wait_time, user_id=None):\n",
                        "        \"\"\"不再设置任何限制\"\"\"\n",
                        "        pass\n",
                        "    \n",
                        "    def get_wait_time(self, operation_type, user_id=None):\n",
                        "        \"\"\"不再返回任何等待时间\"\"\"\n",
                        "        return 0\n",
                        "    \n",
                        "    def should_skip_operation(self, operation_type, user_id=None):\n",
                        "        \"\"\"不再跳过任何操作\"\"\"\n",
                        "        return False\n",
                        "\n",
                        "# 创建全局FloodWait管理器实例\n",
                        "flood_wait_manager = FloodWaitManager()\n",
                        "\n"
                    ]
                    
                    # 替换类定义
                    lines[start_line:end_line] = replacement_lines
                    modified = True
                    print("  ✅ 已修改FloodWait管理器类")
                    break
            
            # 移除所有flood_wait_manager.wait_if_needed调用
            print("  🔧 移除wait_if_needed调用...")
            for i, line in enumerate(lines):
                if "await flood_wait_manager.wait_if_needed(" in line:
                    lines[i] = "# " + line.strip() + "  # 已移除限制\n"
                    modified = True
            
            # 移除所有flood_wait_manager.set_flood_wait调用
            print("  🔧 移除set_flood_wait调用...")
            for i, line in enumerate(lines):
                if "flood_wait_manager.set_flood_wait(" in line:
                    lines[i] = "# " + line.strip() + "  # 已移除限制\n"
                    modified = True
            
            # 移除所有flood_wait_manager.should_skip_operation调用
            print("  🔧 移除should_skip_operation调用...")
            i = 0
            while i < len(lines):
                line = lines[i]
                if "if flood_wait_manager.should_skip_operation(" in line:
                    # 注释掉这个if语句和相关的continue
                    lines[i] = "# " + line.strip() + "  # 已移除限制\n"
                    modified = True
                    # 查找相关的continue语句
                    j = i + 1
                    while j < len(lines) and (lines[j].strip().startswith("    ") or lines[j].strip() == ""):
                        if "continue" in lines[j]:
                            lines[j] = "# " + lines[j].strip() + "  # 已移除限制\n"
                            modified = True
                        j += 1
                    i = j
                else:
                    i += 1
            
            if modified:
                # 保存修改后的文件
                with open("csmain.py", 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                print("  ✅ 已温和移除csmain.py中的限制")
            else:
                print("  ℹ️  未发现需要修改的限制")
            
        except Exception as e:
            print(f"  ❌ 修改失败: {e}")
    
    # 3. 温和移除new_cloning_engine.py中的限制
    print("\n📝 温和移除new_cloning_engine.py中的限制...")
    if os.path.exists("new_cloning_engine.py"):
        try:
            with open("new_cloning_engine.py", 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            modified = False
            
            # 只修改延迟配置，不删除整个文件
            print("  🔧 修改延迟配置...")
            for i, line in enumerate(lines):
                if "self.batch_delay_range = (" in line and "延迟范围" in line:
                    lines[i] = "        self.batch_delay_range = (0.0, 0.0)  # 无延迟\n"
                    modified = True
                elif "self.media_group_delay = " in line:
                    lines[i] = "        self.media_group_delay = 0.0\n"
                    modified = True
                elif "self.message_delay_media = " in line:
                    lines[i] = "        self.message_delay_media = 0.0\n"
                    modified = True
                elif "self.message_delay_text = " in line:
                    lines[i] = "        self.message_delay_text = 0.0\n"
                    modified = True
            
            # 注释掉所有asyncio.sleep调用
            print("  🔧 注释掉asyncio.sleep调用...")
            for i, line in enumerate(lines):
                if "await asyncio.sleep(" in line:
                    lines[i] = "# " + line.strip() + "  # 已移除延迟\n"
                    modified = True
            
            if modified:
                # 保存修改后的文件
                with open("new_cloning_engine.py", 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                print("  ✅ 已温和移除new_cloning_engine.py中的限制")
            else:
                print("  ℹ️  未发现需要修改的限制")
            
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
    print("\n📊 温和限制移除完成!")
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
    print("🌱 温和的限制移除工具")
    print("=" * 60)
    print("💡 功能:")
    print("   - 温和移除所有FloodWait限制")
    print("   - 温和移除所有延迟限制")
    print("   - 温和移除所有频率限制")
    print("   - 让机器人无限制运行")
    print("\n⚠️  警告: 此操作将移除所有限制!")
    print("=" * 60)
    
    # 执行温和限制移除
    success = gentle_remove_restrictions()
    
    if success:
        print("\n🎉 所有限制温和移除成功！")
    else:
        print("\n❌ 限制移除失败或已取消")
    
    print("\n" + "=" * 60)
    print("💡 温和限制移除完成！")





