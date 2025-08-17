#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存存储集成脚本
将内存存储管理器集成到csmain.py中，解决Render持久化问题
"""

import os
import re
import shutil
from datetime import datetime

def backup_original_file():
    """备份原始文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"csmain.py.memory_storage_backup_{timestamp}"
    
    if os.path.exists("csmain.py"):
        shutil.copy2("csmain.py", backup_name)
        print(f"✅ 原始文件已备份为: {backup_name}")
        return backup_name
    else:
        print("❌ 找不到csmain.py文件")
        return None

def integrate_memory_storage():
    """集成内存存储管理器到csmain.py"""
    
    # 备份原始文件
    backup_file = backup_original_file()
    if not backup_file:
        return False
    
    try:
        # 读取原始文件
        with open("csmain.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 1. 添加导入语句
        import_statement = '''
# 导入内存存储管理器
try:
    from memory_storage_manager import MemoryStorageManager
    MEMORY_STORAGE_AVAILABLE = True
    logging.info("内存存储管理器已加载")
except ImportError as e:
    MEMORY_STORAGE_AVAILABLE = False
    logging.warning(f"内存存储管理器加载失败: {e}")
'''
        
        # 在导入部分添加
        if "from new_cloning_engine import" in content:
            content = content.replace(
                "from new_cloning_engine import RobustCloningEngine, MessageDeduplicator",
                "from new_cloning_engine import RobustCloningEngine, MessageDeduplicator" + import_statement
            )
        else:
            # 如果找不到特定位置，在文件开头添加
            content = import_statement + "\n" + content
        
        # 2. 添加内存存储管理器实例
        storage_instance = '''
# 创建内存存储管理器实例
memory_storage = None
if MEMORY_STORAGE_AVAILABLE:
    try:
        memory_storage = MemoryStorageManager(bot_config['bot_id'], backup_interval=300)
        logging.info(f"[{bot_config['bot_id']}] 内存存储管理器已初始化")
    except Exception as e:
        logging.error(f"[{bot_config['bot_id']}] 内存存储管理器初始化失败: {e}")
        memory_storage = None
'''
        
        # 在全局变量定义后添加
        if "flood_wait_manager = FloodWaitManager()" in content:
            content = content.replace(
                "flood_wait_manager = FloodWaitManager()",
                "flood_wait_manager = FloodWaitManager()" + storage_instance
            )
        
        # 3. 修改save_configs函数
        save_configs_replacement = '''def save_configs():
    """将用户配置保存到文件"""
    global user_configs
    
    # 优先使用内存存储
    if memory_storage:
        try:
            memory_storage.set_config("user_configs", user_configs)
            logging.info(f"[{bot_config['bot_id']}] 用户配置已保存到内存存储")
            return
        except Exception as e:
            logging.error(f"[{bot_config['bot_id']}] 内存存储保存失败: {e}")
    
    # 回退到文件存储
    config_file = get_config_path(f"user_configs_{bot_config['bot_id']}.json")
    try:
        with open(config_file, "w", encoding='utf-8') as f:
            json.dump(user_configs, f, ensure_ascii=False, indent=4)
        logging.info(f"[{bot_config['bot_id']}] 用户配置已保存到文件 {config_file}")
    except Exception as e:
        logging.error(f"[{bot_config['bot_id']}] 保存用户配置失败: {e}")
        # 尝试保存到当前目录作为备份
        backup_file = f"user_configs_{bot_config['bot_id']}.json"
        try:
            with open(backup_file, "w", encoding='utf-8') as f:
                json.dump(user_configs, f, ensure_ascii=False, indent=4)
            logging.info(f"[{bot_config['bot_id']}] 用户配置已保存到备份文件 {backup_file}")
        except Exception as backup_e:
            logging.error(f"[{bot_config['bot_id']}] 保存备份文件也失败: {backup_e}")'''
        
        # 替换save_configs函数
        old_save_configs_pattern = r'def save_configs\(\):\s*"""[^"]*"""\s*config_file = get_config_path\(f"user_configs_{bot_config\[\'bot_id\'\]}\.json"\)[^}]+}'
        if re.search(old_save_configs_pattern, content, re.DOTALL):
            content = re.sub(old_save_configs_pattern, save_configs_replacement, content, flags=re.DOTALL)
        
        # 4. 修改load_configs函数
        load_configs_replacement = '''def load_configs():
    """从文件载入用户配置"""
    global user_configs
    
    # 优先从内存存储恢复
    if memory_storage:
        try:
            restored = memory_storage.restore_from_backup("user_configs")
            if restored:
                user_configs = memory_storage.get_config("user_configs")
                logging.info(f"[{bot_config['bot_id']}] 用户配置已从内存存储恢复")
                return
        except Exception as e:
            logging.error(f"[{bot_config['bot_id']}] 内存存储恢复失败: {e}")
    
    # 回退到文件加载
    config_file = get_config_path(f"user_configs_{bot_config['bot_id']}.json")
    backup_file = f"user_configs_{bot_config['bot_id']}.json"
    
    # 首先尝试从持久化存储加载
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding='utf-8') as f:
                user_configs = json.load(f)
            logging.info(f"[{bot_config['bot_id']}] 用户配置已从持久化存储 {config_file} 载入")
            return
        except Exception as e:
            logging.error(f"[{bot_config['bot_id']}] 从持久化存储加载配置失败: {e}")
    
    # 如果持久化存储失败，尝试从备份文件加载
    if os.path.exists(backup_file):
        try:
            with open(backup_file, "r", encoding='utf-8') as f:
                user_configs = json.load(f)
            logging.info(f"[{bot_config['bot_id']}] 用户配置已从备份文件 {backup_file} 载入")
            # 尝试保存到持久化存储
            try:
                save_configs()
                logging.info(f"[{bot_config['bot_id']}] 配置已迁移到持久化存储")
            except Exception as migrate_e:
                logging.error(f"[{bot_config['bot_id']}] 迁移到持久化存储失败: {migrate_e}")
            return
        except Exception as e:
            logging.error(f"[{bot_config['bot_id']}] 从备份文件加载配置失败: {e}")
    
    # 如果都失败，创建新配置
    logging.info(f"[{bot_config['bot_id']}] 配置文件不存在，将创建新配置")
    user_configs = {}'''
        
        # 替换load_configs函数
        old_load_configs_pattern = r'def load_configs\(\):\s*"""[^"]*"""\s*global user_configs[^}]+}'
        if re.search(old_load_configs_pattern, content, re.DOTALL):
            content = re.sub(old_load_configs_pattern, load_configs_replacement, content, flags=re.DOTALL)
        
        # 5. 添加新的管理命令
        new_commands = '''
@app.on_message(filters.command("backup") & filters.private)
async def backup_command(client, message):
    """手动备份配置"""
    user_id = message.from_user.id
    if not is_user_logged_in(user_id):
        await message.reply("请先登录后再使用此命令。")
        return
    
    if not is_admin_user(user_id):
        await message.reply("❌ 您没有管理员权限")
        return
    
    if memory_storage:
        try:
            memory_storage.force_backup_all()
            await message.reply("✅ 配置备份已完成！")
        except Exception as e:
            await message.reply(f"❌ 备份失败: {str(e)}")
    else:
        await message.reply("❌ 内存存储管理器未启用")

@app.on_message(filters.command("restore") & filters.private)
async def restore_command(client, message):
    """从备份恢复配置"""
    user_id = message.from_user.id
    if not is_user_logged_in(user_id):
        await message.reply("请先登录后再使用此命令。")
        return
    
    if not is_admin_user(user_id):
        await message.reply("❌ 您没有管理员权限")
        return
    
    if memory_storage:
        try:
            restored_count = memory_storage.restore_all_from_backup()
            await message.reply(f"✅ 配置恢复完成！成功恢复 {restored_count}/5 个配置")
        except Exception as e:
            await message.reply(f"❌ 恢复失败: {str(e)}")
    else:
        await message.reply("❌ 内存存储管理器未启用")

@app.on_message(filters.command("storage") & filters.private)
async def storage_status_command(client, message):
    """查看存储状态"""
    user_id = message.from_user.id
    if not is_user_logged_in(user_id):
        await message.reply("请先登录后再使用此命令。")
        return
    
    if not is_admin_user(user_id):
        await message.reply("❌ 您没有管理员权限")
        return
    
    if memory_storage:
        try:
            status = memory_storage.get_backup_status()
            status_text = "🔍 **存储状态检查**\\n\\n"
            status_text += f"📱 **内存存储**: {'✅ 已启用' if status['github_backup_enabled'] else '❌ 未启用'}\\n"
            status_text += f"⏰ **备份间隔**: {status['backup_interval']}秒\\n\\n"
            status_text += "📊 **备份状态**:\\n"
            
            for config_type, last_time in status['last_backup'].items():
                status_text += f"• {config_type}: {last_time}\\n"
            
            await message.reply(status_text)
        except Exception as e:
            await message.reply(f"❌ 获取状态失败: {str(e)}")
    else:
        await message.reply("❌ 内存存储管理器未启用")
'''
        
        # 在命令定义部分添加新命令
        if "@app.on_message(filters.command(\"configstatus\")" in content:
            content = content.replace(
                "@app.on_message(filters.command(\"configstatus\")",
                new_commands + "\n@app.on_message(filters.command(\"configstatus\")"
            )
        
        # 6. 修改其他save函数调用
        # 为所有save函数添加内存存储支持
        save_functions = [
            "save_user_states", "save_history", "save_login_data", "save_running_tasks"
        ]
        
        for func_name in save_functions:
            # 查找函数定义
            func_pattern = rf'def {func_name}\(\):\s*"""[^"]*"""\s*[^}]+}'
            if re.search(func_pattern, content, re.DOTALL):
                # 在函数开头添加内存存储检查
                memory_check = f'''
    # 优先使用内存存储
    if memory_storage:
        try:
            memory_storage.set_config("{func_name.replace('save_', '')}", {func_name.replace('save_', '')})
            logging.info(f"[{{bot_config['bot_id']}}] {func_name.replace('save_', '')} 已保存到内存存储")
            return
        except Exception as e:
            logging.error(f"[{{bot_config['bot_id']}}] 内存存储保存失败: {{e}}")
    
    # 回退到文件存储'''
                
                # 在函数开头添加
                content = content.replace(
                    f'def {func_name}():',
                    f'def {func_name}():{memory_check}'
                )
        
        # 7. 修改其他load函数调用
        load_functions = [
            "load_user_states", "load_history", "load_login_data"
        ]
        
        for func_name in load_functions:
            # 查找函数定义
            func_pattern = rf'def {func_name}\(\):\s*"""[^"]*"""\s*[^}]+}'
            if re.search(func_pattern, content, re.DOTALL):
                # 在函数开头添加内存存储检查
                memory_check = f'''
    # 优先从内存存储恢复
    if memory_storage:
        try:
            restored = memory_storage.restore_from_backup("{func_name.replace('load_', '')}")
            if restored:
                global {func_name.replace('load_', '')}
                {func_name.replace('load_', '')} = memory_storage.get_config("{func_name.replace('load_', '')}")
                logging.info(f"[{{bot_config['bot_id']}}] {func_name.replace('load_', '')} 已从内存存储恢复")
                return
        except Exception as e:
            logging.error(f"[{{bot_config['bot_id']}}] 内存存储恢复失败: {{e}}")
    
    # 回退到文件加载'''
                
                # 在函数开头添加
                content = content.replace(
                    f'def {func_name}():',
                    f'def {func_name}():{memory_check}'
                )
        
        # 写入修改后的文件
        with open("csmain.py", "w", encoding="utf-8") as f:
            f.write(content)
        
        print("✅ 内存存储管理器已成功集成到csmain.py")
        print("📝 主要修改包括:")
        print("   - 添加了内存存储管理器导入")
        print("   - 修改了所有save/load函数以支持内存存储")
        print("   - 添加了新的管理命令: /backup, /restore, /storage")
        print("   - 保持了原有的文件存储作为备选方案")
        
        return True
        
    except Exception as e:
        print(f"❌ 集成失败: {e}")
        # 恢复备份文件
        if backup_file and os.path.exists(backup_file):
            shutil.copy2(backup_file, "csmain.py")
            print("🔄 已恢复原始文件")
        return False

def create_requirements_file():
    """创建requirements.txt文件"""
    requirements = """requests>=2.25.1
pyrogram>=2.0.0
tgcrypto>=1.2.5
"""
    
    with open("requirements.txt", "w", encoding="utf-8") as f:
        f.write(requirements)
    
    print("✅ requirements.txt 已创建")

def create_env_template():
    """创建环境变量模板"""
    env_template = """# GitHub备份配置
GITHUB_TOKEN=your_github_token_here
GITHUB_REPO_OWNER=laowangbot
GITHUB_REPO_NAME=wangbybot

# 机器人配置
BOT_ID=wang
BOT_NAME=老湿v1
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token

# Render配置
PORT=8080
RENDER_EXTERNAL_URL=your_render_url
"""
    
    with open(".env.template", "w", encoding="utf-8") as f:
        f.write(env_template)
    
    print("✅ .env.template 已创建")

def main():
    """主函数"""
    print("🚀 开始集成内存存储管理器...")
    print("=" * 50)
    
    # 检查必要文件
    if not os.path.exists("csmain.py"):
        print("❌ 找不到csmain.py文件，请确保在正确的目录中运行")
        return
    
    # 集成内存存储管理器
    if integrate_memory_storage():
        print("=" * 50)
        print("📋 下一步操作:")
        print("1. 在Render中设置GITHUB_TOKEN环境变量")
        print("2. 重启Render服务")
        print("3. 使用 /storage 命令检查存储状态")
        print("4. 使用 /backup 命令手动备份配置")
        
        # 创建辅助文件
        create_requirements_file()
        create_env_template()
        
    else:
        print("❌ 集成失败，请检查错误信息")

if __name__ == "__main__":
    main()
