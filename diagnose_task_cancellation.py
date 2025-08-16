#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机器人任务取消诊断工具 - 找出无法停止任务的具体原因
"""

import os
import json
import logging

def diagnose_task_cancellation():
    """诊断任务取消问题"""
    print("🔍 机器人任务取消诊断工具")
    print("=" * 60)
    
    # 1. 检查配置文件
    print("\n📁 检查配置文件...")
    
    # 检查user_configs.json
    if os.path.exists("user_configs.json"):
        try:
            with open("user_configs.json", 'r', encoding='utf-8') as f:
                config = json.load(f)
            print("  ✅ user_configs.json 存在且可读取")
            
            # 检查是否有无限制设置
            if "default_user" in config:
                user_config = config["default_user"]
                if user_config.get("no_restrictions", False):
                    print("  ⚠️  发现无限制模式设置，可能影响任务取消")
                if user_config.get("unlimited_mode", False):
                    print("  ⚠️  发现无限模式设置，可能影响任务取消")
        except Exception as e:
            print(f"  ❌ 读取配置文件失败: {e}")
    else:
        print("  ❌ user_configs.json 不存在")
    
    # 2. 检查运行中的任务
    print("\n📋 检查运行中的任务...")
    
    # 检查running_tasks.json
    if os.path.exists("running_tasks.json"):
        try:
            with open("running_tasks.json", 'r', encoding='utf-8') as f:
                running_tasks = json.load(f)
            
            if running_tasks:
                print(f"  📊 发现 {len(running_tasks)} 个运行中的任务")
                for user_id, tasks in running_tasks.items():
                    print(f"    用户 {user_id}: {len(tasks)} 个任务")
                    for task_id, task in tasks.items():
                        print(f"      任务 {task_id[:8]}: {task.get('state', '未知状态')}")
            else:
                print("  ℹ️  没有运行中的任务")
        except Exception as e:
            print(f"  ❌ 读取运行中任务失败: {e}")
    else:
        print("  ℹ️  running_tasks.json 不存在")
    
    # 3. 检查用户状态
    print("\n👤 检查用户状态...")
    
    # 检查user_states.json
    if os.path.exists("user_states.json"):
        try:
            with open("user_states.json", 'r', encoding='utf-8') as f:
                user_states = json.load(f)
            
            if user_states:
                print(f"  📊 发现 {len(user_states)} 个用户状态")
                for user_id, states in user_states.items():
                    print(f"    用户 {user_id}: {len(states)} 个状态")
                    for state in states:
                        print(f"      状态: {state.get('state', '未知')}, 任务ID: {state.get('task_id', '无')[:8]}")
            else:
                print("  ℹ️  没有用户状态")
        except Exception as e:
            print(f"  ❌ 读取用户状态失败: {e}")
    else:
        print("  ℹ️  user_states.json 不存在")
    
    # 4. 检查错误日志
    print("\n📝 检查错误日志...")
    
    # 检查bot_errors.log
    if os.path.exists("bot_errors.log"):
        try:
            with open("bot_errors.log", 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            if log_content.strip():
                print("  📊 发现错误日志内容:")
                lines = log_content.strip().split('\n')
                for line in lines[-5:]:  # 显示最后5行
                    print(f"    {line}")
            else:
                print("  ℹ️  错误日志为空")
        except Exception as e:
            print(f"  ❌ 读取错误日志失败: {e}")
    else:
        print("  ℹ️  bot_errors.log 不存在")
    
    # 5. 检查代码中的关键部分
    print("\n🔍 检查代码中的关键部分...")
    
    if os.path.exists("csmain.py"):
        try:
            with open("csmain.py", 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查关键函数和变量
            checks = [
                ("running_task_cancellation", "任务取消字典"),
                ("check_cancellation", "取消检查函数"),
                ("cancel_task:", "取消任务回调"),
                ("cancellation_check=", "取消检查参数传递"),
                ("asyncio.create_task", "异步任务创建"),
                ("task.cancel()", "任务取消调用")
            ]
            
            for check, description in checks:
                if check in content:
                    print(f"  ✅ {description}: 存在")
                else:
                    print(f"  ❌ {description}: 缺失")
                    
        except Exception as e:
            print(f"  ❌ 检查代码失败: {e}")
    
    # 6. 诊断建议
    print("\n💡 任务取消问题诊断建议:")
    print("=" * 60)
    print("1. 检查机器人是否正在运行任务")
    print("2. 确认取消按钮是否显示")
    print("3. 检查点击取消按钮后的响应")
    print("4. 查看控制台日志中的取消相关信息")
    print("5. 检查是否有长时间运行的任务")
    print("6. 确认任务状态是否正确更新")
    
    print("\n🔧 可能的解决方案:")
    print("=" * 60)
    print("1. 重启机器人 - 清理所有运行中的任务")
    print("2. 检查网络连接 - 确保与Telegram服务器通信正常")
    print("3. 检查权限 - 确保机器人在目标频道有发送权限")
    print("4. 检查任务配置 - 确保任务参数正确")
    print("5. 查看详细日志 - 找出具体的错误原因")
    
    print("\n🎯 下一步操作:")
    print("=" * 60)
    print("1. 运行机器人并尝试启动一个任务")
    print("2. 观察取消按钮是否出现")
    print("3. 点击取消按钮并观察响应")
    print("4. 检查控制台输出和错误日志")
    print("5. 如果问题持续，提供具体的错误信息")
    
    print("\n🎉 诊断完成！")
    return True

if __name__ == "__main__":
    diagnose_task_cancellation()


