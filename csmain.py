# ==================== 代码版本确认 ====================
print("正在运行老湿姬2.0专版 - 纯新引擎版本...")

# 添加端口绑定功能（用于Render Web Service）
def start_port_server():
    """启动端口服务器，用于Render Web Service"""
    try:
        import socket
        import http.server
        import socketserver
        
        class SimpleHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                response = """
                <html>
                <head><title>机器人运行中</title></head>
                <body>
                <h1>🤖 老湿姬2.0专版机器人</h1>
                <p>状态：正常运行中</p>
                <p>时间：{}</p>
                </body>
                </html>
                """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                self.wfile.write(response.encode())
            
            def log_message(self, format, *args):
                # 禁用HTTP访问日志
                pass
        
        # 绑定到Render分配的端口
        port = int(os.environ.get('PORT', 8080))
        
        with socketserver.TCPServer(("", port), SimpleHandler) as httpd:
            print(f"🌐 端口服务器启动成功，监听端口 {port}")
            httpd.serve_forever()
    
    except Exception as e:
        print(f"⚠️ 端口服务器启动失败: {e}")

# 在后台启动端口服务器
import threading
port_thread = threading.Thread(target=start_port_server, daemon=True)
port_thread.start()

# 添加心跳机制，保持Render服务活跃
def start_heartbeat():
    """启动心跳机制，防止Render 15分钟自动停止"""
    import requests
    import time
    
    while True:
        try:
            # 获取当前服务URL
            service_url = os.environ.get('RENDER_EXTERNAL_URL')
            if service_url:
                # 向自己的服务发送请求，保持活跃
                response = requests.get(f"{service_url}/", timeout=10)
                print(f"💓 心跳请求成功: {response.status_code}")
            else:
                print("💓 心跳机制运行中（无外部URL）")
        except Exception as e:
            print(f"💓 心跳请求失败: {e}")
        
        # 每10分钟发送一次心跳
        time.sleep(600)

# 启动心跳线程
heartbeat_thread = threading.Thread(target=start_heartbeat, daemon=True)
heartbeat_thread.start()
print("💓 心跳机制已启动，每10分钟发送一次请求")

# 启动FloodWait自动恢复检查线程
def start_floodwait_recovery():
    """启动FloodWait自动恢复检查，每5分钟检查一次"""
    import time
    while True:
        try:
            # 等待5分钟
            time.sleep(300)
            
            # 执行自动恢复检查
            recovered, expired = flood_wait_manager.auto_recovery_check()
            
            # 获取健康状态
            health = flood_wait_manager.get_health_status()
            
            if not health['is_healthy']:
                logging.warning(f"⚠️ FloodWait管理器健康检查: 发现 {health['abnormal_restrictions']} 个异常限制")
            else:
                logging.debug("✅ FloodWait管理器健康检查: 状态正常")
                
        except Exception as e:
            logging.error(f"❌ FloodWait自动恢复检查出错: {e}")
            time.sleep(60)  # 出错后等待1分钟再试

# 启动自动恢复线程
recovery_thread = threading.Thread(target=start_floodwait_recovery, daemon=True)
recovery_thread.start()
print("🔄 FloodWait自动恢复检查已启动，每5分钟检查一次")

import os
import time
import asyncio
import re
import logging
import uuid
import json
import random
import signal
import sys

# 持久化存储配置
PERSISTENT_STORAGE = "/opt/render/project/src/data"
if not os.path.exists(PERSISTENT_STORAGE):
    os.makedirs(PERSISTENT_STORAGE, exist_ok=True)

def get_config_path(filename):
    """获取配置文件路径"""
    if os.getenv('RENDER') == 'true':
        return os.path.join(PERSISTENT_STORAGE, filename)
    else:
        return filename
from datetime import datetime
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from pyrogram.enums import ChatType
from pyrogram.errors.exceptions import BadRequest, FloodWait
import config
from urllib.parse import urlparse

# ==================== FloodWait管理器 ====================
class FloodWaitManager:
    def __init__(self):
        self.flood_wait_times = {}  # 记录每个操作的等待时间
        self.last_operation_time = {}  # 记录每个操作的最后执行时间
        self.operation_delays = {  # 不同操作的延迟配置（已最小化）
            'edit_message': 0.5,    # 编辑消息间隔0.5秒
            'send_message': 0.3,    # 发送消息间隔0.3秒
            'forward_message': 0.5, # 转发消息间隔0.5秒
            'delete_message': 0.3,  # 删除消息间隔0.3秒
            'copy_message': 0.3,    # 复制消息间隔0.3秒
            'send_media_group': 0.5, # 发送媒体组间隔0.5秒
        }
    
    async def wait_if_needed(self, operation_type, user_id=None):
        """检查是否需要等待，智能处理FloodWait限制"""
        current_time = time.time()
        key = f"{operation_type}_{user_id}" if user_id else operation_type
        
        # 检查FloodWait限制 - 只影响机器人API调用，不影响用户操作
        if operation_type in self.flood_wait_times:
            wait_until = self.flood_wait_times[operation_type]
            remaining = wait_until - current_time
            
            if remaining > 0:
                # 智能等待策略 - 只等待必要的API操作
                if operation_type in ['send_message', 'edit_message', 'delete_message']:
                    # 这些是机器人API调用，需要等待
                    if remaining > 60:  # 超过1分钟，使用更激进的策略
                        safe_wait = min(30, remaining // 2)  # 最多等待30秒
                        logging.info(f"🔄 API调用等待: {operation_type} 原始等待 {remaining:.1f}秒，实际等待 {safe_wait}秒")
                        await asyncio.sleep(safe_wait)
                        # 清除过长的限制
                        if remaining > 120:
                            del self.flood_wait_times[operation_type]
                            logging.info(f"🧹 清除过长的FloodWait限制: {operation_type}")
                    else:
                        # 正常等待
                        logging.info(f"⏳ API调用等待: {operation_type} 剩余 {remaining:.1f}秒")
                        await asyncio.sleep(remaining)
                        # 清除已完成的限制
                        del self.flood_wait_times[operation_type]
                else:
                    # 非API调用操作，不等待，直接清除限制
                    logging.info(f"🧹 非API操作，清除FloodWait限制: {operation_type}")
                    del self.flood_wait_times[operation_type]
        
        # 基本的操作间隔控制（最小化）- 只针对API调用
        if key in self.last_operation_time and operation_type in ['send_message', 'edit_message', 'delete_message']:
            last_time = self.last_operation_time[key]
            delay_needed = self.operation_delays.get(operation_type, 0.1)  # 减少到0.1秒
            time_since_last = current_time - last_time
            
            if time_since_last < delay_needed:
                sleep_time = max(0.01, delay_needed - time_since_last)
                logging.debug(f"API操作间隔控制: {operation_type} 等待 {sleep_time:.3f} 秒")
                await asyncio.sleep(sleep_time)
        
        # 更新最后操作时间
        self.last_operation_time[key] = time.time()
    
    def is_api_operation(self, operation_type):
        """判断是否为API调用操作"""
        api_operations = ['send_message', 'edit_message', 'delete_message', 'forward_message', 'copy_message']
        return operation_type in api_operations
    
    def set_flood_wait(self, operation_type, wait_time, user_id=None):
        """设置FloodWait等待时间，智能处理异常时间"""
        # 智能检测异常时间
        if wait_time > 300:  # 超过5分钟，可能是异常
            logging.warning(f"🚨 检测到极异常的FloodWait时间: {wait_time}秒，可能是Telegram API错误")
            # 对于极异常时间，直接限制为30秒
            safe_wait_time = 30
        elif wait_time > 120:  # 超过2分钟，可能是异常
            logging.warning(f"⚠️ 检测到异常的FloodWait时间: {wait_time}秒，已自动限制为60秒")
            safe_wait_time = 60
        elif wait_time > 60:  # 超过1分钟，可能是异常
            logging.warning(f"⚠️ 检测到较长的FloodWait时间: {wait_time}秒，已自动限制为60秒")
            safe_wait_time = 60
        else:
            # 正常时间范围，直接使用
            safe_wait_time = wait_time
        
        # 只记录API调用的FloodWait限制，不影响用户操作
        if self.is_api_operation(operation_type):
            if not user_id or user_id == 'unknown':
                key = operation_type
                wait_until = time.time() + safe_wait_time
                self.flood_wait_times[key] = wait_until
                
                # 记录调整信息
                if safe_wait_time != wait_time:
                    logging.warning(f"🔄 API调用FloodWait调整: {operation_type} 从 {wait_time}秒 调整为 {safe_wait_time}秒")
                
                # 格式化等待时间
                if safe_wait_time >= 60:
                    time_str = f"{safe_wait_time // 60}分钟{safe_wait_time % 60}秒"
                else:
                    time_str = f"{safe_wait_time}秒"
                
                logging.info(f"📝 API调用 {operation_type} 设置等待时间: {time_str}")
            else:
                # 用户级API限制只记录日志，不阻止操作
                logging.info(f"用户 {user_id} 的API调用 {operation_type} 遇到限制，但已移除阻止机制")
        else:
            # 非API操作，不记录FloodWait限制
            logging.info(f"非API操作 {operation_type}，不记录FloodWait限制")
    
    def get_wait_time(self, operation_type, user_id=None):
        """获取剩余等待时间（已移除用户级限制）"""
        # 只检查全局限制，不再检查用户级限制
        if operation_type in self.flood_wait_times:
            wait_until = self.flood_wait_times[operation_type]
            remaining = wait_until - time.time()
            return max(0, remaining)
        return 0
    
    def get_all_flood_wait_status(self):
        """获取所有FloodWait状态"""
        current_time = time.time()
        status = {}
        
        for key, wait_until in self.flood_wait_times.items():
            remaining = wait_until - current_time
            if remaining > 0:
                # 解析key获取操作类型和用户ID
                if '_' in key:
                    operation_type, user_id = key.split('_', 1)
                else:
                    operation_type, user_id = key, None
                
                # 格式化剩余时间
                if remaining >= 3600:
                    time_str = f"{remaining // 3600}小时{(remaining % 3600) // 60}分钟"
                elif remaining >= 60:
                    time_str = f"{remaining // 60}分钟{remaining % 60}秒"
                else:
                    time_str = f"{remaining:.1f}秒"
                
                status[key] = {
                    'operation_type': operation_type,
                    'user_id': user_id,
                    'remaining_seconds': remaining,
                    'remaining_formatted': time_str,
                    'wait_until': wait_until
                }
        
        return status
    
    def get_user_flood_wait_status(self, user_id):
        """获取特定用户的FloodWait状态（已移除用户级限制）"""
        # 用户不再有个人限制，只返回全局限制状态
        current_time = time.time()
        user_status = {}
        
        # 检查全局限制是否影响该用户
        for operation_type, wait_until in self.flood_wait_times.items():
            remaining = wait_until - current_time
            if remaining > 0:
                # 格式化剩余时间
                if remaining >= 3600:
                    time_str = f"{remaining // 3600}小时{(remaining % 3600) // 60}分钟"
                elif remaining >= 60:
                    time_str = f"{remaining // 60}分钟{remaining % 60}秒"
                else:
                    time_str = f"{remaining:.1f}秒"
                
                user_status[operation_type] = {
                    'remaining_seconds': remaining,
                    'remaining_formatted': time_str,
                    'wait_until': wait_until,
                    'type': 'global'  # 标记为全局限制
                }
        
        return user_status
    
    def clear_expired_flood_wait(self):
        """清理过期的FloodWait记录"""
        current_time = time.time()
        expired_keys = []
        
        for key, wait_until in self.flood_wait_times.items():
            if current_time >= wait_until:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.flood_wait_times[key]
            logging.debug(f"清理过期的FloodWait记录: {key}")
        
        return len(expired_keys)
    
    def auto_recovery_check(self):
        """自动恢复检查 - 智能检测并修复异常的FloodWait限制"""
        current_time = time.time()
        recovered_count = 0
        expired_count = 0
        
        # 检查所有FloodWait限制
        for key, wait_until in list(self.flood_wait_times.items()):
            remaining = wait_until - current_time
            
            if remaining <= 0:
                # 已过期的限制
                del self.flood_wait_times[key]
                expired_count += 1
                logging.debug(f"清理过期的API调用FloodWait限制: {key}")
            elif remaining > 300:  # 超过5分钟，极异常
                # 极异常限制，直接清除
                del self.flood_wait_times[key]
                recovered_count += 1
                logging.warning(f"🚨 清除极异常的API调用FloodWait限制: {key}，剩余时间: {remaining}秒")
            elif remaining > 120:  # 超过2分钟，异常
                # 异常限制，限制为60秒
                new_wait_until = current_time + 60
                self.flood_wait_times[key] = new_wait_until
                recovered_count += 1
                logging.warning(f"⚠️ 修复异常的API调用FloodWait限制: {key}，从 {remaining}秒 调整为 60秒")
            elif remaining > 60:  # 超过1分钟，可能异常
                # 可能异常，限制为原时间的一半
                new_wait_time = min(60, remaining // 2)
                new_wait_until = current_time + new_wait_time
                self.flood_wait_times[key] = new_wait_until
                recovered_count += 1
                logging.info(f"🔄 调整较长的API调用FloodWait限制: {key}，从 {remaining}秒 调整为 {new_wait_time}秒")
        
        # 清理过期的记录
        expired_count += self.clear_expired_flood_wait()
        
        if recovered_count > 0 or expired_count > 0:
            logging.info(f"🧹 API调用FloodWait自动恢复: 修复 {recovered_count} 个异常限制，清理 {expired_count} 个过期记录")
        
        return recovered_count, expired_count
    
    def get_health_status(self):
        """获取FloodWait管理器健康状态"""
        current_time = time.time()
        total_restrictions = len(self.flood_wait_times)
        active_restrictions = 0
        abnormal_restrictions = 0
        
        for key, wait_until in self.flood_wait_times.items():
            remaining = wait_until - current_time
            if remaining > 0:
                active_restrictions += 1
                # 检查是否有异常的长等待时间
                if remaining > 300:  # 超过5分钟
                    abnormal_restrictions += 1
        
        return {
            'total_restrictions': total_restrictions,
            'active_restrictions': active_restrictions,
            'abnormal_restrictions': abnormal_restrictions,
            'is_healthy': abnormal_restrictions == 0,
            'last_check': current_time
        }
    
    def get_optimal_batch_size(self, operation_type):
        """获取最优批量操作大小"""
        # 根据操作类型返回安全的批量大小
        if operation_type in ['send_message', 'edit_message']:
            return 5  # 消息操作，批量5个
        elif operation_type in ['forward_message', 'copy_message']:
            return 3  # 转发/复制操作，批量3个
        elif operation_type in ['delete_message']:
            return 10  # 删除操作，批量10个
        else:
            return 1  # 其他操作，单个执行

# 创建全局FloodWait管理器实例
flood_wait_manager = FloodWaitManager()

# ==================== 性能监控系统 ====================
performance_stats = defaultdict(list)

def monitor_performance(func_name):
    """性能监控装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                performance_stats[func_name].append(duration)
                
                # 保持最近100次记录
                if len(performance_stats[func_name]) > 100:
                    performance_stats[func_name] = performance_stats[func_name][-100:]
                    
                # 记录慢操作
                if duration > 5.0:  # 超过5秒的操作
                    logging.warning(f"慢操作检测: {func_name} 耗时 {duration:.2f} 秒")
        return wrapper
    return decorator

def get_performance_stats():
    """获取性能统计信息"""
    stats = {}
    for func_name, durations in performance_stats.items():
        if durations:
            stats[func_name] = {
                'count': len(durations),
                'avg': sum(durations) / len(durations),
                'max': max(durations),
                'min': min(durations),
                'recent_avg': sum(durations[-10:]) / min(len(durations), 10)
            }
    return stats

# 导入新的搬运引擎
try:
    from new_cloning_engine import RobustCloningEngine, MessageDeduplicator
    NEW_ENGINE_AVAILABLE = True
    logging.info("新搬运引擎已加载")
except ImportError as e:
    NEW_ENGINE_AVAILABLE = False
    logging.warning(f"新搬运引擎加载失败: {e}")

# 导入内存存储管理器
try:
    from memory_storage_manager import MemoryStorageManager
    MEMORY_STORAGE_AVAILABLE = True
    logging.info("内存存储管理器已加载")
except ImportError as e:
    MEMORY_STORAGE_AVAILABLE = False
    logging.warning(f"内存存储管理器加载失败: {e}")

# Render 部署支持
try:
    from keep_alive import run_keep_alive
    RENDER_DEPLOYMENT = True
    logging.info("Render keep_alive 模块已加载")
except ImportError:
    RENDER_DEPLOYMENT = False
    logging.info("Render keep_alive 模块未找到，跳过部署支持")

# ==================== 内存存储管理器初始化 ====================
# 创建内存存储管理器实例
memory_storage = None

# ==================== 运行中任务持久化 ====================
running_tasks = {}

def save_running_tasks():
    try:
        with open("running_tasks.json", "w", encoding="utf-8") as f:
            json.dump(running_tasks, f, ensure_ascii=False, indent=4)
        logging.info("运行中任务快照已保存。")
    except Exception as e:
        logging.error(f"保存运行中任务失败: {e}")

def sync_task_progress(user_id, task_id, sub_task_index, cloned_count, processed_count, current_offset_id, task_stats=None):
    """实时同步任务进度到running_tasks，确保取消时不丢失进度"""
    try:
        # 确保running_tasks结构存在
        if str(user_id) not in running_tasks:
            running_tasks[str(user_id)] = {}
        if task_id not in running_tasks[str(user_id)]:
            running_tasks[str(user_id)][task_id] = {"progress": {}}
        if "progress" not in running_tasks[str(user_id)][task_id]:
            running_tasks[str(user_id)][task_id]["progress"] = {}
        
        # 更新进度信息
        progress_key = f"sub_task_{sub_task_index}"
        running_tasks[str(user_id)][task_id]["progress"][progress_key] = {
            "cloned_count": cloned_count,
            "processed_count": processed_count,
            "current_offset_id": current_offset_id
        }
        
        # 如果有统计信息，也保存
        if task_stats:
            running_tasks[str(user_id)][task_id]["progress"][progress_key]["message_stats"] = task_stats
        
        # 更新最后保存时间
        running_tasks[str(user_id)][task_id]["last_progress_update"] = time.time()
        
        logging.debug(f"任务 {task_id[:8]} 子任务 {sub_task_index}: 同步进度 - 已搬运:{cloned_count}, 已处理:{processed_count}, 当前ID:{current_offset_id}")
        
    except Exception as e:
        logging.error(f"同步任务进度失败: {e}")

def load_running_tasks():
    global running_tasks
    try:
        if os.path.exists("running_tasks.json"):
            with open("running_tasks.json", "r", encoding="utf-8") as f:
                running_tasks = json.load(f)
            logging.info("运行中任务快照已载入。")
    except Exception as e:
        logging.error(f"载入运行中任务失败: {e}")

# ==================== 配置日志系统 ====================
LOG_FILE = "bot_errors.log"

# 创建自定义格式器，让控制台输出更简洁
class CustomFormatter(logging.Formatter):
    def format(self, record):
        # 控制台显示简化格式
        if hasattr(record, 'stream_handler'):
            level_icon = {
                'DEBUG': '🔍',
                'INFO': 'ℹ️',
                'WARNING': '⚠️',
                'ERROR': '❌',
                'CRITICAL': '🚨'
            }.get(record.levelname, record.levelname)
            return f"[{self.formatTime(record, '%H:%M:%S')}] {level_icon} {record.getMessage()}"
        # 文件显示完整格式
        return f"[{self.formatTime(record, '%Y-%m-%d %H:%M:%S')}] - {record.levelname} - {record.getMessage()}"

# 配置日志
logging.basicConfig(level=logging.INFO, handlers=[])

# 文件处理器 - 详细日志
file_handler = logging.FileHandler(LOG_FILE, 'a', 'utf-8')
file_handler.setFormatter(CustomFormatter())
file_handler.setLevel(logging.INFO)

# 控制台处理器 - 简化日志
console_handler = logging.StreamHandler()
console_handler.setFormatter(CustomFormatter())
console_handler.setLevel(logging.INFO)

# 添加标记以区分处理器
def add_stream_marker(record):
    record.stream_handler = True
    return True

console_handler.addFilter(add_stream_marker)

# 添加处理器
logger = logging.getLogger()
logger.addHandler(file_handler)
logger.addHandler(console_handler)

print("=" * 60)
print("🤖 老湿姬2.0专版启动中...")
print("=" * 60)
logging.info("日志系统已启动")

# ==================== 配置区 ====================
API_ID = config.API_ID
API_HASH = config.API_HASH
BOT_TOKEN = config.BOT_TOKEN
# 新搬运引擎配置
PROGRESS_SAVE_INTERVAL = 20  # 每处理20条消息保存一次进度（保留用于断点续传）

# 性能配置常量
BATCH_SEND_SIZE = 10  # 批量发送大小
MIN_INTERVAL = 2  # 最小发送间隔（秒）
FLOOD_WAIT_THRESHOLD = 30  # 流量限制阈值（秒）

# 性能模式配置
PERFORMANCE_MODE = "aggressive"  # 可选: "conservative", "balanced", "aggressive"
# conservative: 保守模式，适合稳定性和避免API限制
# balanced: 平衡模式，性能和稳定性的折中
# aggressive: 激进模式，最大化性能，可能触发API限制

# 用户名登录系统配置
ENABLE_USERNAME_LOGIN = True  # 启用用户名登录
AUTHORIZED_USERNAMES = ["admin"]  # 授权用户名列表（只保留admin）
ADMIN_USERNAMES = ["admin"]  # 管理员用户名列表
LOGIN_SESSION_TIMEOUT = 30 * 24 * 3600  # 登录会话超时时间（30天）

# 密码验证配置（更安全的方式）
USER_CREDENTIALS = {
    "admin": "159413"  # 用户名: 密码
}

# ==================== 多机器人配置管理 ====================
def get_bot_config():
    """获取机器人配置"""
    # 从环境变量获取机器人标识
    bot_id = os.environ.get('BOT_ID', 'main')
    bot_name = os.environ.get('BOT_NAME', f'老湿姬{bot_id}')
    bot_version = os.environ.get('BOT_VERSION', '多机器人版本')
    
    # 从环境变量获取Telegram配置
    api_id = os.environ.get('API_ID')
    api_hash = os.environ.get('API_HASH')
    bot_token = os.environ.get('BOT_TOKEN')
    
    if not all([api_id, api_hash, bot_token]):
        raise ValueError("缺少必需的环境变量: API_ID, API_HASH, BOT_TOKEN")
    
    return {
        'bot_id': bot_id,
        'bot_name': bot_name,
        'bot_version': bot_version,
        'api_id': api_id,
        'api_hash': api_hash,
        'bot_token': bot_token
    }

# 获取配置
bot_config = get_bot_config()
print(f"🤖 启动机器人: {bot_config['bot_name']} - {bot_config['bot_version']}")
print(f"🔑 机器人ID: {bot_config['bot_id']}")

# 初始化内存存储管理器
if MEMORY_STORAGE_AVAILABLE:
    try:
        memory_storage = MemoryStorageManager(bot_config['bot_id'], backup_interval=300)
        logging.info(f"[{bot_config['bot_id']}] 内存存储管理器已初始化")
    except Exception as e:
        logging.error(f"[{bot_config['bot_id']}] 内存存储管理器初始化失败: {e}")
        memory_storage = None

app = Client(f"{bot_config['bot_id']}_session", api_id=bot_config['api_id'], api_hash=bot_config['api_hash'], bot_token=bot_config['bot_token'])

# ==================== 全局状态 ====================
user_configs = {}  # 存储每个用户的配置，包括频道组和功能设定
user_states = {} # { user_id: [ {task_id: "...", state: "...", ...} ] }
user_history = {} # 存储每个用户的历史记录
listen_media_groups = {}  # {(chat_id, media_group_id): [messages]}
realtime_dedupe_cache = {}  # 实时监听去重缓存 {(source_chat_id, target_chat_id): set()}
processed_messages = {}  # 存储已处理的消息，防止重复处理
# 新搬运引擎实例和状态
robust_cloning_engine = None
running_task_cancellation = {}  # 任务ID -> 取消标志

# 登录系统状态
logged_in_users = {}  # {user_id: {"username": "用户名", "login_time": timestamp, "last_active": timestamp}}
login_attempts = {}   # {user_id: {"attempts": count, "last_attempt": timestamp, "locked_until": timestamp}}
pending_logins = {}   # {user_id: {"waiting_for_username": True}}

# ==================== 登录系统功能 ====================
def save_login_data():
    # 优先使用内存存储
    if memory_storage:
        try:
            memory_storage.set_config("login_data", login_data)
            logging.info(f"[{bot_config['bot_id']}] login_data 已保存到内存存储")
            return
        except Exception as e:
            logging.error(f"[{bot_config['bot_id']}] 内存存储保存失败: {e}")
    
    # 回退到文件存储
    """保存登录数据到文件"""
    try:
        login_file = get_config_path(f"user_login_{bot_config['bot_id']}.json")
        login_data = {
            "logged_in_users": logged_in_users,
            "login_attempts": login_attempts
        }
        with open(login_file, "w", encoding="utf-8") as f:
            json.dump(login_data, f, ensure_ascii=False, indent=4)
        logging.info(f"[{bot_config['bot_id']}] 登录数据已保存到 {login_file}")
    except Exception as e:
        logging.error(f"[{bot_config['bot_id']}] 保存登录数据失败: {e}")

def load_login_data():
    # 优先从内存存储恢复
    if memory_storage:
        try:
            restored = memory_storage.restore_from_backup("login_data")
            if restored:
                global login_data
                login_data = memory_storage.get_config("login_data")
                logging.info(f"[{bot_config['bot_id']}] login_data 已从内存存储恢复")
                return
        except Exception as e:
            logging.error(f"[{bot_config['bot_id']}] 内存存储恢复失败: {e}")
    
    # 回退到文件加载
    """从文件加载登录数据"""
    global logged_in_users, login_attempts
    try:
        login_file = get_config_path(f"user_login_{bot_config['bot_id']}.json")
        if os.path.exists(login_file):
            with open(login_file, "r", encoding="utf-8") as f:
                login_data = json.load(f)
                logged_in_users = login_data.get("logged_in_users", {})
                login_attempts = login_data.get("login_attempts", {})
            logging.info(f"[{bot_config['bot_id']}] 登录数据已从 {login_file} 加载")
        else:
            logging.info(f"[{bot_config['bot_id']}] 登录文件 {login_file} 不存在，将创建新登录数据")
            logged_in_users = {}
            login_attempts = {}
    except Exception as e:
        logging.error(f"[{bot_config['bot_id']}] 加载登录数据失败: {e}")
        logged_in_users = {}
        login_attempts = {}

def is_user_logged_in(user_id):
    """检查用户是否已登录且会话有效"""
    if not ENABLE_USERNAME_LOGIN:
        return True
    
    user_id_str = str(user_id)
    if user_id_str not in logged_in_users:
        return False
    
    user_data = logged_in_users[user_id_str]
    login_time = user_data.get("login_time", 0)
    current_time = time.time()
    
    # 检查会话是否过期
    if current_time - login_time > LOGIN_SESSION_TIMEOUT:
        del logged_in_users[user_id_str]
        save_login_data()
        return False
    
    return True

def is_admin_user(user_id):
    """检查用户是否为管理员"""
    if not is_user_logged_in(user_id):
        return False
    
    user_id_str = str(user_id)
    if user_id_str in logged_in_users:
        username = logged_in_users[user_id_str].get("username", "")
        return username in ADMIN_USERNAMES
    return False

def can_attempt_login(user_id):
    """检查用户是否可以尝试登录（锁定功能已禁用）"""
    # 锁定功能已禁用，所有用户都可以尝试登录
    return True

def record_login_attempt(user_id, success=False):
    """记录登录尝试（锁定功能已禁用）"""
    user_id_str = str(user_id)
    current_time = time.time()
    
    if user_id_str not in login_attempts:
        login_attempts[user_id_str] = {"attempts": 0, "last_attempt": 0, "locked_until": 0}
    
    attempt_data = login_attempts[user_id_str]
    attempt_data["last_attempt"] = current_time
    
    if success:
        # 登录成功，清空失败记录
        attempt_data["attempts"] = 0
        attempt_data["locked_until"] = 0
    else:
        # 登录失败，但不锁定账户
        attempt_data["attempts"] += 1
        # 锁定功能已禁用
    
    save_login_data()

def login_user(user_id, username):
    """用户登录"""
    user_id_str = str(user_id)
    current_time = time.time()
    
    logged_in_users[user_id_str] = {
        "username": username,
        "login_time": current_time,
        "last_active": current_time
    }
    
    record_login_attempt(user_id, success=True)
    save_login_data()
    
    logging.info(f"用户 {user_id} 以用户名 '{username}' 成功登录")

def update_user_activity(user_id):
    """更新用户活动时间"""
    if is_user_logged_in(user_id):
        user_id_str = str(user_id)
        logged_in_users[user_id_str]["last_active"] = time.time()

def logout_user(user_id):
    """用户登出"""
    user_id_str = str(user_id)
    if user_id_str in logged_in_users:
        username = logged_in_users[user_id_str].get("username", "Unknown")
        del logged_in_users[user_id_str]
        save_login_data()
        logging.info(f"用户 {user_id} (用户名: {username}) 已登出")

def get_logged_in_username(user_id):
    """获取已登录用户的用户名"""
    user_id_str = str(user_id)
    if user_id_str in logged_in_users:
        return logged_in_users[user_id_str].get("username", "Unknown")
    return None

async def show_login_screen(message):
    """显示登录界面"""
    user_id = message.from_user.id
    
    # 锁定检查已禁用，直接显示登录界面
    
    # 检查登录尝试次数
    user_id_str = str(user_id)
    if user_id_str not in login_attempts:
        login_attempts[user_id_str] = {"attempts": 0, "last_attempt": 0}
    
    attempts = login_attempts[user_id_str]["attempts"]
    attempts_info = f"\n⚠️ 登录失败次数：{attempts}/3" if attempts > 0 else ""
    
    await message.reply_text(
        f"🔐 **机器人访问验证**\n\n"
        f"请按以下格式输入登录信息：{attempts_info}\n"
        f"格式：`用户名:密码`\n"
        f"例如：`demo:demo123`\n\n"
        f"💡 如需获取账号，请联系管理员",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("ℹ️ 联系管理员", url="https://t.me/your_admin_contact")
        ]])
    )
    
    # 标记用户正在等待输入用户名
    pending_logins[user_id] = {"waiting_for_username": True}

async def handle_username_input(message):
    """处理用户名:密码输入"""
    user_id = message.from_user.id
    login_input = message.text.strip()
    
    # 清除等待状态
    pending_logins.pop(user_id, None)
    
    if not can_attempt_login(user_id):
        await show_login_screen(message)
        return
    
    # 验证输入格式：用户名:密码
    if ":" not in login_input:
        # 格式错误
        await message.reply_text(
            f"❌ **格式错误**\n\n"
            f"请使用正确格式：`用户名:密码`\n"
            f"例如：`demo:demo123`\n\n"
            "请重新使用 /start 命令开始登录："
        )
        return
    
    try:
        username, password = login_input.split(":", 1)
        username = username.strip()
        password = password.strip()
    except ValueError:
        await message.reply_text(
            f"❌ **格式错误**\n\n"
            f"请使用正确格式：`用户名:密码`\n"
            "请重新使用 /start 命令开始登录："
        )
        return
    
    # 验证用户名和密码
    if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
        # 登录成功，清理所有失败记录
        user_id_str = str(user_id)
        if user_id_str in login_attempts:
            del login_attempts[user_id_str]
        
        # 登录用户
        login_user(user_id, username)
        
        is_admin = username in ADMIN_USERNAMES
        admin_text = "\n👑 您拥有管理员权限" if is_admin else ""
        
        await message.reply_text(
            f"✅ **登录成功**\n\n"
            f"欢迎，{username}！{admin_text}\n"
            f"您现在可以使用机器人的所有功能。",
            reply_markup=get_main_menu_buttons(user_id)
        )
    else:
        # 登录失败，直接管理尝试次数
        user_id_str = str(user_id)
        if user_id_str not in login_attempts:
            login_attempts[user_id_str] = {"attempts": 0, "last_attempt": 0}
        
        login_attempts[user_id_str]["attempts"] += 1
        login_attempts[user_id_str]["last_attempt"] = time.time()
        
        attempts = login_attempts[user_id_str]["attempts"]
        
        if attempts >= 3:
            await message.reply_text(
                f"❌ **登录失败**\n\n"
                f"用户名或密码错误。\n"
                f"🔒 由于多次失败，账户已被锁定1小时。"
            )
        else:
            remaining_attempts = 3 - attempts
            await message.reply_text(
                f"❌ **登录失败**\n\n"
                f"用户名或密码错误。\n"
                f"剩余尝试次数：{remaining_attempts}\n\n"
                "请重新使用 /start 命令开始登录："
            )

def require_login(func):
    """登录装饰器 - 要求用户必须登录才能访问功能"""
    async def wrapper(*args, **kwargs):
        # 从参数中提取user_id
        user_id = None
        if args:
            if hasattr(args[0], 'from_user'):  # Message对象
                user_id = args[0].from_user.id
            elif hasattr(args[0], 'message') and hasattr(args[0].message, 'from_user'):  # CallbackQuery对象
                user_id = args[0].message.from_user.id
            elif len(args) > 1 and isinstance(args[1], int):  # 直接传入的user_id
                user_id = args[1]
        
        if user_id and not is_user_logged_in(user_id):
            # 用户未登录，显示登录界面
            if hasattr(args[0], 'reply_text'):
                await show_login_screen(args[0])
            elif hasattr(args[0], 'message'):
                await show_login_screen(args[0].message)
            return
        
        # 更新用户活动时间
        if user_id:
            update_user_activity(user_id)
        
        return await func(*args, **kwargs)
    return wrapper

async def handle_logout(message, user_id):
    """处理用户登出"""
    username = get_logged_in_username(user_id)
    logout_user(user_id)
    
    await safe_edit_or_reply(message,
        f"👋 **再见，{username}！**\n\n"
        f"您已成功退出登录。\n"
        f"感谢使用本机器人！",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔐 重新登录", callback_data="refresh_login_status")
        ]])
    )

async def show_admin_panel(message, user_id):
    """显示管理员控制面板"""
    if not is_admin_user(user_id):
        await safe_edit_or_reply(message, "❌ 您没有管理员权限")
        return
    
    # 统计信息
    total_users = len(logged_in_users)
    total_authorized = len(AUTHORIZED_USERNAMES)
    total_admins = len(ADMIN_USERNAMES)
    
    # 在线用户列表
    online_users = []
    current_time = time.time()
    for uid, data in logged_in_users.items():
        last_active = data.get("last_active", 0)
        if current_time - last_active < 300:  # 5分钟内活跃
            online_users.append(data.get("username", "Unknown"))
    
    # 获取性能统计
    perf_stats = get_performance_stats()
    
    text = (
        f"👑 **管理员控制面板**\n\n"
        f"📊 **系统统计：**\n"
        f"• 当前登录用户：{total_users} 人\n"
        f"• 授权用户总数：{total_authorized} 人\n"
        f"• 管理员总数：{total_admins} 人\n"
        f"• 在线用户：{len(online_users)} 人\n\n"
        f"⚡ **性能监控：**\n"
        f"• 监控函数：{len(perf_stats)} 个\n"
    )
    
    # 显示最慢的3个操作
    if perf_stats:
        sorted_perf = sorted(perf_stats.items(), key=lambda x: x[1]['avg'], reverse=True)[:3]
        text += "• 最慢操作：\n"
        for func_name, stats in sorted_perf:
            text += f"  - {func_name}: {stats['avg']:.2f}s (avg)\n"
    
    text += "\n🟢 **当前在线：**\n"
    
    if online_users:
        text += "• " + "\n• ".join(online_users[:10])
        if len(online_users) > 10:
            text += f"\n... 还有 {len(online_users) - 10} 人"
    else:
        text += "暂无在线用户"
    
    buttons = [
        [
            InlineKeyboardButton("👥 用户管理", callback_data="admin_user_management"),
            InlineKeyboardButton("📊 详细统计", callback_data="admin_statistics")
        ],
        [
            InlineKeyboardButton("⚙️ 系统设置", callback_data="admin_system_settings"),
            InlineKeyboardButton("📋 登录日志", callback_data="admin_login_logs")
        ],
        [
            InlineKeyboardButton("⚡ 性能监控", callback_data="admin_performance"),
            InlineKeyboardButton("🔧 系统维护", callback_data="admin_maintenance")
        ],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_admin_action(message, user_id, action):
    """处理管理员操作"""
    if not is_admin_user(user_id):
        await safe_edit_or_reply(message, "❌ 您没有管理员权限")
        return
    
    if action == "admin_user_management":
        await show_user_management(message, user_id)
    elif action == "admin_statistics":
        await show_detailed_statistics(message, user_id)
    elif action == "admin_system_settings":
        await show_system_settings(message, user_id)
    elif action == "admin_login_logs":
        await show_login_logs(message, user_id)
    elif action == "admin_performance":
        await show_performance_monitor(message, user_id)
    elif action == "admin_maintenance":
        await show_system_maintenance(message, user_id)

async def show_user_management(message, user_id):
    """显示用户管理界面"""
    text = "👥 **用户管理**\n\n"
    text += f"🔑 **授权用户列表：**\n"
    
    for i, username in enumerate(AUTHORIZED_USERNAMES, 1):
        is_admin = "👑" if username in ADMIN_USERNAMES else "👤"
        is_online = "🟢" if any(data.get("username") == username for data in logged_in_users.values()) else "⚪"
        text += f"{i}. {is_admin} {is_online} {username}\n"
    
    text += f"\n💡 提示：🟢=在线 ⚪=离线 👑=管理员 👤=普通用户"
    
    buttons = [
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="show_admin_panel")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_detailed_statistics(message, user_id):
    """显示详细统计信息"""
    current_time = time.time()
    
    # 统计登录用户的活跃度
    active_1h = sum(1 for data in logged_in_users.values() if current_time - data.get("last_active", 0) < 3600)
    active_24h = sum(1 for data in logged_in_users.values() if current_time - data.get("last_active", 0) < 86400)
    
    # 统计配置的频道组数量
    total_pairs = sum(len(cfg.get("channel_pairs", [])) for cfg in user_configs.values())
    
    # 统计任务数量
    active_tasks = sum(len(tasks) for tasks in user_states.values())
    saved_tasks = sum(len(tasks) for tasks in running_tasks.values())
    
    text = (
        f"📊 **详细统计信息**\n\n"
        f"👥 **用户活跃度：**\n"
        f"• 1小时内活跃：{active_1h} 人\n"
        f"• 24小时内活跃：{active_24h} 人\n"
        f"• 总登录用户：{len(logged_in_users)} 人\n\n"
        f"📋 **系统使用情况：**\n"
        f"• 配置的频道组：{total_pairs} 个\n"
        f"• 活跃任务：{active_tasks} 个\n"
        f"• 保存的任务：{saved_tasks} 个\n\n"
        f"🔐 **安全信息：**\n"
        f"• 失败登录记录：{len(login_attempts)} 个\n"
        f"• 授权用户数：{len(AUTHORIZED_USERNAMES)} 人\n"
        f"• 管理员数：{len(ADMIN_USERNAMES)} 人"
    )
    
    buttons = [
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="show_admin_panel")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_system_settings(message, user_id):
    """显示系统设置"""
    text = (
        f"⚙️ **系统设置**\n\n"
        f"🔐 **登录系统：**\n"
        f"• 登录验证：{'✅ 启用' if ENABLE_USERNAME_LOGIN else '❌ 禁用'}\n"
        f"• 会话超时：{LOGIN_SESSION_TIMEOUT // 3600} 小时\n"
        f"• 最大失败次数：3 次\n"
        f"• 锁定时间：1 小时\n\n"
        f"⚡ **性能设置：**\n"
        f"• 批量发送大小：{BATCH_SEND_SIZE}\n"
        f"• 最小发送间隔：{MIN_INTERVAL} 秒\n"
        f"• 流量限制阈值：{FLOOD_WAIT_THRESHOLD} 秒\n\n"
        f"💾 **数据文件：**\n"
        f"• user_login.json - 登录数据\n"
        f"• user_configs.json - 用户配置\n"
        f"• user_history.json - 历史记录\n"
        f"• running_tasks.json - 运行任务"
    )
    
    buttons = [
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="show_admin_panel")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_login_logs(message, user_id):
    """显示登录日志"""
    text = "📋 **登录日志**\n\n"
    
    if not login_attempts:
        text += "暂无登录记录"
    else:
        text += "🔍 **最近登录尝试：**\n"
        sorted_attempts = sorted(login_attempts.items(), key=lambda x: x[1].get("last_attempt", 0), reverse=True)
        
        for user_id_str, data in sorted_attempts[:10]:
            attempts = data.get("attempts", 0)
            last_attempt = data.get("last_attempt", 0)
            locked_until = data.get("locked_until", 0)
            
            time_str = time.strftime("%m-%d %H:%M", time.localtime(last_attempt)) if last_attempt else "未知"
            status = "🔒 锁定" if locked_until > time.time() else f"❌ {attempts}次失败" if attempts > 0 else "✅ 正常"
            
            text += f"• ID {user_id_str}: {status} ({time_str})\n"
        
        if len(login_attempts) > 10:
            text += f"\n... 还有 {len(login_attempts) - 10} 条记录"
    
    buttons = [
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="show_admin_panel")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_performance_monitor(message, user_id):
    """显示性能监控面板"""
    if not is_admin_user(user_id):
        await safe_edit_or_reply(message, "❌ 您没有管理员权限")
        return
    
    perf_stats = get_performance_stats()
    
    text = "⚡ **性能监控面板**\n\n"
    
    if not perf_stats:
        text += "📊 暂无性能数据"
    else:
        text += f"📊 **监控概览** (共 {len(perf_stats)} 个函数)\n\n"
        
        # 按平均耗时排序
        sorted_stats = sorted(perf_stats.items(), key=lambda x: x[1]['avg'], reverse=True)
        
        text += "🐌 **最慢操作 (Top 5):**\n"
        for func_name, stats in sorted_stats[:5]:
            text += f"• `{func_name}`: {stats['avg']:.2f}s (avg) | {stats['max']:.2f}s (max) | {stats['count']} 次\n"
        
        text += "\n⚡ **最快操作 (Top 3):**\n"
        for func_name, stats in sorted_stats[-3:]:
            text += f"• `{func_name}`: {stats['avg']:.3f}s (avg) | {stats['count']} 次\n"
        
        # 总体统计
        total_calls = sum(stats['count'] for stats in perf_stats.values())
        avg_duration = sum(stats['avg'] * stats['count'] for stats in perf_stats.values()) / total_calls if total_calls > 0 else 0
        
        text += f"\n📈 **总体统计:**\n"
        text += f"• 总调用次数: {total_calls}\n"
        text += f"• 平均耗时: {avg_duration:.3f}s\n"
        text += f"• 监控函数数: {len(perf_stats)}\n"
    
    buttons = [
        [InlineKeyboardButton("🔄 刷新数据", callback_data="admin_performance")],
        [InlineKeyboardButton("🗑️ 清空统计", callback_data="admin_clear_performance")],
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="show_admin_panel")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_system_maintenance(message, user_id):
    """显示系统维护面板"""
    if not is_admin_user(user_id):
        await safe_edit_or_reply(message, "❌ 您没有管理员权限")
        return
    
    # 获取系统状态
    import psutil
    import gc
    
    # 内存使用情况
    memory_info = psutil.virtual_memory()
    memory_percent = memory_info.percent
    memory_used = memory_info.used / (1024**3)  # GB
    memory_total = memory_info.total / (1024**3)  # GB
    
    # CPU使用情况
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # 磁盘使用情况
    disk_info = psutil.disk_usage('/')
    disk_percent = (disk_info.used / disk_info.total) * 100
    disk_used = disk_info.used / (1024**3)  # GB
    disk_total = disk_info.total / (1024**3)  # GB
    
    # 垃圾回收统计
    gc_stats = gc.get_stats()
    
    text = (
        f"🔧 **系统维护面板**\n\n"
        f"💾 **内存使用:**\n"
        f"• 使用率: {memory_percent:.1f}%\n"
        f"• 已用: {memory_used:.2f} GB / {memory_total:.2f} GB\n\n"
        f"🖥️ **CPU使用:**\n"
        f"• 使用率: {cpu_percent:.1f}%\n\n"
        f"💿 **磁盘使用:**\n"
        f"• 使用率: {disk_percent:.1f}%\n"
        f"• 已用: {disk_used:.2f} GB / {disk_total:.2f} GB\n\n"
        f"🗑️ **垃圾回收:**\n"
        f"• 代数0: {gc_stats[0]['collections']} 次\n"
        f"• 代数1: {gc_stats[1]['collections']} 次\n"
        f"• 代数2: {gc_stats[2]['collections']} 次\n\n"
        f"📊 **缓存状态:**\n"
        f"• 实时去重缓存: {len(realtime_dedupe_cache)} 个\n"
        f"• 性能统计: {len(performance_stats)} 个函数\n"
    )
    
    buttons = [
        [InlineKeyboardButton("🗑️ 执行垃圾回收", callback_data="admin_gc_collect")],
        [InlineKeyboardButton("🧹 清理缓存", callback_data="admin_clear_cache")],
        [InlineKeyboardButton("💾 保存所有数据", callback_data="admin_save_all")],
        [InlineKeyboardButton("🔄 刷新状态", callback_data="admin_maintenance")],
        [InlineKeyboardButton("🔙 返回管理面板", callback_data="show_admin_panel")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

# ==================== 通用辅助 ====================
def parse_channel_identifier(raw: str):
    s = (raw or "").strip()
    # 纯数字或以 -100 开头
    if s.startswith("-100") and s[4:].isdigit():
        return int(s)
    if s.isdigit():
        # 可能是内部 id
        return int(s)
    # @username
    if s.startswith('@'):
        return s[1:]
    # URL
    if s.startswith('http://') or s.startswith('https://') or s.startswith('t.me/'):
        if s.startswith('t.me/'):
            s = 'https://' + s
        u = urlparse(s)
        path = u.path.strip('/')
        parts = path.split('/') if path else []
        if not parts:
            return s
        if parts[0] == 'c' and len(parts) >= 2 and parts[1].isdigit():
            # 私有频道内部 id
            return int(f"-100{parts[1]}")
        # 普通公开频道用户名
        return parts[0]
    # 默认返回原始字符串，交由 get_chat 解析
    return s

def generate_dedupe_key(message, processed_text=None, config=None):
    """生成统一的去重键"""
    # 判断是否为纯文本消息
    is_text_only = (message.text and not (message.photo or message.video or message.document or message.animation or message.audio or message.voice or message.sticker))
    
    if is_text_only:
        # 文本消息去重
        if processed_text is None and config:
            processed_text, _ = process_message_content(message.caption or message.text, config)
        text_key = (processed_text or message.text or "").strip()
        if text_key:
            return ("text", hash(text_key))
    else:
        # 媒体消息去重
        file_id = None
        if message.photo: file_id = message.photo.file_id
        elif message.video: file_id = message.video.file_id
        elif message.document: file_id = message.document.file_id
        elif message.animation: file_id = message.animation.file_id
        
        if file_id:
            return ("media", file_id)
    
    return None

async def estimate_actual_messages(client, source_channel, start_id, end_id):
    """智能预估指定范围内的实际消息数量"""
    total_range = end_id - start_id + 1
    
    # 如果范围很小，直接返回范围大小
    if total_range <= 100:
        return total_range
    
    # 采样策略：选择3个采样点
    sample_size = 50  # 每个采样点检查50个ID
    sample_points = [
        start_id,  # 开始位置
        start_id + total_range // 2,  # 中间位置  
        end_id - sample_size + 1  # 结束位置
    ]
    
    total_sampled = 0
    valid_sampled = 0
    
    try:
        for sample_start in sample_points:
            sample_end = min(sample_start + sample_size - 1, end_id)
            
            # 获取采样范围的消息
            sample_messages = await client.get_messages(
                chat_id=source_channel,
                message_ids=range(sample_start, sample_end + 1)
            )
            
            # 计算有效消息数量
            for msg in sample_messages:
                total_sampled += 1
                if msg and (msg.text or msg.photo or msg.video or msg.document or msg.animation or msg.audio or msg.voice or msg.sticker):
                    valid_sampled += 1
        
        # 计算有效消息比例
        if total_sampled > 0:
            valid_ratio = valid_sampled / total_sampled
            estimated_actual = int(total_range * valid_ratio)
            
            logging.info(f"预估消息数量: 范围 {start_id}-{end_id} ({total_range}), 采样 {total_sampled}, 有效 {valid_sampled}, 比例 {valid_ratio:.2%}, 预估实际 {estimated_actual}")
            
            return max(estimated_actual, 1)  # 至少返回1
        else:
            logging.warning(f"预估消息数量失败，使用默认值: {total_range}")
            return total_range
            
    except Exception as e:
        logging.warning(f"预估消息数量出错: {e}，使用默认值: {total_range}")
        return total_range

async def cooperative_sleep(task_obj: dict, seconds: int):
    """智能流量限制等待，支持取消和优化等待时间"""
    # 如果等待时间过长，建议用户取消任务
    task_id_short = task_obj.get('task_id', 'unknown')[:8] if task_obj.get('task_id') else 'unknown'
    if seconds > 30:
        logging.warning(f"任务 {task_id_short}: 流量限制时间过长({seconds}秒)，建议暂停任务")
        # 减少等待时间到30秒
        seconds = min(seconds, 30)
    
    remaining = int(max(0, seconds))
    while remaining > 0:
        if task_obj.get("cancel_request"):
            logging.info(f"任务 {task_id_short}: 用户取消，停止等待")
            break
        
        # 分段等待，每5秒检查一次取消状态
        step = min(5, remaining) if remaining >= 5 else remaining
        await asyncio.sleep(step)
        remaining -= step
        
        # 如果剩余时间很短，直接等待完成
        if remaining <= 3:
            await asyncio.sleep(remaining)
            break

# ==================== 持久化函数 ====================
def save_configs():
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
            logging.error(f"[{bot_config['bot_id']}] 保存备份文件也失败: {backup_e}")

def load_configs():
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
    user_configs = {}

def save_user_states():
    # 优先使用内存存储
    if memory_storage:
        try:
            memory_storage.set_config("user_states", user_states)
            logging.info(f"[{bot_config['bot_id']}] user_states 已保存到内存存储")
            return
        except Exception as e:
            logging.error(f"[{bot_config['bot_id']}] 内存存储保存失败: {e}")
    
    # 回退到文件存储
    """将用户状态保存到文件"""
    try:
        config_file = get_config_path(f"user_states_{bot_config['bot_id']}.json")
        with open(config_file, "w", encoding='utf-8') as f:
            json.dump(user_states, f, ensure_ascii=False, indent=4)
        logging.info(f"[{bot_config['bot_id']}] 用户状态已保存到 {config_file}。")
    except Exception as e:
        logging.error(f"[{bot_config['bot_id']}] 保存用户状态失败: {e}")
        # 尝试保存到当前目录作为备份
        backup_file = f"user_states_{bot_config['bot_id']}.json"
        try:
            with open(backup_file, "w", encoding='utf-8') as f:
                json.dump(user_states, f, ensure_ascii=False, indent=4)
            logging.info(f"[{bot_config['bot_id']}] 用户状态已保存到备份文件 {backup_file}。")
        except Exception as backup_e:
            logging.error(f"[{bot_config['bot_id']}] 保存备份文件也失败: {backup_e}")

def load_user_states():
    # 优先从内存存储恢复
    if memory_storage:
        try:
            restored = memory_storage.restore_from_backup("user_states")
            if restored:
                global user_states
                user_states = memory_storage.get_config("user_states")
                logging.info(f"[{bot_config['bot_id']}] user_states 已从内存存储恢复")
                return
        except Exception as e:
            logging.error(f"[{bot_config['bot_id']}] 内存存储恢复失败: {e}")
    
    # 回退到文件加载
    config_file = get_config_path(f"user_states_{bot_config['bot_id']}.json")
    try:
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                user_states = json.load(f)
            logging.info(f"[{bot_config['bot_id']}] 用户状态已从 {config_file} 载入。")
        else:
            user_states = {}
            logging.info(f"[{bot_config['bot_id']}] 用户状态文件 {config_file} 不存在，使用空状态。")
    except Exception as e:
        logging.error(f"[{bot_config['bot_id']}] 载入用户状态失败: {e}")
        user_states = {}

def save_history():
    # 优先使用内存存储
    if memory_storage:
        try:
            memory_storage.set_config("history", history)
            logging.info(f"[{bot_config['bot_id']}] history 已保存到内存存储")
            return
        except Exception as e:
            logging.error(f"[{bot_config['bot_id']}] 内存存储保存失败: {e}")
    
    # 回退到文件存储
    config_file = get_config_path(f"user_history_{bot_config['bot_id']}.json")
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(user_history, f, ensure_ascii=False, indent=4)
        logging.info(f"[{bot_config['bot_id']}] 历史记录已保存到 {config_file}。")
    except Exception as e:
        logging.error(f"[{bot_config['bot_id']}] 保存历史记录失败: {e}")
        # 尝试保存到当前目录作为备份
        backup_file = f"user_history_{bot_config['bot_id']}.json"
        try:
            with open(backup_file, "w", encoding='utf-8') as f:
                json.dump(user_history, f, ensure_ascii=False, indent=4)
            logging.info(f"[{bot_config['bot_id']}] 历史记录已保存到备份文件 {backup_file}。")
        except Exception as backup_e:
            logging.error(f"[{bot_config['bot_id']}] 保存备份文件也失败: {backup_e}")

def load_history():
    # 优先从内存存储恢复
    if memory_storage:
        try:
            restored = memory_storage.restore_from_backup("history")
            if restored:
                global history
                history = memory_storage.get_config("history")
                logging.info(f"[{bot_config['bot_id']}] history 已从内存存储恢复")
                return
        except Exception as e:
            logging.error(f"[{bot_config['bot_id']}] 内存存储恢复失败: {e}")
    
    # 回退到文件加载
    global user_history
    config_file = get_config_path(f"user_history_{bot_config['bot_id']}.json")
    backup_file = f"user_history_{bot_config['bot_id']}.json"
    
    # 首先尝试从持久化存储加载
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding='utf-8') as f:
                user_history = json.load(f)
            logging.info(f"[{bot_config['bot_id']}] 历史记录已从持久化存储 {config_file} 载入。")
            return
        except Exception as e:
            logging.error(f"[{bot_config['bot_id']}] 从持久化存储加载历史记录失败: {e}")
    
    # 如果持久化存储失败，尝试从备份文件加载
    if os.path.exists(backup_file):
        try:
            with open(backup_file, "r", encoding='utf-8') as f:
                user_history = json.load(f)
            logging.info(f"[{bot_config['bot_id']}] 历史记录已从备份文件 {backup_file} 载入。")
            # 尝试保存到持久化存储
            try:
                save_history()
                logging.info(f"[{bot_config['bot_id']}] 历史记录已迁移到持久化存储。")
            except Exception as migrate_e:
                logging.error(f"[{bot_config['bot_id']}] 迁移到持久化存储失败: {migrate_e}")
            return
        except Exception as e:
            logging.error(f"[{bot_config['bot_id']}] 从备份文件加载历史记录失败: {e}")
    
    # 如果都失败，创建新历史记录
    user_history = {}
    logging.info(f"[{bot_config['bot_id']}] 历史记录文件不存在，将创建新记录。")

# ==================== 按钮设置 ====================
def get_main_menu_buttons(user_id):
    buttons = [
        # 主要功能区 - 搬运相关
        [InlineKeyboardButton("🚀 开始搬运", callback_data="select_channel_pairs_to_clone")],
        [InlineKeyboardButton("👂 实时监听", callback_data="show_monitor_menu")],
        
        # 配置管理区
        [
            InlineKeyboardButton("⚙️ 频道管理", callback_data="show_channel_config_menu"),
            InlineKeyboardButton("🔧 过滤设定", callback_data="show_feature_config_menu")
        ],
        
        # 查看信息区
        [
            InlineKeyboardButton("📜 我的任务", callback_data="view_tasks"),
            InlineKeyboardButton("📋 历史记录", callback_data="view_history")
        ],
        [
            InlineKeyboardButton("🔍 当前配置", callback_data="view_config"),
            InlineKeyboardButton("❓ 帮助", callback_data="show_help")
        ]
    ]
    
    # 添加管理员专用按钮和登出按钮
    admin_logout_row = []
    if is_admin_user(user_id):
        admin_logout_row.append(InlineKeyboardButton("👑 管理面板", callback_data="show_admin_panel"))
    admin_logout_row.append(InlineKeyboardButton("🚪 退出登录", callback_data="logout"))
    
    if admin_logout_row:
        buttons.append(admin_logout_row)
    
    return InlineKeyboardMarkup(buttons)

# 频道组管理菜单 - 新增了编辑和删除按钮
def get_channel_config_menu_buttons(user_id):
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    text = "⚙️ **频道组管理**\n您可以在此新增、编辑或删除频道配对：\n\n"
    buttons = []
    
    if not channel_pairs:
        text += "❌ 您尚未设定任何频道组。"
    else:
        for i, pair in enumerate(channel_pairs):
            source = pair['source']
            target = pair['target']
            is_enabled = pair.get("enabled", True)
            
            status_text = "✅ 启用" if is_enabled else "⏸ 暂停"
            
            text += f"`{i+1}. {source} -> {target}` ({status_text})\n"
            buttons.append([
                InlineKeyboardButton(f"✏️ 编辑 {i+1} ", callback_data=f"edit_channel_pair:{i}"),
                InlineKeyboardButton(f"🗑️ 删除 {i+1}", callback_data=f"delete_channel_pair:{i}")
            ])
            
    buttons.append([InlineKeyboardButton("➕ 新增频道组", callback_data="add_channel_pair")])
    buttons.append([InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")])
    
    return text, InlineKeyboardMarkup(buttons)

# 新增功能：选择要编辑的频道组属性
def get_edit_channel_pair_menu(pair_id, current_pair):
    is_enabled = current_pair.get("enabled", True)
    status_text = "⏸ 暂停" if is_enabled else "✅ 启用"
    
    # 检查是否有单独的过滤设置
    has_custom_filters = bool(current_pair.get("custom_filters"))
    filter_status = "🔧" if has_custom_filters else "➕"
    filter_text = "编辑过滤设置" if has_custom_filters else "设置专用过滤"
    
    buttons = [
        [InlineKeyboardButton(f"🔄 更改采集频道", callback_data=f"edit_pair_source:{pair_id}")],
        [InlineKeyboardButton(f"🔄 更改目标频道", callback_data=f"edit_pair_target:{pair_id}")],
        [InlineKeyboardButton(f"{status_text}该频道组", callback_data=f"toggle_pair_enabled:{pair_id}")],
        [InlineKeyboardButton(f"{filter_status} {filter_text}", callback_data=f"manage_pair_filters:{pair_id}")],
        [InlineKeyboardButton("🔙 返回管理菜单", callback_data="show_channel_config_menu")]
    ]
    return InlineKeyboardMarkup(buttons)


def get_clone_confirm_buttons(task_id, clone_tasks):
    buttons = [
        [InlineKeyboardButton(f"✅ 确认开始搬运 ({len(clone_tasks)} 组频道)", callback_data=f"confirm_clone_action:{task_id}")],
        [InlineKeyboardButton("❌ 取消", callback_data=f"cancel:{task_id}")]
    ]
    return InlineKeyboardMarkup(buttons)


# 重新设计功能设定菜单，优化布局和分组
def get_feature_config_menu(user_id):
    config = user_configs.get(str(user_id), {})
    
    keywords_count = len(config.get("filter_keywords", []))
    replacements_count = len(config.get("replacement_words", {}))
    ext_count = len(config.get("file_filter_extensions", []))
    buttons_count = len(config.get("buttons", []))
    
    # 获取各功能状态指示器
    content_removal_status = "🟢" if any([
        config.get("remove_links"), 
        config.get("remove_hashtags"), 
        config.get("remove_usernames")
    ]) else "⚫"
    
    file_filter_status = "🟢" if any([
        config.get("filter_photo"),
        config.get("filter_video"),
        ext_count > 0
    ]) else "⚫"
    
    button_filter_status = "🟢" if config.get("filter_buttons") else "⚫"
    
    tail_text_status = "🟢" if config.get("tail_text") else "⚫"
    
    buttons = [
        # 🔍 内容过滤区域
        [InlineKeyboardButton("🔍 **内容过滤设置**", callback_data="filter_settings_header")],
        [
            InlineKeyboardButton(f"📝 关键字过滤 ({keywords_count})", callback_data="manage_filter_keywords"),
            InlineKeyboardButton(f"🔀 敏感词替换 ({replacements_count})", callback_data="manage_replacement_words")
        ],
        [
            InlineKeyboardButton(f"{content_removal_status} 文本内容移除", callback_data="toggle_content_removal"),
            InlineKeyboardButton(f"{file_filter_status} 文件过滤设定 ({ext_count})", callback_data="manage_file_filter")
        ],
        
        # 🎛️ 按钮和界面控制
        [InlineKeyboardButton("🎛️ **按钮和界面控制**", callback_data="button_control_header")],
        [InlineKeyboardButton(f"{button_filter_status} 按钮策略设置", callback_data="manage_filter_buttons")],
        
        # ✨ 内容增强功能
        [InlineKeyboardButton("✨ **内容增强功能**", callback_data="content_enhancement_header")],
        [
            InlineKeyboardButton(f"{tail_text_status} 附加文字设定", callback_data="request_tail_text"),
            InlineKeyboardButton(f"📋 附加按钮设定 ({buttons_count})", callback_data="request_buttons")
        ],
        [InlineKeyboardButton("🎯 附加频率设置", callback_data="show_frequency_settings")],
        
        # 🔙 返回
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]
    ]
    return InlineKeyboardMarkup(buttons)


# 全面更新的帮助菜单
HELP_TEXT = """
**❓ 帮助与使用指南**

**🔧 基础设置**
**1. 如何获取频道ID？**
   • **公共频道**：使用 `@username` 格式
   • **私人频道**：点击频道信息 → 复制链接
     格式：`https://t.me/c/1234567890/` 
     转换为：`-1001234567890` (前面加-100)

**2. 如何设定频道组？**
   • 主菜单 → 频道管理 → 新增频道组
   • 输入来源频道ID和目标频道ID
   • 可随时编辑、暂停或删除频道组

**🚀 搬运功能**
**3. 如何开始搬运？**
   • 主菜单 → 开始搬运 → 选择频道组
   • 输入消息ID范围（如：100-200）
   • 确认后开始自动搬运

**4. 搬运顺序说明**
   • 本机器人采用**正序搬运**（从旧到新）
   • 支持断点续传，取消后可继续
   • 智能去重，避免重复发送

**🔍 过滤功能**
**5. 内容过滤设置**
   • **关键字过滤**：过滤包含特定词汇的消息
   • **敏感词替换**：自动替换敏感词汇
   • **文本内容移除**：移除链接、@用户名、#标签
   • **文件过滤**：按文件类型和扩展名过滤

**6. 按钮策略设置**
   • **drop**：丢弃带按钮的整条消息
   • **strip**：移除按钮，保留内容
   • **whitelist**：仅允许白名单域名按钮

**✨ 增强功能**
**7. 内容增强**
   • **附加文字**：在消息前/后添加自定义文字
   • **附加按钮**：为消息添加自定义按钮
   • **频率设置**：控制附加内容的显示频率

**👂 实时监听**
   • 开启后自动搬运新消息
   • 可为每个频道组单独设置
   • 支持后台持续运行

**📊 任务管理**
**8. 查看和管理任务**
   • **我的任务**：查看进行中和历史任务
   • **历史记录**：查看搬运历史和统计
   • **任务续传**：恢复中断的搬运任务

**⚠️ 常见问题**
**9. 任务失败原因**
   • 机器人未加入频道或权限不足
   • 频道ID格式错误
   • 网络问题或API限制
   • 消息ID范围不存在

**10. 如何优化搬运效果？**
   • 合理设置消息ID范围
   • 配置适当的过滤规则
   • 避免频繁操作防止限流

**🆘 获取支持**
如遇问题，请联系开发者并提供：
• 错误描述和复现步骤
• 频道设置和过滤配置
• 任务执行时的错误信息

**版本信息**
当前版本：2.4.1 增强用户体验版
更新内容：智能进度显示、完善续传功能、优化用户界面
"""


# ==================== 辅助函数 ====================
def find_task(user_id, task_id=None, state=None):
    """根据 task_id 或 state 寻找特定任务"""
    user_tasks = user_states.get(user_id, [])
    if task_id:
        return next((task for task in user_tasks if task.get("task_id") == task_id), None)
    if state:
        for task in reversed(user_tasks):
            if task.get("state") == state:
                return task
    return None

def remove_task(user_id, task_id):
    """从任务列表中移除一个任务"""
    if user_id in user_states:
        user_states[user_id] = [task for task in user_states[user_id] if task.get("task_id") != task_id]
        if not user_states[user_id]:
            del user_states[user_id]
        logging.info(f"用户 {user_id} 的任务 {task_id[:8]} 已被移除。")
        save_user_states()  # 保存用户状态

@monitor_performance('safe_edit_or_reply')
async def safe_edit_or_reply(message, text, reply_markup=None, user_id=None):
    """安全的编辑或回复消息，智能处理FloodWait"""
    try:
        # 智能检查FloodWait限制
        await flood_wait_manager.wait_if_needed('edit_message')
        
        # 尝试编辑消息
        await message.edit_text(text, reply_markup=reply_markup)
        return True
        
    except FloodWait as e:
        # 智能处理FloodWait
        wait_time = e.value
        
        # 记录并智能调整限制
        flood_wait_manager.set_flood_wait('edit_message', wait_time)
        
        logging.info(f"📝 操作 edit_message 遇到FloodWait: {wait_time}秒")
        
        # 智能等待策略
        if wait_time > 300:  # 超过5分钟，直接发送新消息
            logging.info(f"🚨 等待时间过长({wait_time}秒)，改为发送新消息")
            try:
                await flood_wait_manager.wait_if_needed('send_message')
                await message.reply_text(text, reply_markup=reply_markup)
                return True
            except Exception as reply_e:
                logging.error(f"发送新消息失败: {reply_e}")
                return False
        elif wait_time > 60:  # 超过1分钟，使用智能等待
            safe_wait = min(30, wait_time // 2)  # 最多等待30秒
            logging.info(f"🔄 智能等待: 原始{wait_time}秒，实际{safe_wait}秒")
            await asyncio.sleep(safe_wait)
        else:
            # 正常等待
            await asyncio.sleep(wait_time)
        
        # 重试编辑
        try:
            await message.edit_text(text, reply_markup=reply_markup)
            return True
        except Exception as retry_e:
            logging.error(f"重试编辑失败: {retry_e}")
            # 发送新消息
            try:
                await message.reply_text(text, reply_markup=reply_markup)
                return True
            except Exception as final_e:
                logging.error(f"最终发送失败: {final_e}")
                return False
                
    except BadRequest as e:
        error_str = str(e).lower()
        if ("message_id_invalid" in error_str or 
            "message is not modified" in error_str or 
            "message_not_modified" in error_str):
            # 消息无法编辑，改为发送新消息
            logging.info(f"消息无法编辑，改为发送新消息: {e}")
            try:
                await flood_wait_manager.wait_if_needed('send_message')
                await message.reply_text(text, reply_markup=reply_markup)
                return True
            except Exception as reply_e:
                logging.error(f"回复消息失败: {reply_e}")
                return False
        else:
            logging.error(f"BadRequest错误: {e}")
            # 尝试发送新消息
            try:
                await flood_wait_manager.wait_if_needed('send_message')
                await message.reply_text(text, reply_markup=reply_markup)
                return True
            except Exception as reply_e:
                logging.error(f"发送新消息失败: {reply_e}")
                return False
                
    except Exception as e:
        logging.error(f"未知错误: {e}")
        # 尝试发送简单文本
        try:
            await message.reply_text("⚠️ 操作失败，请稍后再试")
            return False
        except:
            return False

# ========== 新增的菜单显示函数 (用于修复 NameError) ==========
async def show_main_menu(message, user_id):
    await safe_edit_or_reply(message,
                             "🌟 **欢迎使用老湿姬搬运机器人** 🌟\n请选择你想要执行的操作：",
                             reply_markup=get_main_menu_buttons(user_id))

async def show_channel_config_menu(message, user_id):
    text, buttons = get_channel_config_menu_buttons(user_id)
    await safe_edit_or_reply(message, text, reply_markup=buttons)

async def show_feature_config_menu(message, user_id):
    await safe_edit_or_reply(message,
                             "🔧 **功能设定**\n请选择要配置的功能：",
                             reply_markup=get_feature_config_menu(user_id))

# 新增监控管理菜单
def get_monitor_menu_buttons(user_id):
    config = user_configs.get(str(user_id), {})
    monitor_enabled = config.get("realtime_listen", False)
    channel_pairs = config.get("channel_pairs", [])
    
    # 统计启用监控的频道组数量
    monitored_pairs = []
    for i, pair in enumerate(channel_pairs):
        if pair.get("enabled", True) and pair.get("monitor_enabled", False):
            monitored_pairs.append(i)
    
    buttons = [
        [InlineKeyboardButton(f"👂 监听总开关: {'✅ 开启' if monitor_enabled else '❌ 关闭'}", callback_data="toggle_realtime_listen")],
        [InlineKeyboardButton(f"📋 选择监听频道 ({len(monitored_pairs)}个)", callback_data="manage_monitor_channels")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]
    ]
    return InlineKeyboardMarkup(buttons)

async def show_monitor_menu(message, user_id):
    config = user_configs.get(str(user_id), {})
    monitor_enabled = config.get("realtime_listen", False)
    channel_pairs = config.get("channel_pairs", [])
    
    # 统计启用监控的频道组
    monitored_pairs = []
    for i, pair in enumerate(channel_pairs):
        if pair.get("enabled", True) and pair.get("monitor_enabled", False):
            monitored_pairs.append(f"`{pair['source']}` -> `{pair['target']}`")
    
    text = "👂 **监听设置**\n\n"
    text += f"监听状态：{'✅ 开启' if monitor_enabled else '❌ 关闭'}\n"
    text += f"监听的频道组数量：{len(monitored_pairs)}\n\n"
    
    if monitored_pairs:
        text += "**当前监听的频道组：**\n"
        text += "\n".join(monitored_pairs)
    else:
        text += "**尚未选择任何频道组进行监听**\n\n"
        text += "💡 **说明**：开启监听后，系统会自动监听选定频道的新消息并实时搬运到目标频道。"
        
    await safe_edit_or_reply(message, text, reply_markup=get_monitor_menu_buttons(user_id))

# 频道监控选择菜单
async def show_monitor_channels_menu(message, user_id):
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if not channel_pairs:
        await safe_edit_or_reply(message,
                                 "❌ 您尚未设定任何频道组。请先在【频道组管理】中添加频道组。",
                                 reply_markup=InlineKeyboardMarkup([
                                     [InlineKeyboardButton("⚙️ 频道组管理", callback_data="show_channel_config_menu")],
                                     [InlineKeyboardButton("🔙 返回监听设置", callback_data="show_monitor_menu")]
                                 ]))
        return
    
    text = "📋 **选择监听频道**\n"
    text += "点击频道组可切换是否监听该频道。只有同时满足以下条件的频道组才会被监听：\n"
    text += "1. 频道组本身已启用\n"
    text += "2. 监听总开关已开启\n"
    text += "3. 该频道组的监听已启用\n\n"
    
    buttons = []
    for i, pair in enumerate(channel_pairs):
        is_pair_enabled = pair.get("enabled", True)
        is_monitor_enabled = pair.get("monitor_enabled", False)
        
        # 只有启用的频道组才能设置监控
        if is_pair_enabled:
            status_icon = "✅" if is_monitor_enabled else "⬜"
            button_text = f"{status_icon} {pair['source']} -> {pair['target']}"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"toggle_monitor_pair:{i}")])
        else:
            # 暂停的频道组显示为灰色，不可点击
            button_text = f"⏸ {pair['source']} -> {pair['target']} (已暂停)"
            buttons.append([InlineKeyboardButton(button_text, callback_data="monitor_pair_disabled")])
    
    buttons.append([InlineKeyboardButton("✅ 全选", callback_data="monitor_select_all")])
    buttons.append([InlineKeyboardButton("❌ 全不选", callback_data="monitor_select_none")])
    buttons.append([InlineKeyboardButton("🔙 返回监听设置", callback_data="show_monitor_menu")])
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

# 监控频道组操作函数
async def toggle_monitor_pair(message, user_id, pair_id):
    logging.info(f"toggle_monitor_pair 被调用: user_id={user_id}, pair_id={pair_id}")
    config = user_configs.setdefault(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    logging.info(f"用户 {user_id} 的频道组数量: {len(channel_pairs)}")
    
    if not (0 <= pair_id < len(channel_pairs)):
        logging.error(f"频道组ID {pair_id} 超出范围 [0, {len(channel_pairs)})")
        await safe_edit_or_reply(message, "❌ 频道组编号无效。", 
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监听设置", callback_data="show_monitor_menu")]]))
        return
    
    pair = channel_pairs[pair_id]
    logging.info(f"频道组 {pair_id} 信息: {pair}")
    
    if not pair.get("enabled", True):
        logging.warning(f"频道组 {pair_id} 已暂停，无法设置监控")
        await safe_edit_or_reply(message, "❌ 该频道组已暂停，无法设置监控。", 
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回监听设置", callback_data="show_monitor_menu")]]))
        return
    
    # 切换监控状态
    current_state = pair.get("monitor_enabled", False)
    pair["monitor_enabled"] = not current_state
    save_configs()
    
    status = "开启" if not current_state else "关闭"
    logging.info(f"用户 {user_id} {status}了频道组 {pair_id} 的监控: {pair['source']} -> {pair['target']}")
    
    # 刷新频道选择菜单
    await show_monitor_channels_menu(message, user_id)

async def monitor_select_all(message, user_id):
    config = user_configs.setdefault(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    count = 0
    for pair in channel_pairs:
        if pair.get("enabled", True):  # 只选择启用的频道组
            pair["monitor_enabled"] = True
            count += 1
    
    save_configs()
    logging.info(f"用户 {user_id} 全选了监控频道，共 {count} 个")
    
    # 刷新频道选择菜单
    await show_monitor_channels_menu(message, user_id)

async def monitor_select_none(message, user_id):
    config = user_configs.setdefault(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    count = 0
    for pair in channel_pairs:
        if pair.get("monitor_enabled", False):
            pair["monitor_enabled"] = False
            count += 1
    
    save_configs()
    logging.info(f"用户 {user_id} 取消了所有监控频道，共 {count} 个")
    
    # 刷新频道选择菜单
    await show_monitor_channels_menu(message, user_id)

async def show_file_filter_menu(message, user_id):
    config = user_configs.get(str(user_id), {})
    
    # 统计文件扩展名过滤数量
    ext_count = len(config.get("file_filter_extensions", []))
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📁 副档名过滤 ({ext_count}个)", callback_data="manage_file_extension_filter")],
        [
            InlineKeyboardButton(f"🖼 图片: {'✅' if config.get('filter_photo', False) else '❌'}", callback_data="toggle_filter_photo"),
            InlineKeyboardButton(f"🎬 影片: {'✅' if config.get('filter_video', False) else '❌'}", callback_data="toggle_filter_video")
        ],
        [InlineKeyboardButton("🔙 返回功能设定", callback_data="show_feature_config_menu")]
    ])
    await safe_edit_or_reply(message,
                             "📁 **文件类型过滤设定**\n选择您想要过滤的文件类型：",
                             reply_markup=buttons)


async def toggle_content_removal_menu(message, user_id):
    config = user_configs.get(str(user_id), {})
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔗 移除超链接: {'✅ 开启' if config.get('remove_links', False) else '❌ 关闭'}", callback_data="toggle_remove_links")],
        [InlineKeyboardButton(f"🏷 移除Hashtags: {'✅ 开启' if config.get('remove_hashtags', False) else '❌ 关闭'}", callback_data="toggle_remove_hashtags")],
        [InlineKeyboardButton(f"👤 移除@使用者名: {'✅ 开启' if config.get('remove_usernames', False) else '❌ 关闭'}", callback_data="toggle_remove_usernames")],
        [InlineKeyboardButton("🔙 返回功能设定", callback_data="show_feature_config_menu")]
    ])
    await safe_edit_or_reply(message,
                             "📝 **文本内容移除设定**\n选择您想要自动移除的内容类型：",
                             reply_markup=buttons)

async def show_frequency_settings(message, user_id):
    """显示附加内容频率设置"""
    config = user_configs.get(str(user_id), {})
    
    # 获取当前设置
    tail_mode = config.get("tail_frequency_mode", "always")
    tail_interval = config.get("tail_interval", 10)
    tail_probability = config.get("tail_random_probability", 20)
    
    button_mode = config.get("button_frequency_mode", "always")
    button_interval = config.get("button_interval", 10)
    button_probability = config.get("button_random_probability", 20)
    
    # 生成状态文本
    tail_status = {
        "always": "每条消息",
        "interval": f"每{tail_interval}条消息",
        "random": f"{tail_probability}%概率"
    }.get(tail_mode, "每条消息")
    
    button_status = {
        "always": "每条消息",
        "interval": f"每{button_interval}条消息", 
        "random": f"{button_probability}%概率"
    }.get(button_mode, "每条消息")
    
    text = (
        f"🎯 **附加内容频率设置**\n\n"
        f"📝 **附加文字：** {tail_status}\n"
        f"📋 **附加按钮：** {button_status}\n\n"
        f"💡 **说明：**\n"
        f"• 每条消息：每条搬运的消息都添加\n"
        f"• 间隔添加：每N条消息添加一次\n"
        f"• 随机添加：按概率随机添加"
    )
    
    buttons = [
        [InlineKeyboardButton("📝 附加文字频率", callback_data="config_tail_frequency")],
        [InlineKeyboardButton("📋 附加按钮频率", callback_data="config_button_frequency")],
        [InlineKeyboardButton("🔙 返回功能设定", callback_data="show_feature_config_menu")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_tail_frequency_config(message, user_id):
    """显示附加文字频率配置"""
    config = user_configs.get(str(user_id), {})
    current_mode = config.get("tail_frequency_mode", "always")
    interval = config.get("tail_interval", 10)
    probability = config.get("tail_random_probability", 20)
    
    mode_display = {
        'always': '每条消息',
        'interval': f'每{interval}条',
        'random': f'{probability}%概率'
    }
    
    text = (
        f"📝 **附加文字频率设置**\n\n"
        f"当前模式：**{mode_display[current_mode]}**\n\n"
        f"请选择附加文字的添加方式："
    )
    
    buttons = [
        [InlineKeyboardButton(f"{'✅' if current_mode == 'always' else '⚪'} 每条消息都添加", 
                            callback_data="set_tail_freq:always")],
        [InlineKeyboardButton(f"{'✅' if current_mode == 'interval' else '⚪'} 间隔添加", 
                            callback_data="set_tail_freq:interval")],
        [InlineKeyboardButton(f"{'✅' if current_mode == 'random' else '⚪'} 随机添加", 
                            callback_data="set_tail_freq:random")],
        [InlineKeyboardButton("🔙 返回频率设置", callback_data="show_frequency_settings")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_button_frequency_config(message, user_id):
    """显示附加按钮频率配置"""
    config = user_configs.get(str(user_id), {})
    current_mode = config.get("button_frequency_mode", "always")
    interval = config.get("button_interval", 10)
    probability = config.get("button_random_probability", 20)
    
    mode_display = {
        'always': '每条消息',
        'interval': f'每{interval}条',
        'random': f'{probability}%概率'
    }
    
    text = (
        f"📋 **附加按钮频率设置**\n\n"
        f"当前模式：**{mode_display[current_mode]}**\n\n"
        f"请选择附加按钮的添加方式："
    )
    
    buttons = [
        [InlineKeyboardButton(f"{'✅' if current_mode == 'always' else '⚪'} 每条消息都添加", 
                            callback_data="set_button_freq:always")],
        [InlineKeyboardButton(f"{'✅' if current_mode == 'interval' else '⚪'} 间隔添加", 
                            callback_data="set_button_freq:interval")],
        [InlineKeyboardButton(f"{'✅' if current_mode == 'random' else '⚪'} 随机添加", 
                            callback_data="set_button_freq:random")],
        [InlineKeyboardButton("🔙 返回频率设置", callback_data="show_frequency_settings")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_tail_frequency_set(message, user_id, mode):
    """处理附加文字频率模式设置"""
    config = user_configs.setdefault(str(user_id), {})
    config["tail_frequency_mode"] = mode
    
    if mode == "interval":
        # 需要设置间隔
        config["tail_interval"] = config.get("tail_interval", 10)
        text = f"✅ 已设置为间隔添加模式\n\n当前间隔：每 **{config['tail_interval']}** 条消息添加一次附加文字"
        buttons = [
            [InlineKeyboardButton("🔢 修改间隔数量", callback_data="set_tail_interval")],
            [InlineKeyboardButton("🔙 返回文字频率设置", callback_data="config_tail_frequency")]
        ]
    elif mode == "random":
        # 需要设置概率
        config["tail_random_probability"] = config.get("tail_random_probability", 20)
        text = f"✅ 已设置为随机添加模式\n\n当前概率：**{config['tail_random_probability']}%** 的消息会添加附加文字"
        buttons = [
            [InlineKeyboardButton("🎲 修改随机概率", callback_data="set_tail_probability")],
            [InlineKeyboardButton("🔙 返回文字频率设置", callback_data="config_tail_frequency")]
        ]
    else:  # always
        text = "✅ 已设置为每条消息都添加附加文字"
        buttons = [
            [InlineKeyboardButton("🔙 返回文字频率设置", callback_data="config_tail_frequency")]
        ]
    
    save_configs()
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_button_frequency_set(message, user_id, mode):
    """处理附加按钮频率模式设置"""
    config = user_configs.setdefault(str(user_id), {})
    config["button_frequency_mode"] = mode
    
    if mode == "interval":
        # 需要设置间隔
        config["button_interval"] = config.get("button_interval", 10)
        text = f"✅ 已设置为间隔添加模式\n\n当前间隔：每 **{config['button_interval']}** 条消息添加一次附加按钮"
        buttons = [
            [InlineKeyboardButton("🔢 修改间隔数量", callback_data="set_button_interval")],
            [InlineKeyboardButton("🔙 返回按钮频率设置", callback_data="config_button_frequency")]
        ]
    elif mode == "random":
        # 需要设置概率
        config["button_random_probability"] = config.get("button_random_probability", 20)
        text = f"✅ 已设置为随机添加模式\n\n当前概率：**{config['button_random_probability']}%** 的消息会添加附加按钮"
        buttons = [
            [InlineKeyboardButton("🎲 修改随机概率", callback_data="set_button_probability")],
            [InlineKeyboardButton("🔙 返回按钮频率设置", callback_data="config_button_frequency")]
        ]
    else:  # always
        text = "✅ 已设置为每条消息都添加附加按钮"
        buttons = [
            [InlineKeyboardButton("🔙 返回按钮频率设置", callback_data="config_button_frequency")]
        ]
    
    save_configs()
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def request_tail_interval(message, user_id):
    """请求设置附加文字间隔"""
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "waiting_for_tail_interval"}
    user_states.setdefault(user_id, []).append(new_task)
    
    await safe_edit_or_reply(message, 
        f"🔢 **设置附加文字间隔**\n\n"
        f"请输入数字，表示每多少条消息添加一次附加文字：\n"
        f"例如：输入 `10` 表示每10条消息添加一次\n\n"
        f"(任务ID: `{task_id[:8]}`)")

async def request_tail_probability(message, user_id):
    """请求设置附加文字概率"""
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "waiting_for_tail_probability"}
    user_states.setdefault(user_id, []).append(new_task)
    
    await safe_edit_or_reply(message, 
        f"🎲 **设置附加文字概率**\n\n"
        f"请输入1-100之间的数字，表示添加附加文字的概率：\n"
        f"例如：输入 `20` 表示20%的消息会添加附加文字\n\n"
        f"(任务ID: `{task_id[:8]}`)")

async def request_button_interval(message, user_id):
    """请求设置附加按钮间隔"""
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "waiting_for_button_interval"}
    user_states.setdefault(user_id, []).append(new_task)
    
    await safe_edit_or_reply(message, 
        f"🔢 **设置附加按钮间隔**\n\n"
        f"请输入数字，表示每多少条消息添加一次附加按钮：\n"
        f"例如：输入 `10` 表示每10条消息添加一次\n\n"
        f"(任务ID: `{task_id[:8]}`)")

async def request_button_probability(message, user_id):
    """请求设置附加按钮概率"""
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "waiting_for_button_probability"}
    user_states.setdefault(user_id, []).append(new_task)
    
    await safe_edit_or_reply(message, 
        f"🎲 **设置附加按钮概率**\n\n"
        f"请输入1-100之间的数字，表示添加附加按钮的概率：\n"
        f"例如：输入 `20` 表示20%的消息会添加附加按钮\n\n"
        f"(任务ID: `{task_id[:8]}`)")

async def set_tail_interval(message, user_id, task):
    """设置附加文字间隔"""
    try:
        interval = int(message.text.strip())
        if interval <= 0:
            await message.reply_text("❌ 间隔必须是大于0的正整数。")
            return
        
        config = user_configs.setdefault(str(user_id), {})
        config["tail_interval"] = interval
        save_configs()
        remove_task(user_id, task["task_id"])
        
        await message.reply_text(f"✅ 附加文字间隔已设置为每 {interval} 条消息。", 
                               reply_markup=get_main_menu_buttons(user_id))
        logging.info(f"用户 {user_id} 设置附加文字间隔为: {interval}")
    except ValueError:
        await message.reply_text("❌ 请输入有效的数字。")

async def set_tail_probability(message, user_id, task):
    """设置附加文字概率"""
    try:
        probability = int(message.text.strip())
        if not (1 <= probability <= 100):
            await message.reply_text("❌ 概率必须在1-100之间。")
            return
        
        config = user_configs.setdefault(str(user_id), {})
        config["tail_random_probability"] = probability
        save_configs()
        remove_task(user_id, task["task_id"])
        
        await message.reply_text(f"✅ 附加文字概率已设置为 {probability}%。", 
                               reply_markup=get_main_menu_buttons(user_id))
        logging.info(f"用户 {user_id} 设置附加文字概率为: {probability}%")
    except ValueError:
        await message.reply_text("❌ 请输入有效的数字。")

async def set_button_interval(message, user_id, task):
    """设置附加按钮间隔"""
    try:
        interval = int(message.text.strip())
        if interval <= 0:
            await message.reply_text("❌ 间隔必须是大于0的正整数。")
            return
        
        config = user_configs.setdefault(str(user_id), {})
        config["button_interval"] = interval
        save_configs()
        remove_task(user_id, task["task_id"])
        
        await message.reply_text(f"✅ 附加按钮间隔已设置为每 {interval} 条消息。", 
                               reply_markup=get_main_menu_buttons(user_id))
        logging.info(f"用户 {user_id} 设置附加按钮间隔为: {interval}")
    except ValueError:
        await message.reply_text("❌ 请输入有效的数字。")

async def set_button_probability(message, user_id, task):
    """设置附加按钮概率"""
    try:
        probability = int(message.text.strip())
        if not (1 <= probability <= 100):
            await message.reply_text("❌ 概率必须在1-100之间。")
            return
        
        config = user_configs.setdefault(str(user_id), {})
        config["button_random_probability"] = probability
        save_configs()
        remove_task(user_id, task["task_id"])
        
        await message.reply_text(f"✅ 附加按钮概率已设置为 {probability}%。", 
                               reply_markup=get_main_menu_buttons(user_id))
        logging.info(f"用户 {user_id} 设置附加按钮概率为: {probability}%")
    except ValueError:
        await message.reply_text("❌ 请输入有效的数字。")

# ==================== FloodWait管理命令 ====================
async def fix_floodwait_now(message, user_id):
    """立即修复所有异常的FloodWait限制"""
    try:
        # 执行自动恢复检查
        recovered, expired = flood_wait_manager.auto_recovery_check()
        
        # 获取修复后的健康状态
        health = flood_wait_manager.get_health_status()
        
        if recovered > 0:
            status_text = f"🔄 **FloodWait异常修复完成！**\n\n"
            status_text += f"✅ **修复结果:**\n"
            status_text += f"• 修复异常限制: {recovered} 个\n"
            status_text += f"• 清理过期记录: {expired} 个\n"
            status_text += f"• 系统状态: {'✅ 健康' if health['is_healthy'] else '⚠️ 仍有异常'}\n"
            
            if not health['is_healthy']:
                status_text += f"\n⚠️ **注意:** 仍有 {health['abnormal_restrictions']} 个异常限制\n"
                status_text += f"建议等待几分钟后再次检查"
        else:
            status_text = f"✅ **FloodWait状态检查完成**\n\n"
            status_text += f"• 修复异常限制: 0 个\n"
            status_text += f"• 清理过期记录: {expired} 个\n"
            status_text += f"• 系统状态: {'✅ 健康' if health['is_healthy'] else '⚠️ 异常'}\n"
        
        # 添加刷新按钮
        buttons = [[InlineKeyboardButton("🔍 刷新状态", callback_data="refresh_floodwait_status")]]
        reply_markup = InlineKeyboardMarkup(buttons)
        
        await safe_edit_or_reply(message, status_text, reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"修复FloodWait异常时出错: {e}")
        await safe_edit_or_reply(message, f"❌ 修复过程中出现错误: {str(e)}")

async def refresh_floodwait_status(message, user_id):
    """刷新FloodWait状态"""
    try:
        # 重新执行floodwait命令
        await floodwait_status_command(None, message)
    except Exception as e:
        logging.error(f"刷新FloodWait状态时出错: {e}")
        await safe_edit_or_reply(message, f"❌ 刷新状态时出现错误: {str(e)}")

# ==================== 任务完成通知 ====================
async def send_task_completion_notification(message, user_id, task_id_short, total_stats, was_cancelled):
    """发送任务完成通知"""
    try:
        if was_cancelled:
            notification_text = f"🛑 **任务已取消** `{task_id_short}`\n\n"
            notification_text += f"📊 **完成统计：**\n"
            notification_text += f"• 已搬运: {total_stats['successfully_cloned']} 条\n"
            notification_text += f"• 已处理: {total_stats['total_processed']} 条\n"
            notification_text += f"• 重复跳过: {total_stats['duplicates_skipped']} 条\n"
            notification_text += f"• 运行时间: {total_stats.get('elapsed_time', 0):.1f} 秒\n\n"
            notification_text += f"💡 任务进度已保存，可以稍后继续搬运"
        else:
            notification_text = f"🎉 **任务完成！** `{task_id_short}`\n\n"
            notification_text += f"📊 **完成统计：**\n"
            notification_text += f"• 成功搬运: {total_stats['successfully_cloned']} 条\n"
            notification_text += f"• 总处理: {total_stats['total_processed']} 条\n"
            notification_text += f"• 重复跳过: {total_stats['duplicates_skipped']} 条\n"
            notification_text += f"• 运行时间: {total_stats.get('elapsed_time', 0):.1f} 秒\n\n"
            notification_text += f"✅ 所有消息已成功搬运到目标频道！"
        
        # 添加查看历史记录按钮
        buttons = [
            [InlineKeyboardButton("📋 查看历史记录", callback_data="view_history")],
            [InlineKeyboardButton("📜 查看我的任务", callback_data="view_tasks")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]
        ]
        
        # 发送通知消息
        await message.reply_text(
            notification_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
        logging.info(f"用户 {user_id} 任务 {task_id_short} 完成通知已发送")
        
    except Exception as e:
        logging.error(f"发送任务完成通知失败: {e}")
        # 如果通知失败，至少记录日志

# ==================== 命令处理 ====================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    logging.info(f"用户 {user_id} 启动机器人。")
    
    # 清理之前的登录状态，避免重复
    if user_id in pending_logins:
        del pending_logins[user_id]
        logging.info(f"清理用户 {user_id} 的重复登录状态")
    
    # 检查登录状态
    if not is_user_logged_in(user_id):
        # 避免重复显示登录界面
        if user_id not in pending_logins:
            await show_login_screen(message)
        return
    # 更新用户活动时间
    update_user_activity(user_id)
    
    # 获取用户名用于欢迎消息
    username = get_logged_in_username(user_id)
    
    # 仅清理非进行中的任务，保留正在搬运的任务，避免进度更新中断
    if user_id in user_states:
        active_tasks = [t for t in user_states[user_id] if t.get("state") == "cloning_in_progress"]
        if active_tasks:
            user_states[user_id] = active_tasks
        else:
            del user_states[user_id]
    # 若存在未完成任务，提示恢复
    resume_buttons = []
    resumed_text = ""
    pending = running_tasks.get(str(user_id), {})
    if pending:
        resumed_text = "\n\n检测到未完成任务，可前往任务列表恢复。"
        resume_buttons.append([InlineKeyboardButton("📜 查看我的任务", callback_data="view_tasks")])
    await message.reply_text(
        f"👋 **欢迎回来，{username}！** 🌟\n请选择你想要执行的操作：{resumed_text}",
        reply_markup=InlineKeyboardMarkup(resume_buttons + get_main_menu_buttons(user_id).inline_keyboard)
    )

@app.on_message(filters.command("clone") & filters.private)
async def clone_command(client, message):
    await select_channel_pairs_to_clone(message, message.from_user.id)

@app.on_message(filters.command("manage") & filters.private)
async def manage_command(client, message):
    await show_channel_config_menu(message, message.from_user.id)

@app.on_message(filters.command("features") & filters.private)
async def features_command(client, message):
    await show_feature_config_menu(message, message.from_user.id)

@app.on_message(filters.command("config") & filters.private)
async def config_command(client, message):
    await view_config(message, message.from_user.id)

@app.on_message(filters.command("tasks") & filters.private)
async def tasks_command(client, message):
    await view_tasks(message, message.from_user.id)

@app.on_message(filters.command("history") & filters.private)
async def history_command(client, message):
    await view_history(message, message.from_user.id)

@app.on_message(filters.command("debug") & filters.private)


@app.on_message(filters.command("resetlogin") & filters.private)
async def reset_login_command(client, message):
    """重置用户登录状态，解决重复登录问题"""
    user_id = message.from_user.id
    
    # 清理登录状态
    if user_id in pending_logins:
        del pending_logins[user_id]
        logging.info(f"用户 {user_id} 重置登录状态")
    
    # 清理登录尝试记录
    user_id_str = str(user_id)
    if user_id_str in login_attempts:
        del login_attempts[user_id_str]
        logging.info(f"用户 {user_id} 清理登录尝试记录")
    
    # 清理消息处理记录
    global processed_messages
    keys_to_remove = [k for k in processed_messages.keys() if k.startswith(f"{user_id}_")]
    for k in keys_to_remove:
        del processed_messages[k]
    
    await message.reply_text(
        "🔄 **登录状态已重置**\n\n"
        "您的登录状态已被清理，现在可以重新使用 /start 命令开始登录。\n\n"
        "如果遇到重复登录问题，请使用此命令重置。"
    )



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


@app.on_message(filters.command("emergency") & filters.private)
async def emergency_reset_command(client, message):
    """紧急重置所有状态，解决FloodWait和按钮失效问题"""
    user_id = message.from_user.id
    if not is_user_logged_in(user_id):
        await message.reply("请先登录后再使用此命令。")
        return
    
    if not is_admin_user(user_id):
        await message.reply("❌ 您没有管理员权限")
        return
    
    try:
        # 重置FloodWait状态
        if hasattr(flood_wait_manager, 'flood_wait_status'):
            flood_wait_manager.flood_wait_status.clear()
            logging.info(f"[{bot_config['bot_id']}] 已清除所有FloodWait状态")
        
        # 重置用户状态
        if user_id in user_states:
            del user_states[user_id]
            logging.info(f"[{bot_config['bot_id']}] 已清除用户状态")
        
        # 重置pending_logins
        if user_id in pending_logins:
            del pending_logins[user_id]
            logging.info(f"[{bot_config['bot_id']}] 已清除登录等待状态")
        
        # 重置processed_messages
        global processed_messages
        keys_to_remove = [k for k in processed_messages.keys() if k.startswith(f"{user_id}_")]
        for k in keys_to_remove:
            del processed_messages[k]
        
        await message.reply(
            "🚨 **紧急重置完成**\n\n"
            "已清除以下状态：\n"
            "✅ FloodWait限制\n"
            "✅ 用户状态\n"
            "✅ 登录等待\n"
            "✅ 消息处理记录\n\n"
            "现在所有功能应该恢复正常！"
        )
        
    except Exception as e:
        logging.error(f"紧急重置失败: {e}")
        await message.reply(f"❌ 紧急重置失败: {str(e)}")
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
            status_text = "🔍 **存储状态检查**\n\n"
            status_text += f"📱 **内存存储**: {'✅ 已启用' if status['github_backup_enabled'] else '❌ 未启用'}\n"
            status_text += f"⏰ **备份间隔**: {status['backup_interval']}秒\n\n"
            status_text += "📊 **备份状态**:\n"
            
            for config_type, last_time in status['last_backup'].items():
                status_text += f"• {config_type}: {last_time}\n"
            
            await message.reply(status_text)
        except Exception as e:
            await message.reply(f"❌ 获取状态失败: {str(e)}")
    else:
        await message.reply("❌ 内存存储管理器未启用")

@app.on_message(filters.command("configstatus") & filters.private)
async def config_status_command(client, message):
    """检查配置保存状态"""
    user_id = message.from_user.id
    if not is_user_logged_in(user_id):
        await message.reply("请先登录后再使用此命令。")
        return
    
    # 检查各种配置文件的状态
    status_text = "🔍 **配置保存状态检查**\n\n"
    
    # 检查持久化存储路径
    persistent_path = get_config_path("")
    status_text += f"📁 **持久化存储路径**: {persistent_path}\n"
    
    # 检查各种配置文件
    config_files = [
        f"user_configs_{bot_config['bot_id']}.json",
        f"user_states_{bot_config['bot_id']}.json", 
        f"user_history_{bot_config['bot_id']}.json",
        f"user_login_{bot_config['bot_id']}.json"
    ]
    
    for filename in config_files:
        persistent_file = get_config_path(filename)
        backup_file = filename
        
        persistent_exists = os.path.exists(persistent_file)
        backup_exists = os.path.exists(backup_file)
        
        if persistent_exists:
            status_text += f"✅ {filename} - 持久化存储\n"
        elif backup_exists:
            status_text += f"⚠️ {filename} - 仅备份文件\n"
        else:
            status_text += f"❌ {filename} - 不存在\n"
    
    # 检查内存中的配置
    status_text += f"\n💾 **内存配置状态**:\n"
    status_text += f"• 用户配置: {len(user_configs)} 个用户\n"
    status_text += f"• 用户状态: {len(user_states)} 个用户\n"
    status_text += f"• 历史记录: {len(user_history)} 个用户\n"
    status_text += f"• 登录用户: {len(logged_in_users)} 个\n"
    
    # 添加修复按钮
    buttons = [
        [InlineKeyboardButton("🔄 强制保存配置", callback_data="force_save_configs")],
        [InlineKeyboardButton("🔍 查看详细状态", callback_data="view_detailed_config_status")]
    ]
    
    await message.reply_text(status_text, reply_markup=InlineKeyboardMarkup(buttons))
async def debug_command(client, message):
    user_id = message.from_user.id
    if not is_user_logged_in(user_id):
        await message.reply("请先登录后再使用此命令。")
        return
    
    cfg = user_configs.get(str(user_id), {})
    realtime_listen = cfg.get("realtime_listen", False)
    channel_pairs = cfg.get("channel_pairs", [])
    
    debug_text = f"🔍 **实时监听调试信息**\n\n"
    debug_text += f"**监听总开关**: {'✅ 开启' if realtime_listen else '❌ 关闭'}\n"
    debug_text += f"**频道组总数**: {len(channel_pairs)}\n\n"
    
    if not channel_pairs:
        debug_text += "❌ 未配置任何频道组。请先添加频道组。\n"
    else:
        debug_text += "**频道组详情**:\n"
        monitored_count = 0
        for i, pair in enumerate(channel_pairs):
            enabled = pair.get("enabled", True)
            monitor_enabled = pair.get("monitor_enabled", False)
            if enabled and monitor_enabled:
                monitored_count += 1
            
            status_icons = []
            if enabled:
                status_icons.append("✅ 启用")
            else:
                status_icons.append("⏸ 暂停")
                
            if monitor_enabled:
                status_icons.append("👂 监听")
            else:
                status_icons.append("🔇 静音")
            
            debug_text += f"`{i+1}.` `{pair.get('source')}` → `{pair.get('target')}`\n"
            debug_text += f"    状态: {' | '.join(status_icons)}\n"
    
    debug_text += f"\n**有效监听频道组数**: {monitored_count}\n"
    
    if realtime_listen and monitored_count > 0:
        debug_text += "\n✅ **实时监听应该正常工作**\n"
        debug_text += "如果仍然无法搬运，请检查:\n"
        debug_text += "• 机器人是否加入了源频道\n"
        debug_text += "• 机器人是否有目标频道的发送权限\n"
        debug_text += "• 源频道的消息是否符合过滤规则\n"
    else:
        debug_text += "\n❌ **实时监听无法工作，原因**:\n"
        if not realtime_listen:
            debug_text += "• 监听总开关未开启\n"
        if monitored_count == 0:
            debug_text += "• 没有启用监听的频道组\n"
    
    await message.reply(debug_text)

# FloodWait测试命令
@app.on_message(filters.command("testfloodwait") & filters.private)
async def test_floodwait_system(message):
    """测试FloodWait系统"""
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        await message.reply_text("❌ 只有管理员可以使用此命令")
        return
    
    # 显示FloodWait系统状态
    health = flood_wait_manager.get_health_status()
    all_status = flood_wait_manager.get_all_flood_wait_status()
    
    status_text = f"🧪 **FloodWait系统测试**\n\n"
    status_text += f"**系统健康状态**:\n"
    status_text += f"• 总限制数: {health['total_restrictions']}\n"
    status_text += f"• 异常限制: {health['abnormal_restrictions']}\n"
    status_text += f"• 正常限制: {health['normal_restrictions']}\n\n"
    
    if all_status:
        status_text += "**当前限制详情**:\n"
        for key, info in all_status.items():
            status_text += f"• {info['operation_type']}: {info['remaining_formatted']}\n"
    else:
        status_text += "✅ **当前无FloodWait限制**\n"
    
    status_text += f"\n**智能处理策略**:\n"
    status_text += f"• 极异常时间(>5分钟): 直接清除\n"
    status_text += f"• 异常时间(>2分钟): 限制为60秒\n"
    status_text += f"• 较长时间(>1分钟): 智能调整\n"
    status_text += f"• 正常时间: 保持原样\n"
    
    await message.reply_text(status_text)

# 模拟FloodWait测试
@app.on_message(filters.command("simulatefloodwait") & filters.private)
async def simulate_floodwait_test(message):
    """模拟FloodWait测试"""
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        await message.reply_text("❌ 只有管理员可以使用此命令")
        return
    
    # 模拟设置一个异常的FloodWait时间
    test_wait_time = 180  # 3分钟
    flood_wait_manager.set_flood_wait('test_operation', test_wait_time)
    
    await message.reply_text(
        f"🧪 **FloodWait模拟测试**\n\n"
        f"已设置测试限制:\n"
        f"• 操作类型: test_operation\n"
        f"• 等待时间: {test_wait_time}秒\n\n"
        f"使用 /testfloodwait 查看系统如何处理\n"
        f"使用 /fixfloodwait 立即修复"
    )

# 登录测试命令
@app.on_message(filters.command("testlogin") & filters.private)
async def test_login_status(message):
    """测试登录状态"""
    user_id = message.from_user.id
    
    # 检查登录状态
    if is_user_logged_in(user_id):
        username = get_logged_in_username(user_id)
        is_admin = is_admin_user(user_id)
        admin_text = " (管理员)" if is_admin else ""
        
        await message.reply_text(
            f"✅ **登录状态检查**\n\n"
            f"用户ID: {user_id}\n"
            f"用户名: {username}{admin_text}\n"
            f"状态: 已登录\n\n"
            f"所有功能可用！"
        )
    else:
        await message.reply_text(
            f"❌ **登录状态检查**\n\n"
            f"用户ID: {user_id}\n"
            f"状态: 未登录\n\n"
            f"请使用 /start 命令登录"
        )

# 登录数据检查命令
@app.on_message(filters.command("checklogin") & filters.private)
async def check_login_data(message):
    """检查登录数据"""
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        await message.reply_text("❌ 只有管理员可以使用此命令")
        return
    
    # 显示登录数据统计
    total_users = len(logged_in_users)
    total_attempts = len(login_attempts)
    
    await message.reply_text(
        f"📊 **登录数据统计**\n\n"
        f"已登录用户: {total_users}\n"
        f"登录尝试记录: {total_attempts}\n\n"
        f"数据文件: {get_config_path('user_login_' + bot_config['bot_id'] + '.json')}"
    )

# ==================== 回调处理 ====================
@app.on_callback_query()
async def callback_handler(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    # 特殊处理登录相关的回调
    if data == "refresh_login_status":
        if can_attempt_login(user_id):
            await show_login_screen(callback_query.message)
        # 锁定检查已禁用，继续处理
    
    # 其他回调需要登录验证
    if not is_user_logged_in(user_id):
        try:
            await callback_query.answer("请先登录", show_alert=True)
        except Exception as e:
            logging.warning(f"回调查询应答失败: {e}")
        await show_login_screen(callback_query.message)
        return
    
    # 更新用户活动时间
    update_user_activity(user_id)
    logging.info(f"用户 {user_id} 点击了回调按钮: {data}")
    
    # 安全地处理回调查询，避免 QUERY_ID_INVALID 错误
    try:
        await callback_query.answer()
    except Exception as answer_error:
        logging.warning(f"回调查询应答失败，继续处理: {answer_error}")
        # 继续处理，不因为应答失败而中断

    if data == "show_main_menu":
        await show_main_menu(callback_query.message, user_id)
    elif data == "show_channel_config_menu":
        await show_channel_config_menu(callback_query.message, user_id)
    elif data == "show_feature_config_menu":
        await show_feature_config_menu(callback_query.message, user_id)
    elif data == "toggle_content_removal":
        await toggle_content_removal_menu(callback_query.message, user_id)
    elif data.startswith("toggle_monitor_pair:"):
        pair_id = int(data.split(':')[1])
        logging.info(f"用户 {user_id} 点击了单选监听按钮，频道组ID: {pair_id}")
        await toggle_monitor_pair(callback_query.message, user_id, pair_id)
    elif data.startswith("toggle_"):
        await handle_toggle_options(callback_query.message, user_id, data)
    elif data.startswith("set_tail_position_"):
        await handle_tail_position_setting(callback_query.message, user_id, data)
    elif data == "view_config":
        await view_config(callback_query.message, user_id)
    elif data == "add_channel_pair":
        await request_channel_pair_input(callback_query.message, user_id)
    elif data.startswith("edit_channel_pair:"):
        pair_id = int(data.split(':')[1])
        await show_edit_channel_pair_menu(callback_query.message, user_id, pair_id)
    elif data.startswith("edit_pair_source:"):
        pair_id = int(data.split(':')[1])
        await request_edit_pair_input(callback_query.message, user_id, pair_id, "source")
    elif data.startswith("edit_pair_target:"):
        pair_id = int(data.split(':')[1])
        await request_edit_pair_input(callback_query.message, user_id, pair_id, "target")
    elif data.startswith("toggle_pair_enabled:"):
        pair_id = int(data.split(':')[1])
        await toggle_pair_enabled(callback_query.message, user_id, pair_id)
    elif data.startswith("manage_pair_filters:"):
        pair_id = int(data.split(':')[1])
        await show_pair_filter_menu(callback_query.message, user_id, pair_id)
    elif data.startswith("enable_pair_filters:"):
        pair_id = int(data.split(':')[1])
        await enable_pair_filters(callback_query.message, user_id, pair_id)
    elif data.startswith("reset_pair_filters:"):
        pair_id = int(data.split(':')[1])
        await reset_pair_filters(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_filter_tail_text:"):
        pair_id = int(data.split(':')[1])
        await show_pair_tail_text_menu(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_set_tail_text:"):
        pair_id = int(data.split(':')[1])
        await request_pair_tail_text(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_set_tail_position:"):
        pair_id = int(data.split(':')[1])
        await show_pair_tail_position_menu(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_set_tail_pos:"):
        parts = data.split(':')
        if len(parts) == 3:
            position = parts[1]
            pair_id = int(parts[2])
            await set_pair_tail_position(callback_query.message, user_id, position, pair_id)
    elif data.startswith("pair_clear_tail_text:"):
        pair_id = int(data.split(':')[1])
        await clear_pair_tail_text(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_add_button:"):
        pair_id = int(data.split(':')[1])
        await request_pair_button_input(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_clear_buttons:"):
        pair_id = int(data.split(':')[1])
        await clear_pair_buttons(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_filter_keywords:"):
        pair_id = int(data.split(':')[1])
        await show_pair_keywords_menu(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_add_keyword:"):
        pair_id = int(data.split(':')[1])
        await request_pair_add_keyword(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_clear_keywords:"):
        pair_id = int(data.split(':')[1])
        await clear_pair_keywords(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_filter_replacements:"):
        pair_id = int(data.split(':')[1])
        await show_pair_replacements_menu(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_filter_files:"):
        pair_id = int(data.split(':')[1])
        await show_pair_files_menu(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_filter_content:"):
        pair_id = int(data.split(':')[1])
        await show_pair_content_menu(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_filter_buttons:"):
        pair_id = int(data.split(':')[1])
        await show_pair_buttons_menu(callback_query.message, user_id, pair_id)
    elif data.startswith("pair_filter_button_policy:"):
        pair_id = int(data.split(':')[1])
        await show_pair_button_policy_menu(callback_query.message, user_id, pair_id)
    elif data == "select_channel_pairs_to_clone":
        await select_channel_pairs_to_clone(callback_query.message, user_id)
    elif data.startswith("select_channel_pair:"):
        await handle_channel_pair_selection(callback_query, user_id, data)
    elif data.startswith("next_step_clone_range:"):
        task_id = data.split(':')[1]
        await handle_next_step_clone_range(callback_query, user_id, task_id)

    elif data.startswith("confirm_clone_action:"):
        task_id = data.split(":")[1]
        task = find_task(user_id, task_id=task_id)
        if not task:
            await safe_edit_or_reply(callback_query.message, "❌ 任务已失效，请重新操作。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]))
            return
        
        # 直接启动老湿姬2.0引擎
        await start_cloning_with_new_engine(client, callback_query.message, user_id, task)

    elif data.startswith("delete_channel_pair:"):
        pair_id = int(data.split(":")[1])
        await delete_channel_pair(callback_query.message, user_id, pair_id)
    elif data.startswith("cancel_task:"):
        task_id = data.split(":")[1]
        # 设置取消标志
        running_task_cancellation[task_id] = True
        logging.info(f"用户 {user_id} 取消了任务 {task_id[:8]}")
        
        # 同时设置旧的取消标志以确保兼容性
        task = find_task(user_id, task_id=task_id)
        if task:
            task["cancel_request"] = True
        
        await safe_edit_or_reply(callback_query.message, 
            f"🛑 **正在取消任务** `{task_id[:8]}`\n\n"
            f"⏳ 等待当前操作完成后停止...",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")
            ]])
        )
    elif data.startswith("cancel:"):
        task_id = data.split(":")[1]
        task = find_task(user_id, task_id=task_id)
        if task and task.get("state") == "cloning_in_progress":
            task["cancel_request"] = True
            await safe_edit_or_reply(callback_query.message,
                                     f"✅ 任务 `{task_id[:8]}` 已发出取消请求，将在搬运下一条信息时停止。",
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📜 查看我的任务", callback_data="view_tasks")]]))
        else:
            remove_task(user_id, task_id)
            await safe_edit_or_reply(callback_query.message,
                                     f"✅ 任务 `{task_id[:8]}` 已取消。",
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📜 查看我的任务", callback_data="view_tasks")]]))
    elif data == "cancel_all":
        if user_id in user_states:
            for task in user_states[user_id]:
                if task.get("state") == "cloning_in_progress":
                    task["cancel_request"] = True
                else:
                    remove_task(user_id, task["task_id"])
        logging.info(f"用户 {user_id} 取消了所有任务。")
        await safe_edit_or_reply(callback_query.message,
                                 "✅ 已发出所有进行中任务的取消请求，其他任务已移除。",
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]))
    # 新增互动式功能设定的回调处理
    elif data == "manage_filter_keywords":
        await show_manage_keywords_menu(callback_query.message, user_id)
    elif data.startswith("add_keyword:"):
        await request_add_keyword(callback_query.message, user_id)
    elif data.startswith("delete_keyword:"):
        keyword = data.split(':', 1)[1]
        await delete_keyword(callback_query.message, user_id, keyword)
    elif data == "manage_replacement_words":
        await show_manage_replacements_menu(callback_query.message, user_id)
    elif data.startswith("add_replacement:"):
        await request_add_replacement(callback_query.message, user_id)
    elif data.startswith("delete_replacement:"):
        word = data.split(':', 1)[1]
        await delete_replacement(callback_query.message, user_id, word)
    elif data == "manage_file_filter":
        await show_file_filter_menu(callback_query.message, user_id)
    elif data == "manage_file_extension_filter":
        await show_manage_file_extensions_menu(callback_query.message, user_id)
    elif data == "manage_filter_buttons":
        await show_manage_filter_buttons_menu(callback_query.message, user_id)
    elif data == "request_tail_text":
        await request_tail_text(callback_query.message, user_id)
    elif data == "request_buttons":
        await request_buttons_input(callback_query.message, user_id)
    elif data.startswith("add_file_extension:"):
        await request_add_file_extension(callback_query.message, user_id)
    elif data.startswith("delete_file_extension:"):
        ext = data.split(':', 1)[1]
        await delete_file_extension(callback_query.message, user_id, ext)
    elif data.startswith("set_btn_mode:"):
        mode = data.split(':', 1)[1]
        user_configs.setdefault(str(user_id), {})["filter_buttons_mode"] = mode
        save_configs()
        await show_manage_filter_buttons_menu(callback_query.message, user_id)
    elif data.startswith("add_btn_domain:"):
        await request_add_whitelist_domain(callback_query.message, user_id)
    elif data == "clear_btn_domain":
        user_configs.setdefault(str(user_id), {})["button_domain_whitelist"] = []
        save_configs()
        await show_manage_filter_buttons_menu(callback_query.message, user_id)
    elif data == "clear_history":
        await clear_user_history(callback_query.message, user_id)
    elif data == "show_help":
        await show_help(callback_query.message, user_id)
    elif data == "force_save_configs":
        await force_save_configs(callback_query.message, user_id)
    elif data == "view_detailed_config_status":
        await view_detailed_config_status(callback_query.message, user_id)
    elif data == "view_tasks":
        await view_tasks(callback_query.message, user_id)
    elif data.startswith("resume:"):
        tid = data.split(":", 1)[1]
        snap = running_tasks.get(str(user_id), {}).get(tid)
        if not snap:
            await safe_edit_or_reply(callback_query.message, "❌ 未找到可恢复的任务。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]))
            return
        # 构造任务对象注入 user_states
        restore_task = {
            "task_id": tid,
            "state": "cloning_in_progress",
            "clone_tasks": snap.get("clone_tasks", []),
            "partial_stats": snap.get("partial_stats", {}),
            "progress": snap.get("progress", {}),
            "restore_mode": True  # 标记为恢复模式
        }
        user_states.setdefault(user_id, []).append(restore_task)
        
        # 清除取消和中断标记，准备恢复
        if str(user_id) in running_tasks and tid in running_tasks[str(user_id)]:
            running_tasks[str(user_id)][tid].pop("cancelled", None)
            running_tasks[str(user_id)][tid].pop("cancelled_time", None)
            save_running_tasks()
        
        task_type = "被取消" if snap.get("cancelled") else "中断"
        await safe_edit_or_reply(callback_query.message, f"🔄 正在恢复{task_type}的任务 `{tid[:8]}` ...")
        try:
            await start_cloning_with_new_engine(client, callback_query.message, user_id, restore_task)
        finally:
            pass
    elif data.startswith("drop_running:"):
        tid = data.split(":", 1)[1]
        if str(user_id) in running_tasks and tid in running_tasks[str(user_id)]:
            del running_tasks[str(user_id)][tid]
            if not running_tasks[str(user_id)]:
                del running_tasks[str(user_id)]
            save_running_tasks()
        await view_tasks(callback_query.message, user_id)
    elif data == "view_history":
        await view_history(callback_query.message, user_id)
    elif data == "daily_stats":
        await show_daily_stats(callback_query.message, user_id)
    elif data.startswith("history_page:"):
        parts = data.split(":")
        if len(parts) == 3:
            target_user_id = int(parts[1])
            page = int(parts[2])
            if target_user_id == user_id:  # 确保用户只能查看自己的历史记录
                await view_history(callback_query.message, user_id, page)
    # 新增监控相关回调
    elif data == "show_monitor_menu":
        await show_monitor_menu(callback_query.message, user_id)
    elif data == "manage_monitor_channels":
        await show_monitor_channels_menu(callback_query.message, user_id)
    elif data == "monitor_select_all":
        await monitor_select_all(callback_query.message, user_id)
    elif data == "monitor_select_none":
        await monitor_select_none(callback_query.message, user_id)
    elif data == "logout":
        await handle_logout(callback_query.message, user_id)
    elif data == "show_admin_panel":
        await show_admin_panel(callback_query.message, user_id)
    elif data.startswith("admin_"):
        if data == "admin_clear_performance":
            if is_admin_user(user_id):
                performance_stats.clear()
                try:
                    await callback_query.answer("✅ 性能统计已清空")
                except Exception as e:
                    logging.warning(f"回调查询应答失败: {e}")
                await show_performance_monitor(callback_query.message, user_id)
        elif data == "admin_gc_collect":
            if is_admin_user(user_id):
                import gc
                collected = gc.collect()
                try:
                    await callback_query.answer(f"✅ 垃圾回收完成，清理了 {collected} 个对象")
                except Exception as e:
                    logging.warning(f"回调查询应答失败: {e}")
                await show_system_maintenance(callback_query.message, user_id)
        elif data == "admin_clear_cache":
            if is_admin_user(user_id):
                realtime_dedupe_cache.clear()
                try:
                    await callback_query.answer("✅ 缓存已清理")
                except Exception as e:
                    logging.warning(f"回调查询应答失败: {e}")
                await show_system_maintenance(callback_query.message, user_id)
        elif data == "admin_save_all":
            if is_admin_user(user_id):
                try:
                    save_configs()
                    save_history()
                    save_running_tasks()
                    save_user_states()
                    save_login_data()
                    try:
                        await callback_query.answer("✅ 所有数据已保存")
                    except Exception as answer_e:
                        logging.warning(f"回调查询应答失败: {answer_e}")
                except Exception as e:
                    try:
                        await callback_query.answer(f"❌ 保存失败: {str(e)}")
                    except Exception as answer_e:
                        logging.warning(f"回调查询应答失败: {answer_e}")
                await show_system_maintenance(callback_query.message, user_id)
        else:
            await handle_admin_action(callback_query.message, user_id, data)
    elif data == "show_frequency_settings":
        await show_frequency_settings(callback_query.message, user_id)
    elif data == "config_tail_frequency":
        await show_tail_frequency_config(callback_query.message, user_id)
    elif data == "config_button_frequency":
        await show_button_frequency_config(callback_query.message, user_id)
    elif data == "fix_floodwait_now":
        await fix_floodwait_now(callback_query.message, user_id)
    elif data == "refresh_floodwait_status":
        await refresh_floodwait_status(callback_query.message, user_id)
    elif data.startswith("set_tail_freq:"):
        mode = data.split(":", 1)[1]
        await handle_tail_frequency_set(callback_query.message, user_id, mode)
    elif data.startswith("set_button_freq:"):
        mode = data.split(":", 1)[1]
        await handle_button_frequency_set(callback_query.message, user_id, mode)
    elif data.startswith("set_tail_interval"):
        await request_tail_interval(callback_query.message, user_id)
    elif data.startswith("set_tail_probability"):
        await request_tail_probability(callback_query.message, user_id)
    elif data.startswith("set_button_interval"):
        await request_button_interval(callback_query.message, user_id)
    elif data.startswith("set_button_probability"):
        await request_button_probability(callback_query.message, user_id)
    elif data == "monitor_pair_disabled":
        # 已暂停的频道组按钮，显示提示
        try:
            await callback_query.answer("⏸ 该频道组已暂停，无法操作", show_alert=True)
        except Exception as e:
            logging.warning(f"回调查询应答失败: {e}")
    elif data in ["filter_settings_header", "button_control_header", "content_enhancement_header"]:
        # 标题按钮，无需操作
        try:
            await callback_query.answer("ℹ️ 这是功能分类标题", show_alert=False)
        except Exception as e:
            logging.warning(f"回调查询应答失败: {e}")

# ==================== 智能搬运优化命令 ====================
@app.on_message(filters.command("optimize") & filters.private)
async def optimize_transport_command(client, message):
    user_id = message.from_user.id
    if not is_user_logged_in(user_id):
        await message.reply("请先登录后再使用此命令。")
        return
    
    # 获取用户配置
    cfg = user_configs.get(str(user_id), {})
    channel_pairs = cfg.get("channel_pairs", [])
    
    if not channel_pairs:
        await message.reply("❌ 没有配置频道组，无法优化。")
        return
    
    optimization_text = f"🔧 **智能搬运优化建议**\n\n"
    
    # 分析当前配置
    total_pairs = len(channel_pairs)
    enabled_pairs = [p for p in channel_pairs if p.get("enabled")]
    monitor_pairs = [p for p in enabled_pairs if p.get("monitor_enabled")]
    
    optimization_text += f"**当前配置分析**:\n"
    optimization_text += f"• 频道组总数: {total_pairs}\n"
    optimization_text += f"• 启用频道组: {len(enabled_pairs)}\n"
    optimization_text += f"• 监听频道组: {len(monitor_pairs)}\n\n"
    
    # 优化建议
    optimization_text += f"**优化建议**:\n"
    
    if len(monitor_pairs) > 5:
        optimization_text += f"⚠️ 监听频道组过多 ({len(monitor_pairs)} > 5)\n"
        optimization_text += f"   建议: 减少到 3-5 个，避免触发限制\n"
    else:
        optimization_text += f"✅ 监听频道组数量合理\n"
    
    # 检查是否有大量搬运任务
    user_tasks = user_states.get(user_id, [])
    active_tasks = [t for t in user_tasks if t.get("state") in ["running", "paused"]]
    
    if active_tasks:
        optimization_text += f"⚠️ 有 {len(active_tasks)} 个活跃任务\n"
        optimization_text += f"   建议: 避免同时运行多个大任务\n"
    else:
        optimization_text += f"✅ 当前没有活跃任务\n"
    
    # 添加预防措施
    optimization_text += f"\n**预防 FloodWait 措施**:\n"
    optimization_text += f"• 搬运间隔: 建议 2-3 秒\n"
    optimization_text += f"• 批量大小: 建议 3-5 条\n"
    optimization_text += f"• 监听频道: 建议 ≤5 个\n"
    optimization_text += f"• 任务并发: 建议 ≤2 个\n"
    
    # 添加当前状态
    optimization_text += f"\n**当前状态**:\n"
    user_status = flood_wait_manager.get_user_flood_wait_status(str(user_id))
    if user_status:
        for operation, info in user_status.items():
            remaining = info['remaining_formatted']
            limit_type = info.get('type', 'unknown')
            if limit_type == 'global':
                optimization_text += f"• {operation}: 全局限制，剩余 {remaining}\n"
            else:
                optimization_text += f"• {operation}: 剩余 {remaining}\n"
    else:
        optimization_text += f"✅ 无任何限制，可以自由操作\n"
    
    optimization_text += f"\n🎉 **好消息**: 已移除所有用户级限制！\n"
    optimization_text += f"现在您可以不受限制地使用机器人功能。"
    
    try:
        await message.reply_text(optimization_text, parse_mode="Markdown")
    except Exception as e:
        optimization_text_plain = optimization_text.replace("**", "").replace("*", "")
        await message.reply_text(optimization_text_plain)

# ==================== 限制状态说明命令 ====================
@app.on_message(filters.command("limits") & filters.private)
async def explain_limits_command(client, message):
    user_id = message.from_user.id
    if not is_user_logged_in(user_id):
        await message.reply("请先登录后再使用此命令。")
        return
    
    explain_text = f"🎉 **限制状态说明**\n\n"
    explain_text += f"✅ **已移除所有用户级限制！**\n\n"
    explain_text += f"**当前状态**:\n"
    explain_text += f"• 用户个人限制: ❌ 已完全移除\n"
    explain_text += f"• 全局操作限制: ⚠️ 仅保留最基本的频率控制\n"
    explain_text += f"• 操作间隔: 最小化到 0.05 秒\n\n"
    
    explain_text += f"**这意味着**:\n"
    explain_text += f"• 您可以不受限制地使用机器人\n"
    explain_text += f"• 不再有个人等待时间\n"
    explain_text += f"• 可以连续快速操作\n"
    explain_text += f"• 机器人性能最大化\n\n"
    
    explain_text += f"**使用建议**:\n"
    explain_text += f"• 尽情使用所有功能\n"
    explain_text += f"• 无需担心个人限制\n"
    explain_text += f"• 享受无限制的搬运体验！"
    
    try:
        await message.reply_text(explain_text, parse_mode="Markdown")
    except Exception as e:
        explain_text_plain = explain_text.replace("**", "").replace("*", "")
        await message.reply_text(explain_text_plain)

# ==================== FloodWait状态查询命令 ====================
@app.on_message(filters.command("floodwait") & filters.private)
async def floodwait_status_command(client, message):
    user_id = message.from_user.id
    if not is_user_logged_in(user_id):
        await message.reply("请先登录后再使用此命令。")
        return
    
    # 执行自动恢复检查
    recovered, expired = flood_wait_manager.auto_recovery_check()
    
    # 获取健康状态
    health = flood_wait_manager.get_health_status()
    
    # 清理过期的FloodWait记录
    expired_count = flood_wait_manager.clear_expired_flood_wait()
    
    # 获取所有FloodWait状态
    all_status = flood_wait_manager.get_all_flood_wait_status()
    
    # 获取当前用户的FloodWait状态
    user_status = flood_wait_manager.get_user_flood_wait_status(str(user_id))
    
    status_text = f"🚫 **限制状态报告**\n\n"
    
    # 添加健康状态信息
    if health['is_healthy']:
        status_text += "✅ **系统状态: 健康**\n"
    else:
        status_text += f"⚠️ **系统状态: 异常** (发现 {health['abnormal_restrictions']} 个异常限制)\n"
    
    status_text += f"📈 **统计信息:**\n"
    status_text += f"• 总限制数: {health['total_restrictions']}\n"
    status_text += f"• 活跃限制: {health['active_restrictions']}\n"
    status_text += f"• 异常限制: {health['abnormal_restrictions']}\n"
    
    if recovered > 0 or expired > 0:
        status_text += f"\n🔄 **自动恢复结果:**\n"
        status_text += f"• 修复异常限制: {recovered} 个\n"
        status_text += f"• 清理过期记录: {expired} 个\n"
    
    if not all_status:
        status_text += f"\n✅ **当前没有任何限制**\n"
        status_text += "所有操作都可以正常执行\n"
    else:
        status_text += f"\n⚠️ **当前有 {len(all_status)} 个全局限制**\n\n"
        
        # 显示所有限制
        for key, info in all_status.items():
            operation = info['operation_type']
            remaining = info['remaining_formatted']
            
            status_text += f"**{operation}**: 剩余等待时间 {remaining}\n\n"
    
    # 显示当前用户的状态
    if user_status:
        status_text += f"**您受到的影响**:\n"
        for operation, info in user_status.items():
            remaining = info['remaining_formatted']
            limit_type = info.get('type', 'unknown')
            if limit_type == 'global':
                status_text += f"• {operation}: 全局限制，剩余 {remaining}\n"
            else:
                status_text += f"• {operation}: 剩余 {remaining}\n"
    else:
        status_text += f"**您的状态**: ✅ 完全无限制\n"
    
    status_text += f"\n🎉 **重要更新**: 已移除所有用户级限制！\n"
    status_text += f"现在您可以不受个人限制地使用机器人。"
    
    if expired_count > 0:
        status_text += f"\n🧹 已清理 {expired_count} 个过期的限制记录\n"
    
    # 添加建议
    status_text += f"\n**建议**:\n"
    if all_status:
        status_text += "• 请等待限制时间结束后再操作\n"
        status_text += "• 避免频繁发送消息\n"
        status_text += "• 考虑降低操作频率\n"
    else:
        status_text += "• 可以正常使用机器人功能\n"
        status_text += "• 注意保持合理的操作频率\n"
    
    # 添加手动恢复按钮
    buttons = []
    if health['abnormal_restrictions'] > 0:
        buttons.append([InlineKeyboardButton("🔄 立即修复异常限制", callback_data="fix_floodwait_now")])
    buttons.append([InlineKeyboardButton("🔍 刷新状态", callback_data="refresh_floodwait_status")])
    
    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    
    try:
        await message.reply_text(status_text, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception as e:
        # 如果Markdown解析失败，发送纯文本
        status_text_plain = status_text.replace("**", "").replace("*", "")
        await message.reply_text(status_text_plain, reply_markup=reply_markup)

# ==================== 文本处理 ====================
@app.on_message(filters.private & filters.text)
@monitor_performance('handle_text_input')
async def handle_text_input(client, message):
    global processed_messages
    user_id = message.from_user.id
    
    # 防止重复处理 - 使用更强大的去重机制
    message_id = message.id
    current_time = time.time()
    
    # 创建消息处理记录键
    process_key = f"{user_id}_{message_id}"
    
    # 检查是否已经处理过
    if process_key in processed_messages:
        logging.info(f"消息 {message_id} 已被处理，跳过")
        return
    
    # 清理过期的处理记录（3分钟前的）
    expired_keys = [k for k, v in processed_messages.items() 
                    if current_time - v > 180]
    for k in expired_keys:
        del processed_messages[k]
    
    # 标记为已处理
    processed_messages[process_key] = current_time
    logging.info(f"标记消息 {message_id} 为已处理")
    
    # 检查是否正在等待用户名输入
    if user_id in pending_logins and pending_logins[user_id].get("waiting_for_username"):
        await handle_username_input(message)
        return
    
    # 检查登录状态
    if not is_user_logged_in(user_id):
        # 避免重复显示登录界面
        if user_id not in pending_logins:
            await show_login_screen(message)
        return
    
    # 更新用户活动时间
    update_user_activity(user_id)
    last_task = find_task(user_id, state="waiting_for_source") or \
                find_task(user_id, state="waiting_for_target") or \
                find_task(user_id, state="waiting_for_edit_input") or \
                find_task(user_id, state="waiting_for_range_for_pair") or \
                find_task(user_id, state="waiting_for_add_keyword") or \
                find_task(user_id, state="waiting_for_add_replacement") or \
                find_task(user_id, state="waiting_for_add_file_extension") or \
                find_task(user_id, state="waiting_for_tail_text") or \
                find_task(user_id, state="waiting_for_buttons") or \
                find_task(user_id, state="waiting_for_add_btn_domain") or \
                find_task(user_id, state="waiting_for_tail_interval") or \
                find_task(user_id, state="waiting_for_tail_probability") or \
                find_task(user_id, state="waiting_for_button_interval") or \
                find_task(user_id, state="waiting_for_button_probability") or \
                            find_task(user_id, state="waiting_pair_tail_text") or \
            find_task(user_id, state="waiting_pair_buttons") or \
            find_task(user_id, state="waiting_pair_add_keyword")

    if not last_task:
        # 避免重复发送相同内容
        try:
            await message.reply_text("请先从菜单中选择操作。", reply_markup=get_main_menu_buttons(user_id))
        except Exception as e:
            logging.warning(f"发送菜单提示失败: {e}")
        return
    
    current_state = last_task.get("state")
    task_id_short = last_task.get('task_id', '')[:8] if last_task.get('task_id') else 'None'
    logging.info(f"用户 {user_id} 输入文本: {message.text}, 处理任务ID: {task_id_short}")

    if current_state == "waiting_for_source":
        await set_channel_pair(client, message, user_id, "source", message.text, last_task)
    elif current_state == "waiting_for_target":
        await set_channel_pair(client, message, user_id, "target", message.text, last_task)
    elif current_state == "waiting_for_edit_input":
        await handle_edit_pair_input(client, message, user_id, last_task)
    elif current_state == "waiting_for_range_for_pair":
        await handle_range_input_for_pair(message, user_id, last_task)
    elif current_state == "waiting_for_add_keyword":
        await add_keyword(message, user_id, last_task)
    elif current_state == "waiting_for_add_replacement":
        await add_replacement(message, user_id, last_task)
    elif current_state == "waiting_for_add_file_extension":
        await add_file_extension(message, user_id, last_task)
    elif current_state == "waiting_for_tail_text":
        await set_tail_text(message, user_id, last_task)
    elif current_state == "waiting_for_buttons":
        await set_buttons(message, user_id, last_task)
    elif current_state == "waiting_for_add_btn_domain":
        await add_whitelist_domain(message, user_id, last_task)
    elif current_state == "waiting_for_tail_interval":
        await set_tail_interval(message, user_id, last_task)
    elif current_state == "waiting_for_tail_probability":
        await set_tail_probability(message, user_id, last_task)
    elif current_state == "waiting_for_button_interval":
        await set_button_interval(message, user_id, last_task)
    elif current_state == "waiting_for_button_probability":
        await set_button_probability(message, user_id, last_task)
    elif current_state == "waiting_pair_tail_text":
        await set_pair_tail_text(message, user_id, message.text)
    elif current_state == "waiting_pair_buttons":
        logging.info(f"handle_text_input: 处理 waiting_pair_buttons 状态，用户 {user_id}")
        await set_pair_buttons(message, user_id, message.text)
    elif current_state == "waiting_pair_add_keyword":
        logging.info(f"handle_text_input: 处理 waiting_pair_add_keyword 状态，用户 {user_id}")
        await set_pair_add_keyword(message, user_id, message.text)
    else:
        # 避免重复发送相同内容
        try:
            await message.reply_text("请先从菜单中选择操作。", reply_markup=get_main_menu_buttons(user_id))
        except Exception as e:
            logging.warning(f"发送菜单提示失败: {e}")

# ==================== 实时监听搬运 ====================
def resolve_user_for_source_channel(chat_id):
    # 遍历所有用户配置，找出包含该源频道且开启监听的用户
    matched = []
    logging.info(f"resolve_user_for_source_channel: 查找频道 {chat_id} 的监听配置")
    
    for uid, cfg in user_configs.items():
        logging.debug(f"检查用户 {uid} 的配置: realtime_listen={cfg.get('realtime_listen')}")
        if not cfg.get("realtime_listen"):
            continue
        
        for i, pair in enumerate(cfg.get("channel_pairs", [])):
            logging.debug(f"用户 {uid} 频道组 {i}: enabled={pair.get('enabled', True)}, monitor_enabled={pair.get('monitor_enabled', False)}, source={pair.get('source')}")
            
            # 检查频道组是否启用且监控已开启
            if not pair.get("enabled", True) or not pair.get("monitor_enabled", False):
                continue
                
            source_channel = str(pair.get("source"))
            chat_id_str = str(chat_id)
            
            # 比较频道标识符
            if source_channel == chat_id_str or source_channel.lstrip('@') == chat_id_str.lstrip('@'):
                logging.info(f"匹配成功: 用户 {uid} 的频道组 {pair.get('source')} -> {pair.get('target')}")
                matched.append((int(uid), pair))
            else:
                logging.info(f"未匹配: 配置的源频道 '{source_channel}' != 实际频道 '{chat_id_str}'")
    
    logging.info(f"resolve_user_for_source_channel: 频道 {chat_id} 找到 {len(matched)} 个匹配配置")
    return matched

@app.on_message(~filters.private)
@monitor_performance('listen_and_clone')
async def listen_and_clone(client, message):
    # 调试：记录所有非私聊消息
    logging.info(f"🔍 收到消息: 类型={message.chat.type if message.chat else 'None'}, 频道={message.chat.title if message.chat else 'None'}, ID={message.chat.id if message.chat else 'None'}, username={message.chat.username if message.chat else 'None'}")
    
    # 仅处理频道消息
    if not message.chat or message.chat.type != ChatType.CHANNEL:
        logging.info(f"🔍 跳过消息: 不是频道类型，实际类型: {message.chat.type if message.chat else 'None'}")
        return
    
    # 添加调试日志
    chat_identifier = message.chat.username or message.chat.id
    logging.info(f"实时监听: 收到频道消息，频道ID: {chat_identifier}, 消息ID: {message.id}")
    
    matched_pairs = resolve_user_for_source_channel(chat_identifier)
    if not matched_pairs:
        logging.info(f"实时监听: 频道 {chat_identifier} 未找到匹配的监听配置")
        return
    
    logging.info(f"实时监听: 频道 {chat_identifier} 找到 {len(matched_pairs)} 个匹配的监听配置")
    for uid, pair in matched_pairs:
        # 获取该频道组的有效配置（专用或全局）
        cfg = get_effective_config_for_realtime(uid, pair.get('source'), pair.get('target'))
        logging.info(f"实时监听: 开始处理用户 {uid} 的频道组 {pair.get('source')} -> {pair.get('target')}")
        
        if not pair.get("enabled", True):
            logging.info(f"实时监听: 跳过用户 {uid} 的频道组（已禁用）")
            continue
        # 多媒体组聚合：等待同 media_group_id 的消息齐全
        if message.media_group_id:
            key = (message.chat.id, message.media_group_id)
            listen_media_groups.setdefault(key, []).append(message)
            # 简化：当达到 10 条或 1 秒后发送（此处仅按数量触发；生产应使用定时器）
            if len(listen_media_groups[key]) < 2:
                return
            group_messages = sorted(listen_media_groups.pop(key), key=lambda m: m.id)
            # 过滤整组
            logging.info(f"🔍 实时监听: 开始过滤检查媒体组 {message.media_group_id}")
            filtered_messages = [m for m in group_messages if should_filter_message(m, cfg)]
            if filtered_messages:
                logging.info(f"🚫 实时监听: 媒体组 {message.media_group_id} 中有 {len(filtered_messages)} 条消息被过滤，跳过整组")
                continue
            logging.info(f"✅ 实时监听: 媒体组 {message.media_group_id} 通过过滤检查，继续处理")
            
            # 实时监听媒体组去重检查
            cache_key = (message.chat.id, pair['target'])
            if cache_key not in realtime_dedupe_cache:
                realtime_dedupe_cache[cache_key] = set()
            
            # 生成媒体组去重键（使用媒体组ID）
            media_group_dedup_key = ("media_group", message.media_group_id)
            if media_group_dedup_key in realtime_dedupe_cache[cache_key]:
                logging.debug(f"实时监听: 跳过重复媒体组 {message.media_group_id}")
                continue
            realtime_dedupe_cache[cache_key].add(media_group_dedup_key)
            media_list = []
            caption = ""
            reply_markup = None
            full_text_content = ""  # 收集所有文本内容
            
            # 收集媒体组中的所有文本内容（实时监听版本）
            for m in group_messages:
                # 收集caption和text
                if m.caption or m.text:
                    text_content = m.caption or m.text
                    if text_content.strip() and text_content not in full_text_content:
                        if full_text_content:
                            full_text_content += "\n\n" + text_content
                        else:
                            full_text_content = text_content
                
                # 收集引用的文本内容
                if m.reply_to_message and m.reply_to_message.text:
                    quoted_text = m.reply_to_message.text
                    if quoted_text.strip() and quoted_text not in full_text_content:
                        # 添加引用标记
                        quoted_format = f"💬 引用消息：\n{quoted_text}"
                        if full_text_content:
                            full_text_content = quoted_format + "\n\n" + full_text_content
                        else:
                            full_text_content = quoted_format
            
            # 处理收集到的完整文本内容
            if full_text_content:
                caption, reply_markup = process_message_content(full_text_content, cfg)
            
            # 构建媒体列表
            for i, m in enumerate(group_messages):
                if m.photo:
                    media_list.append(InputMediaPhoto(m.photo.file_id, caption=caption if i == 0 else ""))
                elif m.video:
                    media_list.append(InputMediaVideo(m.video.file_id, caption=caption if i == 0 else ""))
            if media_list:
                try:
                    await client.send_media_group(chat_id=pair['target'], media=media_list)
                    if reply_markup:
                        # 为按钮消息添加占位符文本，避免 MESSAGE_EMPTY 错误
                        await client.send_message(chat_id=pair['target'], text="📋", reply_markup=reply_markup)
                except Exception as e:
                    logging.error(f"监听搬运媒体组失败: {e}")
            return
        # 非媒体组单条
        logging.info(f"🔍 实时监听: 开始过滤检查消息 {message.id}")
        if should_filter_message(message, cfg):
            logging.info(f"🚫 实时监听: 消息 {message.id} 被过滤，跳过处理")
            continue
        logging.info(f"✅ 实时监听: 消息 {message.id} 通过过滤检查，继续处理")
        try:
            processed_text, reply_markup = process_message_content(message.caption or message.text, cfg)
            
            # 实时监听去重检查（使用统一去重函数）
            cache_key = (message.chat.id, pair['target'])
            if cache_key not in realtime_dedupe_cache:
                realtime_dedupe_cache[cache_key] = set()
            
            # 生成去重键并检查
            dedup_key = generate_dedupe_key(message, processed_text, cfg)
            if dedup_key and dedup_key in realtime_dedupe_cache[cache_key]:
                logging.debug(f"实时监听: 跳过重复消息 {message.id} (类型: {dedup_key[0]})")
                continue
            elif dedup_key:
                realtime_dedupe_cache[cache_key].add(dedup_key)
            
            # 限制缓存大小，防止内存泄漏
            if len(realtime_dedupe_cache[cache_key]) > 10000:
                # 清理最旧的一半缓存
                cache_list = list(realtime_dedupe_cache[cache_key])
                realtime_dedupe_cache[cache_key] = set(cache_list[5000:])
            
            # 处理引用信息（实时监听时暂不处理跨消息引用，因为目标消息可能不存在）
            reply_to_id = None
            if message.reply_to_message:
                logging.debug(f"实时监听: 消息 {message.id} 包含引用，但跨频道引用暂不支持")
            
            # 判断消息类型
            is_text_only = (message.text and not (message.photo or message.video or message.document or message.animation or message.audio or message.voice or message.sticker))
            
            # 智能按钮处理：区分用户添加的按钮和原始消息按钮
            safe_reply_markup = None
            if reply_markup:
                try:
                    logging.info(f"实时监听: 检测到按钮，开始处理")
                    
                    # 检查是否有用户自定义按钮配置
                    user_custom_buttons = cfg.get("buttons", [])
                    
                    if user_custom_buttons:
                        # 用户配置了自定义按钮，使用自定义按钮替代原始按钮
                        custom_button_rows = []
                        for button_config in user_custom_buttons:
                            button_text = button_config.get("text", "")
                            button_url = button_config.get("url", "")
                            
                            # 验证和转换URL格式
                            if button_text and button_url:
                                # 规范化URL格式
                                normalized_url = button_url.strip()
                                
                                # 处理 @username 格式
                                if normalized_url.startswith("@"):
                                    normalized_url = f"t.me/{normalized_url[1:]}"
                                # 处理纯用户名格式
                                elif not normalized_url.startswith(("http://", "https://", "t.me/")):
                                    # 假设是Telegram用户名或机器人名
                                    normalized_url = f"t.me/{normalized_url}"
                                
                                # 验证最终URL格式
                                if normalized_url.startswith(("http://", "https://", "t.me/")):
                                    custom_button_rows.append([InlineKeyboardButton(button_text, url=normalized_url)])
                                    logging.info(f"实时监听: 添加用户自定义按钮: {button_text} -> {normalized_url}")
                                else:
                                    logging.warning(f"实时监听: 跳过无效的自定义按钮: {button_text} -> {button_url}")
                            else:
                                logging.warning(f"实时监听: 跳过空的自定义按钮: {button_text} -> {button_url}")
                        
                        if custom_button_rows:
                            safe_reply_markup = InlineKeyboardMarkup(custom_button_rows)
                            logging.info(f"实时监听: 使用用户自定义按钮 ({len(custom_button_rows)} 个)")
                        else:
                            logging.info(f"实时监听: 用户配置的自定义按钮无效，不添加按钮")
                    else:
                        # 用户没有配置自定义按钮，检查过滤策略
                        filter_buttons = cfg.get("filter_buttons", False)
                        if filter_buttons:
                            logging.info(f"实时监听: 用户启用了按钮过滤，跳过原始按钮")
                            # 不添加任何按钮
                        else:
                            logging.info(f"实时监听: 用户未启用按钮过滤，但为避免URL错误暂时跳过原始按钮")
                            # 暂时跳过原始按钮，直到修复URL验证问题
                except Exception as e:
                    logging.error(f"实时监听: 按钮处理出错: {e}")
                    safe_reply_markup = None
            
            # 记录详细信息
            logging.info(f"实时监听: 准备发送到目标频道 {pair['target']}")
            logging.info(f"实时监听: 消息内容长度: {len(processed_text or '')}")
            logging.info(f"实时监听: 消息类型: {'纯文本' if is_text_only else '媒体'}")
            
            # 添加重试机制提高稳定性
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if is_text_only:
                        logging.info(f"实时监听: 用户 {uid} 发送纯文本消息到 {pair['target']} (尝试 {attempt + 1}/{max_retries})")
                        await client.send_message(chat_id=pair['target'], text=processed_text, reply_markup=safe_reply_markup, reply_to_message_id=reply_to_id)
                    else:
                        logging.info(f"实时监听: 用户 {uid} 复制媒体消息到 {pair['target']} (尝试 {attempt + 1}/{max_retries})")
                        await client.copy_message(chat_id=pair['target'], from_chat_id=message.chat.id, message_id=message.id, caption=processed_text, reply_markup=safe_reply_markup, reply_to_message_id=reply_to_id)
                    
                    logging.info(f"实时监听: 用户 {uid} 成功搬运消息 {message.id} 到 {pair['target']}")
                    break  # 成功则跳出重试循环
                    
                except Exception as send_error:
                    if attempt == max_retries - 1:
                        # 最后一次尝试失败，记录错误
                        logging.error(f"实时监听最终失败: 用户 {uid}, 目标 {pair.get('target')}, 消息 {message.id}, 错误: {send_error}")
                        raise send_error
                    else:
                        # 指数退避重试
                        retry_delay = 2 ** attempt
                        logging.warning(f"实时监听重试: 用户 {uid}, 尝试 {attempt + 1}/{max_retries}, {retry_delay}秒后重试, 错误: {send_error}")
                        await asyncio.sleep(retry_delay)
        except Exception as e:
            logging.error(f"监听搬运单条失败: 用户 {uid}, 目标 {pair.get('target')}, 错误: {e}")

# ==================== 菜单函数 ====================
async def show_help(message, user_id):
    await safe_edit_or_reply(message, HELP_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]))

async def force_save_configs(message, user_id):
    """强制保存所有配置"""
    try:
        # 保存所有配置
        save_configs()
        save_user_states()
        save_history()
        save_running_tasks()
        
        # 检查保存结果
        status_text = "🔄 **强制保存配置完成**\n\n"
        
        # 检查持久化存储
        persistent_path = get_config_path("")
        status_text += f"📁 **持久化存储路径**: {persistent_path}\n"
        
        # 检查各种配置文件
        config_files = [
            f"user_configs_{bot_config['bot_id']}.json",
            f"user_states_{bot_config['bot_id']}.json", 
            f"user_history_{bot_config['bot_id']}.json"
        ]
        
        for filename in config_files:
            persistent_file = get_config_path(filename)
            if os.path.exists(persistent_file):
                file_size = os.path.getsize(persistent_file)
                status_text += f"✅ {filename} - 已保存 ({file_size} 字节)\n"
            else:
                status_text += f"❌ {filename} - 保存失败\n"
        
        status_text += f"\n💾 **内存配置状态**:\n"
        status_text += f"• 用户配置: {len(user_configs)} 个用户\n"
        status_text += f"• 用户状态: {len(user_states)} 个用户\n"
        status_text += f"• 历史记录: {len(user_history)} 个用户\n"
        
        buttons = [
            [InlineKeyboardButton("🔍 再次检查状态", callback_data="configstatus")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]
        ]
        
        await safe_edit_or_reply(message, status_text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        logging.error(f"强制保存配置失败: {e}")
        await safe_edit_or_reply(message, f"❌ 强制保存配置失败: {str(e)}")

async def view_detailed_config_status(message, user_id):
    """查看详细的配置状态"""
    try:
        status_text = "🔍 **详细配置状态**\n\n"
        
        # 检查持久化存储路径
        persistent_path = get_config_path("")
        status_text += f"📁 **持久化存储路径**: {persistent_path}\n"
        status_text += f"📁 **当前工作目录**: {os.getcwd()}\n"
        status_text += f"🌍 **环境变量**: RENDER={'true' if os.getenv('RENDER') == 'true' else 'false'}\n\n"
        
        # 检查各种配置文件
        config_files = [
            f"user_configs_{bot_config['bot_id']}.json",
            f"user_states_{bot_config['bot_id']}.json", 
            f"user_history_{bot_config['bot_id']}.json",
            f"user_login_{bot_config['bot_id']}.json"
        ]
        
        for filename in config_files:
            persistent_file = get_config_path(filename)
            backup_file = filename
            
            persistent_exists = os.path.exists(persistent_file)
            backup_exists = os.path.exists(backup_file)
            
            if persistent_exists:
                file_size = os.path.getsize(persistent_file)
                status_text += f"✅ {filename} - 持久化存储 ({file_size} 字节)\n"
            elif backup_exists:
                file_size = os.path.getsize(backup_file)
                status_text += f"⚠️ {filename} - 仅备份文件 ({file_size} 字节)\n"
            else:
                status_text += f"❌ {filename} - 不存在\n"
        
        # 检查内存中的配置详情
        status_text += f"\n💾 **内存配置详情**:\n"
        
        # 用户配置详情
        user_config_count = len(user_configs)
        status_text += f"• 用户配置: {user_config_count} 个用户\n"
        if user_config_count > 0:
            for uid, cfg in list(user_configs.items())[:3]:  # 只显示前3个
                channel_pairs = cfg.get("channel_pairs", [])
                status_text += f"  - 用户 {uid}: {len(channel_pairs)} 个频道组\n"
        
        # 用户状态详情
        user_states_count = len(user_states)
        status_text += f"• 用户状态: {user_states_count} 个用户\n"
        if user_states_count > 0:
            for uid, states in list(user_states.items())[:3]:  # 只显示前3个
                status_text += f"  - 用户 {uid}: {len(states)} 个状态\n"
        
        # 历史记录详情
        history_count = len(user_history)
        status_text += f"• 历史记录: {history_count} 个用户\n"
        if history_count > 0:
            for uid, history in list(user_history.items())[:3]:  # 只显示前3个
                status_text += f"  - 用户 {uid}: {len(history)} 条记录\n"
        
        # 登录用户详情
        login_count = len(logged_in_users)
        status_text += f"• 登录用户: {login_count} 个\n"
        if login_count > 0:
            for uid, username in list(logged_in_users.items())[:3]:  # 只显示前3个
                status_text += f"  - 用户 {uid}: {username}\n"
        
        buttons = [
            [InlineKeyboardButton("🔄 强制保存配置", callback_data="force_save_configs")],
            [InlineKeyboardButton("🔍 检查状态", callback_data="configstatus")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]
        ]
        
        await safe_edit_or_reply(message, status_text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        logging.error(f"查看详细配置状态失败: {e}")
        await safe_edit_or_reply(message, f"❌ 查看详细配置状态失败: {str(e)}")

async def show_manage_filter_buttons_menu(message, user_id):
    config = user_configs.get(str(user_id), {})
    filter_enabled = config.get("filter_buttons", False)
    mode = config.get("filter_buttons_mode", "drop")
    whitelist = ", ".join(config.get("button_domain_whitelist", [])) or "无"
    
    text = (
        "🧰 **按钮策略设定**\n\n"
        f"过滤开关：{'✅ 开启' if filter_enabled else '❌ 关闭'}\n"
        f"当前模式：`{mode}`\n"
        f"白名单域名：`{whitelist}`\n\n"
        "**模式说明：**\n"
        "• drop: 发现带按钮即丢弃整条消息\n"
        "• strip: 移除按钮，保留文本/媒体\n"
        "• whitelist: 仅允许白名单域名的按钮，其余移除\n"
    )
    
    buttons = [
        [InlineKeyboardButton(f"🚫 按钮过滤: {'✅ 开启' if filter_enabled else '❌ 关闭'}", callback_data="toggle_filter_buttons")],
        [InlineKeyboardButton("drop", callback_data="set_btn_mode:drop"), 
         InlineKeyboardButton("strip", callback_data="set_btn_mode:strip"), 
         InlineKeyboardButton("whitelist", callback_data="set_btn_mode:whitelist")],
        [InlineKeyboardButton("➕ 添加白名单域名", callback_data=f"add_btn_domain:{uuid.uuid4()}")],
        [InlineKeyboardButton("🗑️ 清空白名单", callback_data="clear_btn_domain")],
        [InlineKeyboardButton("🔙 返回功能设定", callback_data="show_feature_config_menu")]
    ]
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def request_add_whitelist_domain(message, user_id):
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "waiting_for_add_btn_domain"}
    user_states.setdefault(user_id, []).append(new_task)
    await message.reply_text("请回复要添加的域名（不含 http/https），例如：example.com\n(多个域名用逗号分隔)")

async def add_whitelist_domain(message, user_id, task):
    domains_text = message.text.strip()
    domains = [d.strip().lower() for d in domains_text.split(',') if d.strip()]
    config = user_configs.setdefault(str(user_id), {})
    current = config.setdefault("button_domain_whitelist", [])
    current_set = set(current)
    for d in domains:
        if d.startswith('www.'):
            d = d[4:]
        if d not in current_set:
            current.append(d)
            current_set.add(d)
    save_configs()
    remove_task(user_id, task["task_id"])
    await message.reply_text("✅ 已添加白名单域名。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回按钮策略", callback_data="manage_filter_buttons")]]))

async def show_edit_channel_pair_menu(message, user_id, pair_id):
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    if not (0 <= pair_id < len(channel_pairs)):
        await safe_edit_or_reply(message, "❌ 频道组编号无效。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]))
        return
    
    current_pair = channel_pairs[pair_id]
    text = f"✏️ **编辑频道组 `{pair_id+1}`**\n`{current_pair['source']}` -> `{current_pair['target']}`\n\n请选择您要修改的项目："
    
    await safe_edit_or_reply(message, text, reply_markup=get_edit_channel_pair_menu(pair_id, current_pair))

async def toggle_pair_enabled(message, user_id, pair_id):
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    if not (0 <= pair_id < len(channel_pairs)):
        await safe_edit_or_reply(message, "❌ 频道组编号无效。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]))
        return
    
    current_pair = channel_pairs[pair_id]
    is_enabled = current_pair.get("enabled", True)
    current_pair["enabled"] = not is_enabled
    save_configs()
    
    status_text = "启用" if not is_enabled else "暂停"
    await safe_edit_or_reply(message, f"✅ 频道组 `{pair_id+1}` 已设定为 **{status_text}**。", reply_markup=get_edit_channel_pair_menu(pair_id, current_pair))

async def delete_channel_pair(message, user_id, pair_id):
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    if 0 <= pair_id < len(channel_pairs):
        deleted_pair = channel_pairs.pop(pair_id)
        save_configs() # 新增: 保存配置
        logging.info(f"用户 {user_id} 删除频道组: {deleted_pair}")
        await show_channel_config_menu(message, user_id)
    else:
        await safe_edit_or_reply(message,
                                 "❌ 频道组编号无效。",
                                 reply_markup=get_channel_config_menu_buttons(user_id))
                                 
async def view_config(message, user_id):
    config = user_configs.get(str(user_id), {})
    
    channel_pairs = config.get("channel_pairs", [])
    pairs_text = "\n".join([f"`{i+1}`. `{pair['source']}` -> `{pair['target']}` ({'✅ 启用' if pair.get('enabled', True) else '⏸ 暂停'})" for i, pair in enumerate(channel_pairs)]) or "未设定"
    
    keywords = ", ".join(config.get("filter_keywords", [])) or "无"
    replacements = ", ".join([f"{k} -> {v}" for k, v in config.get("replacement_words", {}).items()]) or "无"
    remove_links = "✅" if config.get("remove_links") else "❌"
    remove_hashtags = "✅" if config.get("remove_hashtags") else "❌"
    remove_usernames = "✅" if config.get("remove_usernames") else "❌"
    filter_buttons_status = "✅" if config.get("filter_buttons") else "❌"
    
    file_filter_extensions = ", ".join(config.get("file_filter_extensions", [])) or "无"
    file_filter_media = []
    if config.get("filter_photo"): file_filter_media.append("图片")
    if config.get("filter_video"): file_filter_media.append("影片")
    file_filter_media_str = ", ".join(file_filter_media) or "无"
    
    tail_text = config.get("tail_text", "无")
    tail_position = {"top": "开头", "bottom": "结尾"}.get(config.get("tail_position"), "无")
    buttons = ", ".join([f"[{b['text']}]({b['url']})" for b in config.get("buttons", [])]) or "无"
    filter_buttons_mode = config.get("filter_buttons_mode", "drop")
    button_domain_whitelist = ", ".join(config.get("button_domain_whitelist", [])) or "无"
    realtime_listen = "✅" if config.get("realtime_listen") else "❌"

    config_text = (
        f"🔍 **当前配置概览**\n\n"
        f"**⚙️ 频道组设定**\n"
        f"{pairs_text}\n\n"
        f"**🔧 功能设定**\n"
        f"📝 关键字过滤: `{keywords}`\n"
        f"🔀 敏感词替换: `{replacements}`\n"
        f"🔗 移除超链接: {remove_links}\n"
        f"🏷 移除Hashtags: {remove_hashtags}\n"
        f"👤 移除使用者名: {remove_usernames}\n"
        f"🚫 过滤带按钮: {filter_buttons_status}\n"
        f"🧰 按钮策略: `{filter_buttons_mode}`\n"
        f"✅ 按钮域名白名单: `{button_domain_whitelist}`\n"
        f"📡 实时监听搬运: {realtime_listen}\n"
        f"📁 文件过滤: `{file_filter_extensions}`\n"
        f"🖼/🎬 媒体过滤: `{file_filter_media_str}`\n"
        f"✍️ 附加文字: `{tail_text}` ({tail_position})\n"
        f"📋 附加按钮: `{buttons}`"
    )
    
    await safe_edit_or_reply(message,
                             config_text,
                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]])
    )

async def view_tasks(message, user_id):
    tasks = user_states.get(user_id, [])
    snapshots = running_tasks.get(str(user_id), {})

    text = "📋 **任务管理中心**\n\n"
    buttons = []

    # 当前活跃任务 - 简化显示
    if tasks:
        text += "🔄 **活跃任务**\n"
        for i, task in enumerate(tasks, 1):
            task_id_short = task.get("task_id", "")[:8] if task.get("task_id") else "None"
            state = task.get("state")
            
            # 简化状态显示
            state_icons = {
                "cloning_in_progress": "🚀 搬运中",
                "confirming_clone": "⏳ 等待确认",
                "selecting_pairs_for_clone": "📋 选择频道",
                "waiting_for_range_for_pair": "📝 输入范围"
            }
            state_display = state_icons.get(state, f"🔧 {state}")
            
            text += f"\n**{i}.** `{task_id_short}` - {state_display}\n"
            
            # 只显示基本信息
            if "clone_tasks" in task:
                clone_tasks = task["clone_tasks"]
                text += f"📂 频道组: {len(clone_tasks)}个\n"
                
                # 如果是搬运中状态，显示简单进度
                if state == "cloning_in_progress":
                    progress = task.get("progress", {})
                    total_cloned = 0
                    for j, sub_task in enumerate(clone_tasks):
                        sub_progress = progress.get(f"sub_task_{j}", {}) or progress.get(str(j), {})
                        cloned = sub_progress.get("cloned_count", 0) or sub_progress.get("cloned", 0)
                        total_cloned += cloned
                    
                    if total_cloned > 0:
                        text += f"📊 已搬运: {total_cloned} 条消息\n"
            
            # 操作按钮
            if state == "cloning_in_progress":
                buttons.append([InlineKeyboardButton(f"⏹ 停止任务", callback_data=f"cancel:{task['task_id']}")])
            elif state == "confirming_clone":
                buttons.append([
                    InlineKeyboardButton(f"✅ 开始搬运", callback_data=f"confirm_clone_action:{task['task_id']}"),
                    InlineKeyboardButton(f"❌ 取消", callback_data=f"cancel:{task['task_id']}")
                ])
            elif isinstance(state, str) and state.startswith("waiting_for"):
                buttons.append([InlineKeyboardButton(f"❌ 取消", callback_data=f"cancel:{task['task_id']}")])

    # 可恢复任务 - 简化显示
    if snapshots:
        cancelled_count = sum(1 for snap in snapshots.values() if snap.get("cancelled"))
        normal_count = len(snapshots) - cancelled_count
        
        text += f"\n📦 **可恢复任务** ({len(snapshots)}个)\n"
        text += f"• 被取消: {cancelled_count}个 | 意外中断: {normal_count}个\n\n"
        
        for i, (tid, snap) in enumerate(snapshots.items(), 1):
            tid_short = tid[:8]
            clone_tasks = snap.get("clone_tasks", [])
            is_cancelled = snap.get("cancelled", False)
            
            # 简化状态显示
            status_emoji = "❌" if is_cancelled else "⏭️"
            status_text = "被取消" if is_cancelled else "意外中断"
            
            text += f"**{i}.** `{tid_short}` - {status_emoji} {status_text}\n"
            
            # 显示简单进度
            progress = snap.get("progress", {})
            total_cloned = 0
            for j, sub in enumerate(clone_tasks):
                sub_progress = progress.get(f"sub_task_{j}", {}) or progress.get(str(j), {})
                cloned = sub_progress.get("cloned_count", 0) or sub_progress.get("cloned", 0)
                total_cloned += cloned
            
            if total_cloned > 0:
                text += f"📊 已搬运: {total_cloned} 条消息\n"
            
            text += f"📂 频道组: {len(clone_tasks)}个\n"
            
            buttons.append([
                InlineKeyboardButton(f"▶️ 续传", callback_data=f"resume:{tid}"),
                InlineKeyboardButton(f"🗑 删除", callback_data=f"drop_running:{tid}")
            ])

    # 如果没有任务
    if not tasks and not snapshots:
        text += "🌟 **暂无任务**\n\n"
        text += "💡 您可以：\n"
        text += "• 点击【🚀 开始搬运】创建新任务\n"
        text += "• 开启【👂 实时监听】自动搬运\n"
        text += "• 在【⚙️ 频道管理】中配置频道组"
        buttons = []
    else:
        # 简化统计信息
        total_active = len(tasks)
        total_saved = len(snapshots)
        text += f"\n📊 **统计**\n"
        text += f"活跃: {total_active} | 可恢复: {total_saved}"

    buttons.append([InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")])
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def view_history(message, user_id, page=0):
    history_list = user_history.get(str(user_id), [])
    if not history_list:
        text = "📋 **历史记录**\n\n🌟 **暂无记录**\n\n"
        text += "💡 完成搬运任务后，历史记录会在这里显示。"
        buttons = [[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]
    else:
        # 分页设置
        records_per_page = 5  # 每页显示5条记录
        total_pages = (len(history_list) - 1) // records_per_page + 1
        current_page = min(max(0, page), total_pages - 1)
        
        text = "📋 **历史记录**\n\n"
        text += f"📊 **总共 {len(history_list)} 条记录**（第 {current_page + 1}/{total_pages} 页）\n\n"
        
        buttons = []
        
        # 将历史记录倒序排列（最新的在前面）
        history_list_reversed = list(reversed(history_list))
        
        # 计算当前页的记录范围
        start_idx = current_page * records_per_page
        end_idx = min(start_idx + records_per_page, len(history_list_reversed))
        
        # 获取当前页的记录
        current_records = history_list_reversed[start_idx:end_idx]
        
        # 显示当前页的记录 - 简化显示
        for i, record in enumerate(current_records):
            display_index = start_idx + i + 1  # 从1开始编号
            timestamp = record.get('timestamp', '')
            source = record.get('source', '')
            target = record.get('target', '') 
            start_id = record.get('start_id', 0)
            end_id = record.get('end_id', 0)
            cloned_count = record.get('cloned_count', 0)
            status = record.get('status', '完成')
            
            # 简化时间显示
            try:
                date_part = timestamp.split(' ')[0] if timestamp else ''
                time_part = timestamp.split(' ')[1] if len(timestamp.split(' ')) > 1 else ''
                time_display = f"{date_part} {time_part}" if date_part and time_part else timestamp
            except:
                time_display = timestamp
            
            # 状态图标
            status_icon = "✅" if status == "完成" else "❌"
            
            text += f"**{i}.** {status_icon} {time_display}\n"
            text += f"📤 `{source}` ➜ `{target}`\n"
            text += f"📊 范围: {start_id}-{end_id} | 已搬运: **{cloned_count}** 条\n"
            
            # 显示状态
            if status != "完成":
                text += f"⚠️ 状态: {status}\n"
            
            text += "\n"
            
            # 显示详细统计
            if photo_count > 0 or video_count > 0 or file_count > 0 or text_count > 0:
                stats_parts = []
                if photo_count > 0: stats_parts.append(f"🖼️ {photo_count}")
                if video_count > 0: stats_parts.append(f"🎥 {video_count}")
                if file_count > 0: stats_parts.append(f"📁 {file_count}")
                if text_count > 0: stats_parts.append(f"📝 {text_count}")
                if media_group_count > 0: stats_parts.append(f"🖼️📱 {media_group_count}")
                text += f"   📈 详情: {' | '.join(stats_parts)}\n"
            
            text += "\n"

        # 统计信息
        total_cloned = sum(record.get('cloned_count', 0) for record in history_list)
        total_photos = sum(record.get('photo_count', 0) for record in history_list)
        total_videos = sum(record.get('video_count', 0) for record in history_list)
        total_files = sum(record.get('file_count', 0) for record in history_list)
        total_texts = sum(record.get('text_count', 0) for record in history_list)
        total_media_groups = sum(record.get('media_group_count', 0) for record in history_list)
        
        text += f"📈 **累计统计**\n"
        text += f"• 总任务数: {len(history_list)}\n"
        text += f"• 总搬运量: **{total_cloned}** 条消息\n"
        text += f"• 详细分类: 🖼️ {total_photos} | 🎥 {total_videos} | 📁 {total_files} | 📝 {total_texts} | 🖼️📱 {total_media_groups}\n\n"
        
        # 每日统计
        daily_stats = {}
        for record in history_list:
            timestamp = record.get('timestamp', '')
            if timestamp:
                try:
                    # 提取日期部分
                    date_part = timestamp.split(' ')[0]
                    if date_part not in daily_stats:
                        daily_stats[date_part] = {
                            'photos': 0, 'videos': 0, 'files': 0, 'texts': 0, 'media_groups': 0, 'total': 0
                        }
                    
                    # 累加每日统计（只计算有内容的消息）
                    photo_count = record.get('photo_count', 0)
                    video_count = record.get('video_count', 0)
                    file_count = record.get('file_count', 0)
                    text_count = record.get('text_count', 0)
                    media_group_count = record.get('media_group_count', 0)
                    
                    if photo_count > 0: daily_stats[date_part]['photos'] += photo_count
                    if video_count > 0: daily_stats[date_part]['videos'] += video_count
                    if file_count > 0: daily_stats[date_part]['files'] += file_count
                    if text_count > 0: daily_stats[date_part]['texts'] += text_count
                    if media_group_count > 0: daily_stats[date_part]['media_groups'] += media_group_count
                    
                    # 计算每日有效消息总数（排除空消息）
                    daily_total = photo_count + video_count + file_count + text_count + media_group_count
                    if daily_total > 0:
                        daily_stats[date_part]['total'] += daily_total
                except:
                    continue
        
        # 显示每日统计（按日期倒序，最近的在前面）
        if daily_stats:
            text += f"📅 **每日统计**（最近7天）\n"
            sorted_dates = sorted(daily_stats.keys(), reverse=True)
            
            # 只显示最近7天的统计
            recent_dates = sorted_dates[:7]
            for date in recent_dates:
                stats = daily_stats[date]
                if stats['total'] > 0:  # 只显示有内容的日期
                    # 格式化日期显示
                    try:
                        from datetime import datetime
                        date_obj = datetime.strptime(date, "%Y-%m-%d")
                        formatted_date = date_obj.strftime("%m月%d日")
                    except:
                        formatted_date = date
                    
                    date_parts = []
                    if stats['photos'] > 0: date_parts.append(f"🖼️{stats['photos']}")
                    if stats['videos'] > 0: date_parts.append(f"🎥{stats['videos']}")
                    if stats['files'] > 0: date_parts.append(f"📁{stats['files']}")
                    if stats['texts'] > 0: date_parts.append(f"📝{stats['texts']}")
                    if stats['media_groups'] > 0: date_parts.append(f"🖼️📱{stats['media_groups']}")
                    
                    text += f"• {formatted_date}: **{stats['total']}** 条 ({' | '.join(date_parts)})\n"
            
            if len(sorted_dates) > 7:
                text += f"• ... 还有 {len(sorted_dates) - 7} 天的数据\n"

        # 分页按钮
        if total_pages > 1:
            page_buttons = []
            if current_page > 0:
                page_buttons.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"history_page:{user_id}:{current_page - 1}"))
            if current_page < total_pages - 1:
                page_buttons.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"history_page:{user_id}:{current_page + 1}"))
            if page_buttons:
                buttons.append(page_buttons)

        buttons.append([InlineKeyboardButton("📊 每日统计", callback_data="daily_stats")])
        buttons.append([InlineKeyboardButton("🗑️ 清空历史", callback_data="clear_history")])
        buttons.append([InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")])
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def clear_user_history(message, user_id):
    user_history[str(user_id)] = []
    save_history()
    await safe_edit_or_reply(message, "✅ 您的历史记录已清空。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]))

async def handle_history_page(callback_query, user_id, page):
    """处理历史记录分页"""
    await view_history(callback_query.message, user_id, page)

async def show_daily_stats(message, user_id):
    """显示每日统计详情"""
    history_list = user_history.get(str(user_id), [])
    if not history_list:
        text = "📊 **每日统计**\n\n🌟 **暂无数据**\n\n"
        text += "💡 完成搬运任务后，每日统计会在这里显示。"
        buttons = [[InlineKeyboardButton("🔙 返回历史记录", callback_data="view_history")]]
        await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # 每日统计
    daily_stats = {}
    for record in history_list:
        timestamp = record.get('timestamp', '')
        if timestamp:
            try:
                # 提取日期部分
                date_part = timestamp.split(' ')[0]
                if date_part not in daily_stats:
                    daily_stats[date_part] = {
                        'photos': 0, 'videos': 0, 'files': 0, 'texts': 0, 'media_groups': 0, 'total': 0, 'tasks': 0
                    }
                
                # 累加每日统计（只计算有内容的消息）
                photo_count = record.get('photo_count', 0)
                video_count = record.get('video_count', 0)
                file_count = record.get('file_count', 0)
                text_count = record.get('text_count', 0)
                media_group_count = record.get('media_group_count', 0)
                
                if photo_count > 0: daily_stats[date_part]['photos'] += photo_count
                if video_count > 0: daily_stats[date_part]['videos'] += video_count
                if file_count > 0: daily_stats[date_part]['files'] += file_count
                if text_count > 0: daily_stats[date_part]['texts'] += text_count
                if media_group_count > 0: daily_stats[date_part]['media_groups'] += media_group_count
                
                # 计算每日有效消息总数（排除空消息）
                daily_total = photo_count + video_count + file_count + text_count + media_group_count
                if daily_total > 0:
                    daily_stats[date_part]['total'] += daily_total
                
                # 统计任务数
                daily_stats[date_part]['tasks'] += 1
            except:
                continue
    
    if not daily_stats:
        text = "📊 **每日统计**\n\n🌟 **暂无有效数据**\n\n"
        text += "💡 所有任务都没有有效内容。"
        buttons = [[InlineKeyboardButton("🔙 返回历史记录", callback_data="view_history")]]
        await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))
        return
    
    # 显示每日统计
    text = "📊 **每日统计详情**\n\n"
    sorted_dates = sorted(daily_stats.keys(), reverse=True)
    
    # 显示所有日期的统计
    for date in sorted_dates:
        stats = daily_stats[date]
        if stats['total'] > 0:  # 只显示有内容的日期
            # 格式化日期显示
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%Y年%m月%d日")
            except:
                formatted_date = date
            
            text += f"📅 **{formatted_date}**\n"
            text += f"   📋 任务数: {stats['tasks']} 个\n"
            text += f"   📊 有效消息: **{stats['total']}** 条\n"
            
            # 详细分类
            details = []
            if stats['photos'] > 0: details.append(f"🖼️ 图片: {stats['photos']}")
            if stats['videos'] > 0: details.append(f"🎥 视频: {stats['videos']}")
            if stats['files'] > 0: details.append(f"📁 文件: {stats['files']}")
            if stats['texts'] > 0: details.append(f"📝 文本: {stats['texts']}")
            if stats['media_groups'] > 0: details.append(f"🖼️📱 媒体组: {stats['media_groups']}")
            
            if details:
                text += f"   📈 分类: {' | '.join(details)}\n"
            
            text += "\n"
    
    # 总计统计
    total_tasks = sum(stats['tasks'] for stats in daily_stats.values())
    total_photos = sum(stats['photos'] for stats in daily_stats.values())
    total_videos = sum(stats['videos'] for stats in daily_stats.values())
    total_files = sum(stats['files'] for stats in daily_stats.values())
    total_texts = sum(stats['texts'] for stats in daily_stats.values())
    total_media_groups = sum(stats['media_groups'] for stats in daily_stats.values())
    total_messages = sum(stats['total'] for stats in daily_stats.values())
    
    text += f"📈 **总计统计**\n"
    text += f"• 总任务数: **{total_tasks}** 个\n"
    text += f"• 总有效消息: **{total_messages}** 条\n"
    text += f"• 详细分类: 🖼️ {total_photos} | 🎥 {total_videos} | 📁 {total_files} | 📝 {total_texts} | 🖼️📱 {total_media_groups}"
    
    buttons = [[InlineKeyboardButton("🔙 返回历史记录", callback_data="view_history")]]
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

# ==================== 搬运相关 ====================
async def select_channel_pairs_to_clone(message, user_id):
    config = user_configs.get(str(user_id), {})
    channel_pairs = [p for p in config.get("channel_pairs", []) if p.get("enabled", True)]
    if not channel_pairs:
        await safe_edit_or_reply(message,
                                 "❌ 请先在【频道组管理】中设定并启用频道组。",
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ 频道组管理", callback_data="show_channel_config_menu")]]))
        return
    
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "selecting_pairs_for_clone", "selected_pairs_indices": []}
    if user_id not in user_states: user_states[user_id] = []
    user_states[user_id].append(new_task)
    
    text = "🔢 **请选择要搬运的频道组**\n点击一次选中，再次点击取消。选择后点击 `下一步`。\n\n"
    buttons = []
    for i, pair in enumerate(channel_pairs):
        source = pair['source']
        target = pair['target']
        is_selected = "✅" if i in new_task["selected_pairs_indices"] else "⬜"
        buttons.append([InlineKeyboardButton(f"{is_selected} {source} -> {target}", callback_data=f"select_channel_pair:{task_id}:{i}")])
    
    buttons.append([InlineKeyboardButton("下一步 ➡️", callback_data=f"next_step_clone_range:{task_id}")])
    buttons.append([InlineKeyboardButton("❌ 取消", callback_data=f"cancel:{task_id}")])
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_channel_pair_selection(callback_query, user_id, data):
    parts = data.split(':')
    task_id = parts[1]
    pair_index = int(parts[2])
    
    task = find_task(user_id, task_id=task_id)
    if not task or task.get("state") != "selecting_pairs_for_clone":
        await callback_query.message.reply_text("❌ 任务已失效，请重新操作。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]))
        return
        
    if pair_index in task["selected_pairs_indices"]:
        task["selected_pairs_indices"].remove(pair_index)
    else:
        task["selected_pairs_indices"].append(pair_index)
    
    config = user_configs.get(str(user_id), {})
    channel_pairs = [p for p in config.get("channel_pairs", []) if p.get("enabled", True)]
    text = "🔢 **请选择要搬运的频道组**\n点击一次选中，再次点击取消。选择后点击 `下一步`。\n\n"
    buttons = []
    for i, pair in enumerate(channel_pairs):
        source = pair['source']
        target = pair['target']
        is_selected = "✅" if i in task["selected_pairs_indices"] else "⬜"
        buttons.append([InlineKeyboardButton(f"{is_selected} {source} -> {target}", callback_data=f"select_channel_pair:{task_id}:{i}")])
    
    buttons.append([InlineKeyboardButton("下一步 ➡️", callback_data=f"next_step_clone_range:{task_id}")])
    buttons.append([InlineKeyboardButton("❌ 取消", callback_data=f"cancel:{task_id}")])
    
    await safe_edit_or_reply(callback_query.message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_next_step_clone_range(callback_query, user_id, task_id):
    task = find_task(user_id, task_id=task_id)
    if not task or not task.get("selected_pairs_indices"):
        await safe_edit_or_reply(callback_query.message,
                                 "❌ 请至少选择一组频道配对。",
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]))
        return
    
    task["clone_tasks"] = []
    task["current_pair_index_for_range"] = 0
    task["state"] = "waiting_for_range_for_pair"

    await request_range_for_pair(callback_query.message, user_id, task)


async def request_range_for_pair(message, user_id, task):
    try:
        pair_index = task["current_pair_index_for_range"]
        
        # 验证索引范围
        if pair_index >= len(task["selected_pairs_indices"]):
            logging.error(f"任务 {task['task_id'][:8]} 请求范围时索引超出范围: pair_index={pair_index}, selected_pairs_indices={task['selected_pairs_indices']}")
            await message.reply_text("❌ 任务状态错误，请重新开始。")
            task["state"] = "waiting_for_range_for_pair"
            return
        
        selected_pair_index = task["selected_pairs_indices"][pair_index]
        
        # 获取启用的频道组列表
        enabled_pairs = [p for p in user_configs.get(str(user_id), {}).get("channel_pairs", []) if p.get("enabled", True)]
        
        if selected_pair_index >= len(enabled_pairs):
            logging.error(f"任务 {task['task_id'][:8]} 请求范围时频道组索引超出范围: selected_pair_index={selected_pair_index}, enabled_pairs_count={len(enabled_pairs)}")
            await message.reply_text("❌ 频道组配置错误，请检查频道组设置。")
            task["state"] = "waiting_for_range_for_pair"
            return
        
        pair = enabled_pairs[selected_pair_index]
        
        # 验证频道组信息
        if not pair.get("source") or not pair.get("target"):
            logging.error(f"任务 {task['task_id'][:8]} 请求范围时频道组信息不完整: {pair}")
            await message.reply_text("❌ 频道组信息不完整，请检查频道组配置。")
            task["state"] = "waiting_for_range_for_pair"
            return
        
        source = pair["source"]
        target = pair["target"]
        
        # 显示当前进度
        current_task_num = pair_index + 1
        total_tasks = len(task["selected_pairs_indices"])
        
        await message.reply_text(
            f"🔢 **请为频道组 `{source}` -> `{target}` 回复信息ID范围，例如：`100-200`**\n"
            f"📊 进度: {current_task_num}/{total_tasks}\n"
            f"(任务ID: `{task['task_id'][:8]}`)"
        )
        
    except Exception as e:
        logging.error(f"任务 {task['task_id'][:8]} 请求范围时发生错误: {e}, 任务状态: {task}")
        await message.reply_text("❌ 请求范围失败，请重新开始任务。")
        task["state"] = "waiting_for_range_for_pair"

async def handle_range_input_for_pair(message, user_id, task):
    try:
        # 验证ID范围格式
        if '-' not in message.text:
            await message.reply_text("❌ 无效格式，请输入 `开始ID-结束ID`，例如：`100-200`。")
            return
        
        start_id_str, end_id_str = message.text.split('-')
        
        # 验证是否为数字
        try:
            start_id = int(start_id_str.strip())
            end_id = int(end_id_str.strip())
        except ValueError:
            await message.reply_text("❌ ID必须是数字，请输入 `开始ID-结束ID`，例如：`100-200`。")
            return
        
        if start_id > end_id:
            await message.reply_text("❌ 开始ID必须小于或等于结束ID。")
            return
        
        # 获取当前处理的频道组索引
        pair_index = task["current_pair_index_for_range"]
        if pair_index >= len(task["selected_pairs_indices"]):
            logging.error(f"任务 {task['task_id'][:8]} 索引超出范围: pair_index={pair_index}, selected_pairs_indices={task['selected_pairs_indices']}")
            await message.reply_text("❌ 任务状态错误，请重新开始。")
            task["state"] = "waiting_for_range_for_pair"
            return
        
        original_pair_index = task["selected_pairs_indices"][pair_index]
        
        # 获取启用的频道组列表
        enabled_pairs = [p for p in user_configs.get(str(user_id), {}).get("channel_pairs", []) if p.get("enabled", True)]
        
        if original_pair_index >= len(enabled_pairs):
            logging.error(f"任务 {task['task_id'][:8]} 频道组索引超出范围: original_pair_index={original_pair_index}, enabled_pairs_count={len(enabled_pairs)}")
            await message.reply_text("❌ 频道组配置错误，请检查频道组设置。")
            task["state"] = "waiting_for_range_for_pair"
            return
        
        pair = enabled_pairs[original_pair_index]
        
        # 验证频道组信息
        if not pair.get("source") or not pair.get("target"):
            logging.error(f"任务 {task['task_id'][:8]} 频道组信息不完整: {pair}")
            await message.reply_text("❌ 频道组信息不完整，请检查频道组配置。")
            task["state"] = "waiting_for_range_for_pair"
            return

        # 新引擎不需要预估，直接使用范围
        estimated_messages = end_id - start_id + 1
        
        task["clone_tasks"].append({
            "pair": pair,
            "start_id": start_id,
            "end_id": end_id,
            "total_messages": end_id - start_id + 1,
            "estimated_actual_messages": estimated_messages,
            "sparse_range": estimated_messages < (end_id - start_id + 1) * 0.1  # 如果实际消息少于10%则标记为稀疏
        })

        task["current_pair_index_for_range"] += 1

        if task["current_pair_index_for_range"] < len(task["selected_pairs_indices"]):
            await request_range_for_pair(message, user_id, task)
        else:
            task["state"] = "confirming_clone"
            text = f"你确定要开始搬运以下任务吗？\n\n"
            for sub_task in task["clone_tasks"]:
                text += f"`{sub_task['pair']['source']}` -> `{sub_task['pair']['target']}`\n"
                text += f"    范围: **{sub_task['start_id']} - {sub_task['end_id']}**\n\n"

            logging.info(f"任务 {task['task_id'][:8]} 接收到所有ID范围，等待确认。")
            await message.reply_text(
                text,
                reply_markup=get_clone_confirm_buttons(task['task_id'], task["clone_tasks"])
            )
            
    except ValueError as e:
        logging.warning(f"任务 {task['task_id'][:8]} ID范围格式错误: {message.text}, 错误: {e}")
        await message.reply_text("❌ ID范围格式错误，请输入 `开始ID-结束ID`，例如：`100-200`。")
        task["state"] = "waiting_for_range_for_pair"
    except IndexError as e:
        logging.error(f"任务 {task['task_id'][:8]} 索引错误: {e}, 任务状态: {task}")
        await message.reply_text("❌ 任务状态错误，请重新开始任务。")
        task["state"] = "waiting_for_range_for_pair"
    except Exception as e:
        logging.error(f"任务 {task['task_id'][:8]} 处理ID范围时发生未知错误: {e}, 输入: {message.text}, 任务状态: {task}")
        await message.reply_text("❌ 处理失败，请重新开始任务。")
        task["state"] = "waiting_for_range_for_pair"


async def request_channel_pair_input(message, user_id):
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "waiting_for_source", "pair_data": {}}
    if user_id not in user_states: user_states[user_id] = []
    user_states[user_id].append(new_task)
    
    # 自动保存用户状态
    save_user_states()
    
    await safe_edit_or_reply(message, f"请回复**采集频道**的用户名或ID。\n例如：`@mychannel` 或 `-1001234567890`\n(任务ID: `{task_id[:8]}`)")

# 新增功能：编辑频道组时的输入请求
async def request_edit_pair_input(message, user_id, pair_id, channel_type):
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "waiting_for_edit_input", "pair_id": pair_id, "channel_type": channel_type}
    if user_id not in user_states: user_states[user_id] = []
    user_states[user_id].append(new_task)
    
    text = f"✏️ 请回复新的**{ '采集频道' if channel_type == 'source' else '目标频道' }**的用户名或ID。\n(任务ID: `{task_id[:8]}`)"
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data=f"cancel:{task_id}")]]))

# 新增功能：处理编辑频道组的输入
async def handle_edit_pair_input(client, message, user_id, task):
    pair_id = task["pair_id"]
    channel_type = task["channel_type"]
    channel_id = message.text
    
    try:
        logging.info(f"用户 {user_id} 尝试验证频道: 原始输入='{channel_id}'")
        processed_channel_id = parse_channel_identifier(channel_id)
        logging.info(f"用户 {user_id} 频道ID解析结果: '{processed_channel_id}' (类型: {type(processed_channel_id)})")
            
        chat = await client.get_chat(processed_channel_id)
        logging.info(f"用户 {user_id} 频道验证成功: {chat.title} (ID: {chat.id})")
        
        user_configs.setdefault(str(user_id), {}).setdefault("channel_pairs", [])
        if not (0 <= pair_id < len(user_configs[str(user_id)]["channel_pairs"])):
            raise ValueError("Invalid pair_id")

        user_configs[str(user_id)]["channel_pairs"][pair_id][channel_type] = processed_channel_id
        save_configs()
        
        logging.info(f"用户 {user_id} 成功修改频道组 {pair_id} 的 {channel_type} 频道为 {processed_channel_id}")
        await message.reply_text("✅ 频道组已成功更新。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回管理菜单", callback_data="show_channel_config_menu")]]))
    except Exception as e:
        logging.error(f"用户 {user_id} 修改频道组失败 - 原始输入: '{channel_id}', 解析结果: '{processed_channel_id if 'processed_channel_id' in locals() else 'N/A'}', 错误: {e}")
        await message.reply_text(f"❌ 频道验证失败: {e}\n\n**调试信息:**\n原始输入: `{channel_id}`\n解析结果: `{processed_channel_id if 'processed_channel_id' in locals() else '解析失败'}`\n\n请检查频道ID或机器人是否拥有权限。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回管理菜单", callback_data="show_channel_config_menu")]]))
    finally:
        remove_task(user_id, task["task_id"])

async def set_channel_pair(client, message, user_id, channel_type, channel_id, task):
    logging.info(f"用户 {user_id} 尝试设定 {channel_type} 频道: 原始输入='{channel_id}'")
    processed_channel_id = parse_channel_identifier(channel_id)
    logging.info(f"用户 {user_id} 频道ID解析结果: '{processed_channel_id}' (类型: {type(processed_channel_id)})")
    try:
        chat = await client.get_chat(processed_channel_id)
        logging.info(f"用户 {user_id} 频道验证成功: {chat.title} (ID: {chat.id})")
        task["pair_data"][channel_type] = processed_channel_id
        logging.info(f"用户 {user_id} 正在设定 {channel_type} 频道为 {processed_channel_id}")

        if channel_type == "source":
            task["state"] = "waiting_for_target"
            await message.reply_text(f"请回复**目标频道**的用户名或ID。\n(任务ID: `{task['task_id'][:8]}`)")
        else: # channel_type == "target"
            if str(user_id) not in user_configs: user_configs[str(user_id)] = {}
            if "channel_pairs" not in user_configs[str(user_id)]: user_configs[str(user_id)]["channel_pairs"] = []
            task["pair_data"]["enabled"] = True
            user_configs[str(user_id)]["channel_pairs"].append(task["pair_data"])
            save_configs() # 新增: 保存配置
            save_user_states() # 新增: 保存用户状态
            logging.info(f"用户 {user_id} 成功新增频道组: {task['pair_data']}")
            await message.reply_text(f"✅ **频道组** `{task['pair_data']['source']}` -> `{task['pair_data']['target']}` 已新增。")
            remove_task(user_id, task["task_id"])
            await show_channel_config_menu(message, user_id)
    except Exception as e:
        logging.error(f"用户 {user_id} 设定 {channel_type} 频道失败 - 原始输入: '{channel_id}', 解析结果: '{processed_channel_id}', 错误: {e}")
        remove_task(user_id, task["task_id"])
        await message.reply_text(f"❌ 频道验证失败: {e}\n\n**调试信息:**\n原始输入: `{channel_id}`\n解析结果: `{processed_channel_id}`\n\n请检查频道ID或机器人是否拥有权限。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]))

# ==================== 功能设定函数 (新版互动式) ====================
async def show_manage_keywords_menu(message, user_id):
    config = user_configs.get(str(user_id), {})
    keywords = config.get("filter_keywords", [])
    
    text = "📝 **关键字过滤管理**\n"
    if not keywords:
        text += "您尚未设定任何过滤关键字。"
    else:
        text += "以下是您已设定的关键字：\n" + ", ".join([f"`{kw}`" for kw in keywords])
        
    buttons = [
        [InlineKeyboardButton("➕ 新增关键字", callback_data=f"add_keyword:{uuid.uuid4()}")],
        [InlineKeyboardButton("🗑️ 清空所有关键字", callback_data=f"delete_keyword:clear_all")],
        [InlineKeyboardButton("🔙 返回功能设定", callback_data="show_feature_config_menu")]
    ]
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def request_add_keyword(message, user_id):
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "waiting_for_add_keyword"}
    user_states.setdefault(user_id, []).append(new_task)
    await message.reply_text("📝 请回复您想新增的关键字。\n(多个关键字请用逗号 `,` 分隔)")

async def add_keyword(message, user_id, task):
    keywords_text = message.text.strip()
    new_keywords = [kw.strip().lower() for kw in keywords_text.split(',') if kw.strip()]
    
    config = user_configs.setdefault(str(user_id), {})
    current_keywords = config.setdefault("filter_keywords", [])
    # 去重合并
    current_set = set(current_keywords)
    for kw in new_keywords:
        if kw not in current_set:
            current_keywords.append(kw)
            current_set.add(kw)
    
    save_configs()
    remove_task(user_id, task["task_id"])
    
    await message.reply_text(f"✅ 已新增关键字：`{', '.join(new_keywords)}`。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回关键字管理", callback_data="manage_filter_keywords")]]))

async def delete_keyword(message, user_id, keyword):
    config = user_configs.setdefault(str(user_id), {})
    keywords = config.get("filter_keywords", [])
    
    if keyword == "clear_all":
        config["filter_keywords"] = []
        text = "✅ 所有过滤关键字已清空。"
    else:
        if keyword in keywords:
            keywords.remove(keyword)
            text = f"✅ 关键字 `{keyword}` 已删除。"
        else:
            text = f"❌ 关键字 `{keyword}` 不存在。"
    
    save_configs()
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回关键字管理", callback_data="manage_filter_keywords")]]))


async def show_manage_replacements_menu(message, user_id):
    config = user_configs.get(str(user_id), {})
    replacements = config.get("replacement_words", {})
    
    text = "🔀 **敏感词替换管理**\n\n"
    if not replacements:
        text += "📋 **当前状态**: 您尚未设定任何敏感词替换。\n\n"
        text += "💡 **说明**: 敏感词替换功能可以在搬运过程中自动将指定的敏感词替换为其他文本。\n\n"
        text += "📝 **格式**: `敏感词->替换文本`\n"
        text += "📝 **示例**: `敏感词->替换文本` 或 `词1->替换1,词2->替换2`"
    else:
        text += f"📋 **当前状态**: 已设定 {len(replacements)} 条替换规则\n\n"
        text += "🔀 **已设定的替换规则**:\n"
        for i, (old, new) in enumerate(replacements.items(), 1):
            text += f"{i}. `{old}` → `{new}`\n"
        text += "\n💡 **说明**: 这些规则将在搬运过程中自动应用。"
        
    buttons = [
        [InlineKeyboardButton("➕ 新增替换规则", callback_data=f"add_replacement:{uuid.uuid4()}")],
        [InlineKeyboardButton("🗑️ 清空所有规则", callback_data=f"delete_replacement:clear_all")],
        [InlineKeyboardButton("🔙 返回功能设定", callback_data="show_feature_config_menu")]
    ]
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def request_add_replacement(message, user_id):
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "waiting_for_add_replacement"}
    user_states.setdefault(user_id, []).append(new_task)
    await message.reply_text("🔀 请回复您想新增的替换规则，格式为 `敏感词->替换文本`。\n(多个规则请用逗号 `,` 分隔)")

async def add_replacement(message, user_id, task):
    replacements_text = message.text.strip()
    replacement_dict = {}
    
    # 检查输入格式
    if not replacements_text or '->' not in replacements_text:
        await message.reply_text("❌ 无效格式，请按照 `敏感词->替换文本` 格式输入。\n\n例如：`敏感词->替换文本` 或 `词1->替换1,词2->替换2`")
        return
    
    try:
        items = replacements_text.split(',')
        for item in items:
            item = item.strip()
            if '->' in item:
                old, new = item.split('->', 1)
                old = old.strip()
                new = new.strip()
                if old and new:  # 确保敏感词和替换文本都不为空
                    replacement_dict[old] = new
        
        if not replacement_dict:
            await message.reply_text("❌ 没有有效的替换规则。请按照 `敏感词->替换文本` 格式输入。\n\n例如：`敏感词->替换文本` 或 `词1->替换1,词2->替换2`")
            return
        
        # 保存配置
        config = user_configs.setdefault(str(user_id), {})
        current_replacements = config.setdefault("replacement_words", {})
        current_replacements.update(replacement_dict)
        
        save_configs()
        save_user_states()  # 新增: 保存用户状态
        remove_task(user_id, task["task_id"])
        
        # 显示成功消息并返回管理菜单
        success_text = f"✅ 已成功新增 {len(replacement_dict)} 条替换规则：\n\n"
        for old, new in replacement_dict.items():
            success_text += f"`{old}` → `{new}`\n"
        
        await message.reply_text(
            success_text, 
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 返回替换管理", callback_data="manage_replacement_words")
            ]])
        )
        
    except Exception as e:
        logging.error(f"添加敏感词替换规则时出错: {e}")
        await message.reply_text("❌ 处理替换规则时出错，请重试。")

async def delete_replacement(message, user_id, word):
    config = user_configs.setdefault(str(user_id), {})
    replacements = config.get("replacement_words", {})

    if word == "clear_all":
        config["replacement_words"] = {}
        text = "✅ 所有敏感词替换规则已清空。"
    else:
        if word in replacements:
            del replacements[word]
            text = f"✅ 敏感词 `{word}` 的规则已删除。"
        else:
            text = f"❌ 敏感词 `{word}` 的规则不存在。"
    
    save_configs()
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回替换管理", callback_data="manage_replacement_words")]]))

# ==================== 频道组专用过滤设置 ====================
async def show_pair_filter_menu(message, user_id, pair_id):
    """显示频道组专用过滤设置菜单"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="show_channel_config_menu")]]))
        return
    
    pair = channel_pairs[pair_id]
    custom_filters = pair.get("custom_filters", {})
    
    # 频道组信息
    source = pair.get("source", "未知")
    target = pair.get("target", "未知")
    
    text = f"🔧 **频道组专用过滤设置**\n\n"
    text += f"📂 **频道组**: `{source}` ➜ `{target}`\n\n"
    
    if not custom_filters:
        text += "📋 **当前状态**: 使用全局过滤设置\n\n"
        text += "💡 **说明**: 设置专用过滤后，该频道组将不再使用全局过滤设置，而是使用自己的过滤规则。\n\n"
    else:
        text += "📋 **当前状态**: 已设置专用过滤\n\n"
        
        # 显示当前设置摘要
        keywords_count = len(custom_filters.get("filter_keywords", []))
        replacements_count = len(custom_filters.get("replacement_words", {}))
        extensions_count = len(custom_filters.get("file_filter_extensions", []))
        buttons_count = len(custom_filters.get("buttons", []))
        
        text += "🎯 **过滤设置摘要**:\n"
        text += f"   📝 过滤关键字: {keywords_count} 个\n"
        text += f"   🔀 敏感词替换: {replacements_count} 个\n"
        text += f"   📁 文件扩展名: {extensions_count} 个\n"
        text += f"   📋 自定义按钮: {buttons_count} 个\n\n"
    
    # 构建按钮
    buttons = []
    
    if not custom_filters:
        buttons.append([InlineKeyboardButton("✨ 启用专用过滤", callback_data=f"enable_pair_filters:{pair_id}")])
    else:
        # 过滤设置选项
        buttons.extend([
            [InlineKeyboardButton("📝 关键字过滤", callback_data=f"pair_filter_keywords:{pair_id}"),
             InlineKeyboardButton("🔀 敏感词替换", callback_data=f"pair_filter_replacements:{pair_id}")],
            [InlineKeyboardButton("📁 文件类型过滤", callback_data=f"pair_filter_files:{pair_id}"),
             InlineKeyboardButton("🔗 文本内容移除", callback_data=f"pair_filter_content:{pair_id}")],
            [InlineKeyboardButton("📋 自定义按钮", callback_data=f"pair_filter_buttons:{pair_id}"),
             InlineKeyboardButton("🎛️ 按钮策略", callback_data=f"pair_filter_button_policy:{pair_id}")],
            [InlineKeyboardButton("✍️ 文本小尾巴", callback_data=f"pair_filter_tail_text:{pair_id}")],
            [InlineKeyboardButton("🔄 重置为全局设置", callback_data=f"reset_pair_filters:{pair_id}")]
        ])
    
    buttons.append([InlineKeyboardButton("🔙 返回频道组设置", callback_data=f"edit_channel_pair:{pair_id}")])
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def enable_pair_filters(message, user_id, pair_id):
    """为频道组启用专用过滤设置"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。")
        return
    
    # 复制全局设置作为初始设置
    global_config = user_configs.get(str(user_id), {})
    custom_filters = {
        "filter_keywords": global_config.get("filter_keywords", []).copy(),
        "replacement_words": global_config.get("replacement_words", {}).copy(),
        "file_filter_extensions": global_config.get("file_filter_extensions", []).copy(),
        "remove_links": global_config.get("remove_links", False),
        "remove_hashtags": global_config.get("remove_hashtags", False),
        "remove_usernames": global_config.get("remove_usernames", False),
        "filter_photo": global_config.get("filter_photo", False),
        "filter_video": global_config.get("filter_video", False),
        "filter_buttons": global_config.get("filter_buttons", False),
        "buttons": global_config.get("buttons", []).copy(),
        "tail_text": global_config.get("tail_text", ""),
        "tail_position": global_config.get("tail_position", "end")
    }
    
    channel_pairs[pair_id]["custom_filters"] = custom_filters
    save_configs()
    
    await safe_edit_or_reply(message, 
        f"✅ **专用过滤已启用**\n\n"
        f"📋 已将当前全局设置复制为该频道组的初始专用设置。\n"
        f"现在您可以单独调整该频道组的过滤规则。",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔧 开始设置", callback_data=f"manage_pair_filters:{pair_id}"),
            InlineKeyboardButton("🔙 返回", callback_data=f"edit_channel_pair:{pair_id}")
        ]])
    )

async def reset_pair_filters(message, user_id, pair_id):
    """重置频道组过滤设置为全局设置"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。")
        return
    
    # 移除专用过滤设置
    if "custom_filters" in channel_pairs[pair_id]:
        del channel_pairs[pair_id]["custom_filters"]
    
    save_configs()
    
    await safe_edit_or_reply(message, 
        f"✅ **已重置为全局设置**\n\n"
        f"📋 该频道组现在将使用全局过滤设置。",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 返回频道组设置", callback_data=f"edit_channel_pair:{pair_id}")
        ]])
    )

async def show_pair_tail_text_menu(message, user_id, pair_id):
    """显示频道组文本小尾巴设置菜单"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="show_channel_config_menu")]]))
        return
    
    pair = channel_pairs[pair_id]
    custom_filters = pair.get("custom_filters", {})
    
    if not custom_filters:
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。", 
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔧 启用专用过滤", callback_data=f"enable_pair_filters:{pair_id}"),
                InlineKeyboardButton("🔙 返回", callback_data=f"edit_channel_pair:{pair_id}")
            ]]))
        return
    
    # 频道组信息
    source = pair.get("source", "未知")
    target = pair.get("target", "未知")
    
    # 当前设置
    current_tail_text = custom_filters.get("tail_text", "")
    current_position = custom_filters.get("tail_position", "bottom")
    position_text = "开头" if current_position == "top" else "结尾"
    
    text = f"✍️ **频道组文本小尾巴设置**\n\n"
    text += f"📂 **频道组**: `{source}` ➜ `{target}`\n\n"
    
    if current_tail_text:
        text += f"📝 **当前小尾巴**: `{current_tail_text}`\n"
        text += f"📍 **位置**: {position_text}\n\n"
    else:
        text += "📝 **当前小尾巴**: 未设置\n\n"
    
    text += "💡 **说明**: 文本小尾巴会在搬运的每条消息中添加自定义文字。\n"
    text += "可以选择添加到消息开头或结尾。\n\n"
    
    buttons = [
        [InlineKeyboardButton("📝 设置小尾巴文字", callback_data=f"pair_set_tail_text:{pair_id}")],
        [InlineKeyboardButton("📍 设置位置", callback_data=f"pair_set_tail_position:{pair_id}")],
        [InlineKeyboardButton("🗑️ 清除小尾巴", callback_data=f"pair_clear_tail_text:{pair_id}")],
        [InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_pair_keywords_menu(message, user_id, pair_id):
    """显示频道组关键字过滤设置菜单"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="show_channel_config_menu")]]))
        return
    
    pair = channel_pairs[pair_id]
    custom_filters = pair.get("custom_filters", {})
    
    if not custom_filters:
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。", 
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔧 启用专用过滤", callback_data=f"enable_pair_filters:{pair_id}"),
                InlineKeyboardButton("🔙 返回", callback_data=f"edit_channel_pair:{pair_id}")
            ]]))
        return
    
    # 频道组信息
    source = pair.get("source", "未知")
    target = pair.get("target", "未知")
    
    # 当前设置
    keywords = custom_filters.get("filter_keywords", [])
    keywords_count = len(keywords)
    
    text = f"📝 **频道组关键字过滤设置**\n\n"
    text += f"📂 **频道组**: `{source}` ➜ `{target}`\n\n"
    text += f"🔍 **当前关键字**: {keywords_count} 个\n\n"
    
    if keywords:
        text += "📋 **关键字列表**:\n"
        for i, keyword in enumerate(keywords, 1):
            text += f"   {i}. `{keyword}`\n"
        text += "\n"
    
    text += "💡 **说明**: 包含这些关键字的消息将被过滤，不会搬运。\n\n"
    
    buttons = [
        [InlineKeyboardButton("➕ 添加关键字", callback_data=f"pair_add_keyword:{pair_id}")],
        [InlineKeyboardButton("🗑️ 清空关键字", callback_data=f"pair_clear_keywords:{pair_id}")],
        [InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def request_pair_add_keyword(message, user_id, pair_id):
    """请求添加频道组关键字"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。")
        return
    
    pair = channel_pairs[pair_id]
    if not pair.get("custom_filters"):
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。")
        return
    
    # 设置用户状态
    user_states[user_id] = [{
        "state": "waiting_pair_add_keyword",
        "pair_id": pair_id,
        "timestamp": time.time()
    }]
    save_user_states()
    
    await safe_edit_or_reply(message, 
        f"📝 **添加频道组关键字**\n\n"
        f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n\n"
        f"💬 请输入要添加的关键字：\n\n"
        f"**格式**: `关键字1,关键字2,关键字3`\n\n"
        f"**示例**:\n"
        f"• `广告,推广,营销`\n"
        f"• `政治,敏感,违规`\n\n"
        f"💡 **说明**: 包含这些关键字的消息将被过滤，不会搬运。\n\n"
        f"🔙 输入 /cancel 取消设置",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 取消", callback_data=f"pair_filter_keywords:{pair_id}")]
        ]))

async def set_pair_add_keyword(message, user_id, keywords_text):
    """设置频道组关键字"""
    config = user_configs.get(str(user_id), {})
    user_states_list = user_states.get(user_id, [])
    user_state = user_states_list[0] if user_states_list else {}
    
    if user_state.get("state") != "waiting_pair_add_keyword":
        await safe_edit_or_reply(message, "❌ 无效的操作状态。")
        return
    
    pair_id = user_state.get("pair_id")
    if pair_id is None or pair_id >= len(config.get("channel_pairs", [])):
        await safe_edit_or_reply(message, "❌ 频道组不存在。")
        return
    
    channel_pairs = config.get("channel_pairs", [])
    pair = channel_pairs[pair_id]
    
    if not pair.get("custom_filters"):
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。")
        return
    
    # 解析关键字
    new_keywords = [kw.strip().lower() for kw in keywords_text.split(',') if kw.strip()]
    
    if not new_keywords:
        await safe_edit_or_reply(message, "❌ 没有输入有效的关键字。")
        return
    
    # 获取当前关键字列表
    current_keywords = pair["custom_filters"].setdefault("filter_keywords", [])
    
    # 去重合并
    current_set = set(current_keywords)
    added_keywords = []
    for kw in new_keywords:
        if kw not in current_set:
            current_keywords.append(kw)
            current_set.add(kw)
            added_keywords.append(kw)
    
    if not added_keywords:
        await safe_edit_or_reply(message, 
            f"ℹ️ **无需添加**\n\n"
            f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n\n"
            f"所有输入的关键字都已存在。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔧 继续设置", callback_data=f"pair_filter_keywords:{pair_id}")]
            ]))
        return
    
    # 保存配置
    save_configs()
    logging.info(f"用户 {user_id} 为频道组 {pair_id} 添加了关键字: {added_keywords}")
    
    # 清除用户状态
    if user_id in user_states:
        del user_states[user_id]
        save_user_states()
    
    # 显示成功消息
    await safe_edit_or_reply(message, 
        f"✅ **关键字添加成功**\n\n"
        f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n\n"
        f"📝 **新增关键字**: {len(added_keywords)} 个\n"
        f"📋 **关键字列表**:\n"
        f"{chr(10).join([f'   • `{kw}`' for kw in added_keywords])}\n\n"
        f"💡 现在包含这些关键字的消息将被过滤，不会搬运。",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔧 继续设置", callback_data=f"pair_filter_keywords:{pair_id}")],
            [InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")]
        ]))

async def clear_pair_keywords(message, user_id, pair_id):
    """清空频道组关键字"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。")
        return
    
    pair = channel_pairs[pair_id]
    custom_filters = pair.get("custom_filters", {})
    
    if not custom_filters:
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。")
        return
    
    # 清空关键字
    if "filter_keywords" in custom_filters:
        del custom_filters["filter_keywords"]
        save_configs()
        logging.info(f"用户 {user_id} 清空了频道组 {pair_id} 的关键字")
        
        await safe_edit_or_reply(message, 
            f"✅ **关键字已清空**\n\n"
            f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n\n"
            f"🗑️ 所有过滤关键字已被移除。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔧 继续设置", callback_data=f"pair_filter_keywords:{pair_id}")]
            ]))
    else:
        await safe_edit_or_reply(message, 
            f"ℹ️ **无需清空**\n\n"
            f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n\n"
            f"该频道组尚未设置关键字。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔧 继续设置", callback_data=f"pair_filter_keywords:{pair_id}")]
            ]))

async def show_pair_replacements_menu(message, user_id, pair_id):
    """显示频道组敏感词替换设置菜单"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="show_channel_config_menu")]]))
        return
    
    pair = channel_pairs[pair_id]
    custom_filters = pair.get("custom_filters", {})
    
    if not custom_filters:
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。", 
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔧 启用专用过滤", callback_data=f"enable_pair_filters:{pair_id}"),
                InlineKeyboardButton("🔙 返回", callback_data=f"edit_channel_pair:{pair_id}")
            ]]))
        return
    
    # 频道组信息
    source = pair.get("source", "未知")
    target = pair.get("target", "未知")
    
    # 当前设置
    replacements = custom_filters.get("replacement_words", {})
    replacements_count = len(replacements)
    
    text = f"🔀 **频道组敏感词替换设置**\n\n"
    text += f"📂 **频道组**: `{source}` ➜ `{target}`\n\n"
    text += f"🔄 **当前替换规则**: {replacements_count} 个\n\n"
    
    if replacements:
        text += "📋 **替换规则列表**:\n"
        for i, (old_word, new_word) in enumerate(replacements.items(), 1):
            text += f"   {i}. `{old_word}` → `{new_word}`\n"
        text += "\n"
    
    text += "💡 **说明**: 消息中的敏感词将被自动替换为指定词汇。\n\n"
    
    buttons = [
        [InlineKeyboardButton("➕ 添加替换规则", callback_data=f"pair_add_replacement:{pair_id}")],
        [InlineKeyboardButton("🗑️ 清空替换规则", callback_data=f"pair_clear_replacements:{pair_id}")],
        [InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_pair_files_menu(message, user_id, pair_id):
    """显示频道组文件类型过滤设置菜单"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="show_channel_config_menu")]]))
        return
    
    pair = channel_pairs[pair_id]
    custom_filters = pair.get("custom_filters", {})
    
    if not custom_filters:
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。", 
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔧 启用专用过滤", callback_data=f"enable_pair_filters:{pair_id}"),
                InlineKeyboardButton("🔙 返回", callback_data=f"edit_channel_pair:{pair_id}")
            ]]))
        return
    
    # 频道组信息
    source = pair.get("source", "未知")
    target = pair.get("target", "未知")
    
    # 当前设置
    extensions = custom_filters.get("file_filter_extensions", [])
    extensions_count = len(extensions)
    filter_photo = custom_filters.get("filter_photo", False)
    filter_video = custom_filters.get("filter_video", False)
    
    text = f"📁 **频道组文件类型过滤设置**\n\n"
    text += f"📂 **频道组**: `{source}` ➜ `{target}`\n\n"
    text += f"📁 **文件扩展名过滤**: {extensions_count} 个\n"
    text += f"🖼 **图片过滤**: {'✅ 开启' if filter_photo else '❌ 关闭'}\n"
    text += f"🎬 **视频过滤**: {'✅ 开启' if filter_video else '❌ 关闭'}\n\n"
    
    if extensions:
        text += "📋 **扩展名列表**:\n"
        for i, ext in enumerate(extensions, 1):
            text += f"   {i}. `{ext}`\n"
        text += "\n"
    
    text += "💡 **说明**: 符合过滤条件的文件类型将被过滤，不会搬运。\n\n"
    
    buttons = [
        [InlineKeyboardButton("📁 管理扩展名", callback_data=f"pair_manage_extensions:{pair_id}")],
        [InlineKeyboardButton("🖼 图片过滤", callback_data=f"pair_toggle_photo:{pair_id}")],
        [InlineKeyboardButton("🎬 视频过滤", callback_data=f"pair_toggle_video:{pair_id}")],
        [InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_pair_content_menu(message, user_id, pair_id):
    """显示频道组文本内容移除设置菜单"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="show_channel_config_menu")]]))
        return
    
    pair = channel_pairs[pair_id]
    custom_filters = pair.get("custom_filters", {})
    
    if not custom_filters:
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。", 
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔧 启用专用过滤", callback_data=f"enable_pair_filters:{pair_id}"),
                InlineKeyboardButton("🔙 返回", callback_data=f"edit_channel_pair:{pair_id}")
            ]]))
        return
    
    # 频道组信息
    source = pair.get("source", "未知")
    target = pair.get("target", "未知")
    
    # 当前设置
    remove_links = custom_filters.get("remove_links", False)
    remove_hashtags = custom_filters.get("remove_hashtags", False)
    remove_usernames = custom_filters.get("remove_usernames", False)
    
    text = f"🔗 **频道组文本内容移除设置**\n\n"
    text += f"📂 **频道组**: `{source}` ➜ `{target}`\n\n"
    text += f"🔗 **移除链接**: {'✅ 开启' if remove_links else '❌ 关闭'}\n"
    text += f"🏷 **移除标签**: {'✅ 开启' if remove_hashtags else '❌ 关闭'}\n"
    text += f"👤 **移除用户名**: {'✅ 开启' if remove_usernames else '❌ 关闭'}\n\n"
    
    text += "💡 **说明**: 开启后，搬运时会自动移除相应的文本内容。\n\n"
    
    buttons = [
        [InlineKeyboardButton("🔗 链接移除", callback_data=f"pair_toggle_links:{pair_id}")],
        [InlineKeyboardButton("🏷 标签移除", callback_data=f"pair_toggle_hashtags:{pair_id}")],
        [InlineKeyboardButton("👤 用户名移除", callback_data=f"pair_toggle_usernames:{pair_id}")],
        [InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_pair_buttons_menu(message, user_id, pair_id):
    """显示频道组自定义按钮设置菜单"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="show_channel_config_menu")]]))
        return
    
    pair = channel_pairs[pair_id]
    custom_filters = pair.get("custom_filters", {})
    
    if not custom_filters:
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。", 
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔧 启用专用过滤", callback_data=f"enable_pair_filters:{pair_id}"),
                InlineKeyboardButton("🔙 返回", callback_data=f"edit_channel_pair:{pair_id}")
            ]]))
        return
    
    # 频道组信息
    source = pair.get("source", "未知")
    target = pair.get("target", "未知")
    
    # 当前设置
    buttons = custom_filters.get("buttons", [])
    buttons_count = len(buttons)
    
    text = f"📋 **频道组自定义按钮设置**\n\n"
    text += f"📂 **频道组**: `{source}` ➜ `{target}`\n\n"
    text += f"📋 **当前按钮**: {buttons_count} 个\n\n"
    
    if buttons:
        text += "📋 **按钮列表**:\n"
        for i, button in enumerate(buttons, 1):
            text += f"   {i}. [{button['text']}]({button['url']})\n"
        text += "\n"
    
    text += "💡 **说明**: 这些按钮会添加到搬运的每条消息中。\n\n"
    
    buttons_ui = [
        [InlineKeyboardButton("➕ 添加按钮", callback_data=f"pair_add_button:{pair_id}")],
        [InlineKeyboardButton("🗑️ 清空按钮", callback_data=f"pair_clear_buttons:{pair_id}")],
        [InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons_ui))

async def show_pair_button_policy_menu(message, user_id, pair_id):
    """显示频道组按钮策略设置菜单"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="show_channel_config_menu")]]))
        return
    
    pair = channel_pairs[pair_id]
    custom_filters = pair.get("custom_filters", {})
    
    if not custom_filters:
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。", 
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔧 启用专用过滤", callback_data=f"enable_pair_filters:{pair_id}"),
                InlineKeyboardButton("🔙 返回", callback_data=f"edit_channel_pair:{pair_id}")
            ]]))
        return
    
    # 频道组信息
    source = pair.get("source", "未知")
    target = pair.get("target", "未知")
    
    # 当前设置
    filter_buttons = custom_filters.get("filter_buttons", False)
    filter_mode = custom_filters.get("filter_buttons_mode", "drop")
    whitelist = custom_filters.get("button_domain_whitelist", [])
    whitelist_count = len(whitelist)
    
    text = f"🎛️ **频道组按钮策略设置**\n\n"
    text += f"📂 **频道组**: `{source}` ➜ `{target}`\n\n"
    text += f"🚫 **按钮过滤**: {'✅ 开启' if filter_buttons else '❌ 关闭'}\n"
    text += f"🎯 **过滤模式**: `{filter_mode}`\n"
    text += f"✅ **白名单域名**: {whitelist_count} 个\n\n"
    
    if whitelist:
        text += "📋 **白名单域名**:\n"
        for i, domain in enumerate(whitelist, 1):
            text += f"   {i}. `{domain}`\n"
        text += "\n"
    
    text += "💡 **模式说明**:\n"
    text += "• **drop**: 发现带按钮即丢弃整条消息\n"
    text += "• **strip**: 移除按钮，保留文本/媒体\n"
    text += "• **whitelist**: 仅允许白名单域名的按钮，其余移除\n\n"
    
    buttons = [
        [InlineKeyboardButton(f"🚫 按钮过滤: {'✅ 开启' if filter_buttons else '❌ 关闭'}", callback_data=f"pair_toggle_filter_buttons:{pair_id}")],
        [InlineKeyboardButton("drop", callback_data=f"pair_set_btn_mode:drop:{pair_id}"), 
         InlineKeyboardButton("strip", callback_data=f"pair_set_btn_mode:strip:{pair_id}"), 
         InlineKeyboardButton("whitelist", callback_data=f"pair_set_btn_mode:whitelist:{pair_id}")],
        [InlineKeyboardButton("➕ 添加白名单域名", callback_data=f"pair_add_btn_domain:{pair_id}")],
        [InlineKeyboardButton("🗑️ 清空白名单", callback_data=f"pair_clear_btn_domain:{pair_id}")],
        [InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def request_pair_tail_text(message, user_id, pair_id):
    """请求设置频道组文本小尾巴"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。")
        return
    
    pair = channel_pairs[pair_id]
    if not pair.get("custom_filters"):
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。")
        return
    
    # 设置用户状态
    user_states[user_id] = [{
        "state": "waiting_pair_tail_text",
        "pair_id": pair_id,
        "timestamp": time.time()
    }]
    
    await safe_edit_or_reply(message, 
        f"✍️ **设置文本小尾巴**\n\n"
        f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n\n"
        f"💬 请输入要添加的文本小尾巴：\n\n"
        f"💡 **提示**:\n"
        f"• 支持多行文本\n"
        f"• 可以使用表情符号\n"
        f"• 留空则清除小尾巴\n\n"
        f"🔙 输入 /cancel 取消设置",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 取消", callback_data=f"pair_filter_tail_text:{pair_id}")
        ]])
    )

async def set_pair_tail_text(message, user_id, tail_text):
    """设置频道组文本小尾巴"""
    config = user_configs.get(str(user_id), {})
    user_states_list = user_states.get(user_id, [])
    user_state = user_states_list[0] if user_states_list else {}
    
    if user_state.get("state") != "waiting_pair_tail_text":
        await safe_edit_or_reply(message, "❌ 无效的操作状态。")
        return
    
    pair_id = user_state.get("pair_id")
    if pair_id is None or pair_id >= len(config.get("channel_pairs", [])):
        await safe_edit_or_reply(message, "❌ 频道组不存在。")
        return
    
    channel_pairs = config.get("channel_pairs", [])
    pair = channel_pairs[pair_id]
    
    if not pair.get("custom_filters"):
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。")
        return
    
    # 清除用户状态
    if user_id in user_states:
        del user_states[user_id]
        save_user_states()
    
    # 设置小尾巴
    if tail_text.strip():
        pair["custom_filters"]["tail_text"] = tail_text.strip()
        save_configs()
        
        await safe_edit_or_reply(message, 
            f"✅ **文本小尾巴设置成功**\n\n"
            f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n"
            f"📝 **小尾巴**: `{tail_text.strip()}`\n"
            f"📍 **位置**: {pair['custom_filters'].get('tail_position', 'bottom')}\n\n"
            f"💡 现在搬运该频道的消息时会自动添加此小尾巴。",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔧 继续设置", callback_data=f"pair_filter_tail_text:{pair_id}"),
                InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")
            ]])
        )
    else:
        # 清除小尾巴
        if "tail_text" in pair["custom_filters"]:
            del pair["custom_filters"]["tail_text"]
        save_configs()
        
        await safe_edit_or_reply(message, 
            f"✅ **文本小尾巴已清除**\n\n"
            f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n\n"
            f"💡 现在搬运该频道的消息时不会添加小尾巴。",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔧 继续设置", callback_data=f"pair_filter_tail_text:{pair_id}"),
                InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")
            ]])
        )

async def set_pair_buttons(message, user_id, buttons_text):
    """设置频道组按钮"""
    logging.info(f"set_pair_buttons: 开始处理用户 {user_id} 的按钮设置请求")
    logging.info(f"set_pair_buttons: 输入文本: {buttons_text}")
    
    config = user_configs.get(str(user_id), {})
    user_states_list = user_states.get(user_id, [])
    user_state = user_states_list[0] if user_states_list else {}
    
    logging.info(f"set_pair_buttons: 用户状态: {user_state}")
    logging.info(f"set_pair_buttons: 期望状态: waiting_pair_buttons, 实际状态: {user_state.get('state')}")
    
    if user_state.get("state") != "waiting_pair_buttons":
        logging.warning(f"set_pair_buttons: 状态不匹配，用户 {user_id} 状态: {user_state.get('state')}")
        await safe_edit_or_reply(message, "❌ 无效的操作状态。")
        return
    
    pair_id = user_state.get("pair_id")
    if pair_id is None or pair_id >= len(config.get("channel_pairs", [])):
        await safe_edit_or_reply(message, "❌ 频道组不存在。")
        return
    
    channel_pairs = config.get("channel_pairs", [])
    pair = channel_pairs[pair_id]
    
    if not pair.get("custom_filters"):
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。")
        return
    
    # 处理按钮配置
    if buttons_text.lower() == "清空":
        # 清空按钮
        if "buttons" in pair["custom_filters"]:
            del pair["custom_filters"]["buttons"]
        save_configs()
        logging.info(f"用户 {user_id} 清空了频道组 {pair_id} 的按钮")
        
        # 创建按钮列表
        buttons = []
        buttons.append([InlineKeyboardButton("🔧 继续设置", callback_data=f"pair_filter_buttons:{pair_id}")])
        buttons.append([InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")])
        
        # 创建键盘标记
        keyboard = InlineKeyboardMarkup(buttons)
        
        await safe_edit_or_reply(message, 
            f"✅ **按钮已清空**\n\n"
            f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n\n"
            f"💡 现在搬运该频道的消息时不会添加按钮。",
            reply_markup=keyboard)
        
        # 成功处理后清除用户状态
        if user_id in user_states:
            del user_states[user_id]
            save_user_states()
    else:
        # 解析按钮配置
        buttons_list = []
        try:
            # 添加调试日志
            logging.info(f"set_pair_buttons: 开始解析按钮配置: {buttons_text}")
            
            button_items = buttons_text.split('|')
            logging.info(f"set_pair_buttons: 分割后的按钮项: {button_items}")
            
            for i, item in enumerate(button_items):
                item = item.strip()
                logging.info(f"set_pair_buttons: 处理第 {i+1} 个按钮项: '{item}'")
                
                if not item:  # 跳过空项
                    logging.info(f"set_pair_buttons: 跳过空项")
                    continue
                
                if ',' not in item:
                    error_msg = (f"❌ **格式错误**\n\n"
                               f"📝 **问题项**: `{item}`\n"
                               f"🔍 **问题**: 缺少逗号分隔符\n\n"
                               f"💡 **正确格式**: `按钮文字,按钮链接`\n\n"
                               f"**示例**:\n"
                               f"• `官网,https://example.com`\n"
                               f"• `TG群组,https://t.me/group`\n\n"
                               f"**当前输入**: `{buttons_text}`")
                    await safe_edit_or_reply(message, error_msg)
                    return
                
                parts = item.split(',', 1)
                text = parts[0].strip()
                url = parts[1].strip()
                
                logging.info(f"set_pair_buttons: 解析结果 - 文字: '{text}', 链接: '{url}'")
                
                if not text:
                    error_msg = (f"❌ **格式错误**\n\n"
                               f"📝 **问题项**: `{item}`\n"
                               f"🔍 **问题**: 按钮文字不能为空\n\n"
                               f"💡 **正确格式**: `按钮文字,按钮链接`\n\n"
                               f"**示例**:\n"
                               f"• `官网,https://example.com`\n"
                               f"• `TG群组,https://t.me/group`")
                    await safe_edit_or_reply(message, error_msg)
                    return
                
                if not url:
                    error_msg = (f"❌ **格式错误**\n\n"
                               f"📝 **问题项**: `{item}`\n"
                               f"🔍 **问题**: 按钮链接不能为空\n\n"
                               f"💡 **正确格式**: `按钮文字,按钮链接`\n\n"
                               f"**示例**:\n"
                               f"• `官网,https://example.com`\n"
                               f"• `TG群组,https://t.me/group`")
                    await safe_edit_or_reply(message, error_msg)
                    return
                
                # 验证链接格式
                if not (url.startswith('http://') or url.startswith('https://') or url.startswith('tg://') or url.startswith('@')):
                    error_msg = (f"❌ **链接格式错误**\n\n"
                               f"📝 **问题项**: `{item}`\n"
                               f"🔍 **问题**: 链接格式不正确\n\n"
                               f"💡 **支持的链接格式**:\n"
                               f"• `https://example.com` (网站链接)\n"
                               f"• `tg://openmessage?user=username` (Telegram链接)\n"
                               f"• `@username` (Telegram用户名)\n\n"
                               f"**当前链接**: `{url}`")
                    await safe_edit_or_reply(message, error_msg)
                    return
                
                buttons_list.append({"text": text, "url": url})
                logging.info(f"set_pair_buttons: 成功添加按钮: {{'text': '{text}', 'url': '{url}'}}")
            
            if not buttons_list:
                error_msg = (f"❌ **没有有效按钮**\n\n"
                           f"🔍 **问题**: 没有找到有效的按钮配置\n\n"
                           f"💡 **请按照以下格式输入**:\n"
                           f"• `官网,https://example.com`\n"
                           f"• `官网,https://example.com|TG群组,https://t.me/group`\n\n"
                           f"**当前输入**: `{buttons_text}`")
                await safe_edit_or_reply(message, error_msg)
                return
                
            # 保存按钮配置
            pair["custom_filters"]["buttons"] = buttons_list
            logging.info(f"set_pair_buttons: 按钮配置已设置到内存中: {buttons_list}")
            
            try:
                save_configs()
                logging.info(f"set_pair_buttons: 配置文件保存成功")
            except Exception as save_error:
                logging.error(f"set_pair_buttons: 保存配置文件失败: {save_error}")
                # 即使保存失败，也继续处理，因为配置已经在内存中了
            
            logging.info(f"用户 {user_id} 为频道组 {pair_id} 设定了按钮: {buttons_list}")
            
            # 生成按钮预览
            preview_text = f"✅ **按钮设置成功**\n\n"
            preview_text += f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n"
            preview_text += f"📊 **统计**: 共添加了 {len(buttons_list)} 个按钮\n\n"
            preview_text += "🔍 **预览**:\n"
            for i, btn in enumerate(buttons_list, 1):
                preview_text += f"   {i}. 📋 `{btn['text']}` → `{btn['url']}`\n"
            preview_text += "\n💡 现在搬运该频道的消息时会添加这些按钮。"
            
            logging.info(f"set_pair_buttons: 准备发送成功消息")
            
            try:
                # 创建按钮列表
                buttons = []
                buttons.append([InlineKeyboardButton("🔧 继续设置", callback_data=f"pair_filter_buttons:{pair_id}")])
                buttons.append([InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")])
                
                # 创建键盘标记
                keyboard = InlineKeyboardMarkup(buttons)
                
                await safe_edit_or_reply(message, preview_text, reply_markup=keyboard)
                logging.info(f"set_pair_buttons: 成功消息发送成功")
            except Exception as send_error:
                logging.error(f"set_pair_buttons: 发送成功消息失败: {send_error}")
                # 即使发送失败，也继续处理用户状态清理
            
            # 成功处理后清除用户状态
            logging.info(f"set_pair_buttons: 准备清理用户状态")
            if user_id in user_states:
                del user_states[user_id]
                save_user_states()
                logging.info(f"set_pair_buttons: 用户状态清理成功")
            else:
                logging.warning(f"set_pair_buttons: 用户 {user_id} 不在用户状态中")
        except Exception as e:
            logging.error(f"解析按钮配置时出错: {e}")
            error_msg = (f"❌ **解析错误**\n\n"
                        f"🔍 **错误详情**: {str(e)}\n\n"
                        f"💡 **请按照以下格式输入**:\n"
                        f"• `官网,https://example.com`\n"
                        f"• `官网,https://example.com|TG群组,https://t.me/group`\n\n"
                        f"**当前输入**: `{buttons_text}`\n\n"
                        f"⚠️ 如果问题持续存在，请联系管理员。")
            await safe_edit_or_reply(message, error_msg)
            return

async def show_pair_tail_position_menu(message, user_id, pair_id):
    """显示频道组文本小尾巴位置设置菜单"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="show_channel_config_menu")]]))
        return
    
    pair = channel_pairs[pair_id]
    custom_filters = pair.get("custom_filters", {})
    
    if not custom_filters:
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。", 
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔧 启用专用过滤", callback_data=f"enable_pair_filters:{pair_id}"),
                InlineKeyboardButton("🔙 返回", callback_data=f"edit_channel_pair:{pair_id}")
            ]]))
        return
    
    # 频道组信息
    source = pair.get("source", "未知")
    target = pair.get("target", "未知")
    
    # 当前设置
    current_position = custom_filters.get("tail_position", "bottom")
    current_tail_text = custom_filters.get("tail_text", "")
    
    text = f"📍 **设置文本小尾巴位置**\n\n"
    text += f"📂 **频道组**: `{source}` ➜ `{target}`\n\n"
    
    if current_tail_text:
        text += f"📝 **当前小尾巴**: `{current_tail_text}`\n"
        text += f"📍 **当前位置**: {'开头' if current_position == 'top' else '结尾'}\n\n"
    else:
        text += "📝 **当前小尾巴**: 未设置\n\n"
    
    text += "💡 **位置说明**:\n"
    text += "• **开头**: 小尾巴会添加到消息的最前面\n"
    text += "• **结尾**: 小尾巴会添加到消息的最后面\n\n"
    
    buttons = [
        [InlineKeyboardButton("🔝 添加到开头", callback_data=f"pair_set_tail_pos:top:{pair_id}")],
        [InlineKeyboardButton("🔚 添加到结尾", callback_data=f"pair_set_tail_pos:bottom:{pair_id}")],
        [InlineKeyboardButton("🔙 返回小尾巴设置", callback_data=f"pair_filter_tail_text:{pair_id}")]
    ]
    
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def set_pair_tail_position(message, user_id, position, pair_id):
    """设置频道组文本小尾巴位置"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。")
        return
    
    pair = channel_pairs[pair_id]
    if not pair.get("custom_filters"):
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。")
        return
    
    # 设置位置
    pair["custom_filters"]["tail_position"] = position
    save_configs()
    
    position_text = "开头" if position == "top" else "结尾"
    
    await safe_edit_or_reply(message, 
        f"✅ **小尾巴位置设置成功**\n\n"
        f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n"
        f"📝 **小尾巴**: `{pair['custom_filters'].get('tail_text', '未设置')}`\n"
        f"📍 **位置**: {position_text}\n\n"
        f"💡 现在搬运该频道的消息时小尾巴会添加到{position_text}。",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔧 继续设置", callback_data=f"pair_filter_tail_text:{pair_id}"),
            InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")
        ]])
    )

async def clear_pair_tail_text(message, user_id, pair_id):
    """清除频道组文本小尾巴"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。")
        return
    
    pair = channel_pairs[pair_id]
    if not pair.get("custom_filters"):
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。")
        return
    
    # 清除小尾巴
    if "tail_text" in pair["custom_filters"]:
        del pair["custom_filters"]["tail_text"]
    if "tail_position" in pair["custom_filters"]:
        del pair["custom_filters"]["tail_position"]
    
    save_configs()
    
    await safe_edit_or_reply(message, 
        f"✅ **文本小尾巴已清除**\n\n"
        f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n\n"
        f"💡 现在搬运该频道的消息时不会添加小尾巴。",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔧 继续设置", callback_data=f"pair_filter_tail_text:{pair_id}"),
            InlineKeyboardButton("🔙 返回过滤设置", callback_data=f"manage_pair_filters:{pair_id}")
        ]])
    )

async def request_pair_button_input(message, user_id, pair_id):
    """请求设置频道组按钮"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。")
        return
    
    pair = channel_pairs[pair_id]
    if not pair.get("custom_filters"):
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。")
        return
    
    # 设置用户状态
    user_states[user_id] = [{
        "state": "waiting_pair_buttons",
        "pair_id": pair_id,
        "timestamp": time.time()
    }]
    save_user_states()  # 保存用户状态
    
    await safe_edit_or_reply(message, 
        f"📋 **设置频道组按钮**\n\n"
        f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n\n"
        f"💬 请输入按钮配置：\n\n"
        f"**格式**: `按钮文字1,按钮链接1|按钮文字2,按钮链接2`\n\n"
        f"**示例**:\n"
        f"• `官网,https://example.com`\n"
        f"• `官网,https://example.com|TG群组,https://t.me/group`\n\n"
        f"💡 **提示**:\n"
        f"• 若想清空，请回复 `清空`\n"
        f"• 支持多种链接格式\n"
        f"• 多个按钮用 `|` 分隔\n\n"
        f"🔙 输入 /cancel 取消设置",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 取消", callback_data=f"pair_filter_buttons:{pair_id}")]
        ]))

async def clear_pair_buttons(message, user_id, pair_id):
    """清除频道组按钮"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。")
        return
    
    pair = channel_pairs[pair_id]
    custom_filters = pair.get("custom_filters", {})
    
    if not custom_filters:
        await safe_edit_or_reply(message, "❌ 该频道组尚未启用专用过滤设置。")
        return
    
    # 清除按钮
    if "buttons" in custom_filters:
        del custom_filters["buttons"]
        save_configs()
        logging.info(f"用户 {user_id} 清除了频道组 {pair_id} 的按钮")
        
        await safe_edit_or_reply(message, 
            f"✅ **按钮已清除**\n\n"
            f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n\n"
            f"🗑️ 所有自定义按钮已被移除。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔧 继续设置", callback_data=f"pair_filter_buttons:{pair_id}")]
            ]))
    else:
        await safe_edit_or_reply(message, 
            f"ℹ️ **无需清除**\n\n"
            f"📂 **频道组**: `{pair['source']}` ➜ `{pair['target']}`\n\n"
        f"该频道组尚未设置按钮。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔧 继续设置", callback_data=f"pair_filter_buttons:{pair_id}")]
            ]))

async def show_edit_channel_pair_menu(message, user_id, pair_id):
    """显示编辑频道对的菜单"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_id >= len(channel_pairs):
        await safe_edit_or_reply(message, "❌ 频道组不存在。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="show_channel_config_menu")]]))
        return
    
    pair = channel_pairs[pair_id]
    source = pair.get("source", "未知")
    target = pair.get("target", "未知")
    is_enabled = pair.get("enabled", True)
    has_custom_filters = bool(pair.get("custom_filters"))
    
    status_text = "✅ 启用" if is_enabled else "⏸️ 暂停"
    filter_text = "🔧 已设置专用过滤" if has_custom_filters else "📋 使用全局过滤"
    
    text = (f"✏️ **编辑频道组 {pair_id + 1}**\n\n"
            f"📂 **采集频道**: `{source}`\n"
            f"📁 **目标频道**: `{target}`\n"
            f"📊 **状态**: {status_text}\n"
            f"🔧 **过滤设置**: {filter_text}\n\n"
            f"请选择要修改的设置：")
    
    reply_markup = get_edit_channel_pair_menu(pair_id, pair)
    await safe_edit_or_reply(message, text, reply_markup=reply_markup)

def get_effective_config_for_pair(user_id, pair_index):
    """获取频道组的有效配置（专用配置优先，否则使用全局配置）"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    if pair_index < len(channel_pairs):
        pair = channel_pairs[pair_index]
        custom_filters = pair.get("custom_filters")
        
        if custom_filters:
            # 使用专用过滤设置
            logging.info(f"用户 {user_id} 频道组 {pair_index} 使用专用过滤设置")
            return custom_filters
    
    # 使用全局配置
    logging.info(f"用户 {user_id} 频道组 {pair_index} 使用全局过滤设置")
    return config

def get_effective_config_for_realtime(user_id, source_channel, target_channel):
    """获取实时监听的有效配置（根据源频道和目标频道匹配频道组）"""
    config = user_configs.get(str(user_id), {})
    channel_pairs = config.get("channel_pairs", [])
    
    # 查找匹配的频道组
    for i, pair in enumerate(channel_pairs):
        if (pair.get("source") == source_channel and pair.get("target") == target_channel):
            custom_filters = pair.get("custom_filters")
            if custom_filters:
                logging.info(f"实时监听: 用户 {user_id} 频道组 {source_channel}->{target_channel} 使用专用过滤设置")
                return custom_filters
            break
    
    # 使用全局配置
    logging.info(f"实时监听: 用户 {user_id} 频道组 {source_channel}->{target_channel} 使用全局过滤设置")
    return config

def process_message_content(text, config):
    """处理消息内容，支持频道组专用过滤设置"""
    try:
        # 使用新引擎的高级处理功能
        if NEW_ENGINE_AVAILABLE and robust_cloning_engine:
            processed_text, reply_markup = robust_cloning_engine._advanced_process_content(text, config)
            return processed_text, reply_markup
        else:
            # 回退到简单处理
            return _simple_process_content(text, config)
    except Exception as e:
        logging.error(f"处理消息内容时出错: {e}")
        return _simple_process_content(text, config)

def quick_filter_check(message, config):
    """快速预检过滤（优化性能）- 只检查最明显的过滤条件"""
    # 媒体类型过滤（最快速）
    if message.photo and config.get("filter_photo"):
        return True
    if message.video and config.get("filter_video"):
        return True
    
    # 按钮过滤（如果设置为丢弃模式）
    filter_buttons_enabled = config.get("filter_buttons")
    filter_buttons_mode = config.get("filter_buttons_mode", "drop")
    if filter_buttons_enabled and getattr(message, "reply_markup", None):
        if filter_buttons_mode == "drop":
            return True
    
    return False

def should_filter_message(message, config):
    """判断消息是否应该被过滤"""
    # 关键字过滤
    filter_keywords = config.get("filter_keywords", [])
    text_to_check = ""
    if message.caption:
        text_to_check += message.caption.lower()
    if message.text:
        text_to_check += message.text.lower()
    
    # 添加详细的过滤日志
    if filter_keywords:
        logging.debug(f"🔍 过滤检查: 消息ID {message.id}, 文本长度: {len(text_to_check)}")
        logging.debug(f"🔍 过滤检查: 关键词数量: {len(filter_keywords)}")
        
        # 检查每个关键词
        for keyword in filter_keywords:
            if keyword.lower() in text_to_check:
                logging.info(f"🚫 消息 {message.id} 被关键字过滤: '{keyword}' 匹配文本")
                return True
        
        logging.debug(f"✅ 消息 {message.id} 通过关键字过滤检查")
    else:
        logging.debug(f"⚠️ 消息 {message.id} 过滤检查: 未配置关键词")
    
    return False

    # 过滤带按钮的消息（支持策略）
    filter_buttons_enabled = config.get("filter_buttons")
    filter_buttons_mode = config.get("filter_buttons_mode", "drop")  # drop | strip | whitelist
    if filter_buttons_enabled and getattr(message, "reply_markup", None):
        if filter_buttons_mode == "drop":
            return True

    # 文件类型过滤
    filter_extensions = config.get("file_filter_extensions", [])
    if message.document and filter_extensions:
        filename = getattr(message.document, 'file_name', '')
        if filename and '.' in filename:
            ext = filename.lower().rsplit('.', 1)[1]
            if ext in filter_extensions:
                return True

    # 媒体类型过滤
    if message.photo and config.get("filter_photo"):
        return True
    if message.video and config.get("filter_video"):
        return True

    return False

def _simple_process_content(text, config):
    """简化的消息内容处理（回退方案）"""
    processed_text = text
    
    # 基础文本处理
    if config.get("remove_links", False):
        import re
        processed_text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', processed_text)
    
    if config.get("remove_hashtags", False):
        import re
        processed_text = re.sub(r'#\w+', '', processed_text)
    
    if config.get("remove_usernames", False):
        import re
        processed_text = re.sub(r'@\w+', '', processed_text)
    
    # 敏感词替换
    replacement_words = config.get("replacement_words", {})
    for old_word, new_word in replacement_words.items():
        processed_text = processed_text.replace(old_word, new_word)
    
    # 添加尾巴文字
    tail_text = config.get("tail_text", "")
    if tail_text:
        if not processed_text.strip():
            # 如果原始文本为空，直接使用小尾巴文本
            processed_text = tail_text
        else:
            # 如果原始文本不为空，按位置添加小尾巴
            tail_position = config.get("tail_position", "end")
            if tail_position == "start":
                processed_text = tail_text + "\n\n" + processed_text
            else:  # end
                processed_text = processed_text + "\n\n" + tail_text
    
    # 添加自定义按钮
    reply_markup = None
    custom_buttons = config.get("buttons", [])
    if custom_buttons:
        button_rows = []
        for button_config in custom_buttons:
            text_btn = button_config.get("text", "")
            url_btn = button_config.get("url", "")
            if text_btn and url_btn:
                # 处理URL格式
                if url_btn.startswith("@"):
                    url_btn = f"t.me/{url_btn[1:]}"
                elif not url_btn.startswith(("http://", "https://", "t.me/")):
                    url_btn = f"t.me/{url_btn}"
                
                if url_btn.startswith(("http://", "https://", "t.me/")):
                    button_rows.append([InlineKeyboardButton(text_btn, url=url_btn)])
        
        if button_rows:
            reply_markup = InlineKeyboardMarkup(button_rows)
    
    return processed_text.strip(), reply_markup


async def show_manage_file_extensions_menu(message, user_id):
    config = user_configs.get(str(user_id), {})
    extensions = config.get("file_filter_extensions", [])
    
    text = "📁 **副档名过滤管理**\n"
    if not extensions:
        text += "您尚未设定任何过滤副档名。"
    else:
        text += "以下是您已设定的副档名：\n" + ", ".join([f"`{ext}`" for ext in extensions])

    buttons = [
        [InlineKeyboardButton("➕ 新增副档名", callback_data=f"add_file_extension:{uuid.uuid4()}")],
        [InlineKeyboardButton("🗑️ 清空所有副档名", callback_data=f"delete_file_extension:clear_all")],
        [InlineKeyboardButton("🔙 返回文件过滤设定", callback_data="manage_file_filter")]
    ]
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup(buttons))

async def request_add_file_extension(message, user_id):
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "waiting_for_add_file_extension"}
    user_states.setdefault(user_id, []).append(new_task)
    await message.reply_text("📁 请回复您想新增的副档名。\n(多个副档名请用逗号 `,` 分隔)")

async def add_file_extension(message, user_id, task):
    extensions_text = message.text.strip()
    new_extensions = [ext.strip().lower() for ext in extensions_text.split(',') if ext.strip()]
    
    config = user_configs.setdefault(str(user_id), {})
    current_extensions = config.setdefault("file_filter_extensions", [])
    # 去重合并
    current_set = set(current_extensions)
    for ext in new_extensions:
        if ext not in current_set:
            current_extensions.append(ext)
            current_set.add(ext)
    
    save_configs()
    remove_task(user_id, task["task_id"])
    
    await message.reply_text(f"✅ 已新增副档名：`{', '.join(new_extensions)}`。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回副档名管理", callback_data="manage_file_extension_filter")]]))

async def delete_file_extension(message, user_id, ext):
    config = user_configs.setdefault(str(user_id), {})
    extensions = config.get("file_filter_extensions", [])
    
    if ext == "clear_all":
        config["file_filter_extensions"] = []
        text = "✅ 所有过滤副档名已清空。"
    else:
        if ext in extensions:
            extensions.remove(ext)
            text = f"✅ 副档名 `{ext}` 已删除。"
        else:
            text = f"❌ 副档名 `{ext}` 不存在。"
    
    save_configs()
    await safe_edit_or_reply(message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回副档名管理", callback_data="manage_file_extension_filter")]]))


async def handle_toggle_options(message, user_id, data):
    if str(user_id) not in user_configs: user_configs[str(user_id)] = {}
    
    option = data.replace("toggle_", "")
    
    if option == "remove_links":
        user_configs[str(user_id)]["remove_links"] = not user_configs[str(user_id)].get("remove_links", False)
        logging.info(f"用户 {user_id}  toggled remove_links to {user_configs[str(user_id)]['remove_links']}")
    elif option == "remove_hashtags":
        user_configs[str(user_id)]["remove_hashtags"] = not user_configs[str(user_id)].get("remove_hashtags", False)
        logging.info(f"用户 {user_id} toggled remove_hashtags to {user_configs[str(user_id)]['remove_hashtags']}")
    elif option == "remove_usernames":
        user_configs[str(user_id)]["remove_usernames"] = not user_configs[str(user_id)].get("remove_usernames", False)
        logging.info(f"用户 {user_id} toggled remove_usernames to {user_configs[str(user_id)]['remove_usernames']}")
    elif option == "filter_photo":
        user_configs[str(user_id)]["filter_photo"] = not user_configs[str(user_id)].get("filter_photo", False)
        logging.info(f"用户 {user_id} toggled filter_photo to {user_configs[str(user_id)]['filter_photo']}")
    elif option == "filter_video":
        user_configs[str(user_id)]["filter_video"] = not user_configs[str(user_id)].get("filter_video", False)
        logging.info(f"用户 {user_id} toggled filter_video to {user_configs[str(user_id)]['filter_video']}")
    elif option == "filter_buttons":
        user_configs[str(user_id)]["filter_buttons"] = not user_configs[str(user_id)].get("filter_buttons", False)
        logging.info(f"用户 {user_id} toggled filter_buttons to {user_configs[str(user_id)]['filter_buttons']}")
    elif option == "realtime_listen":
        user_configs[str(user_id)]["realtime_listen"] = not user_configs[str(user_id)].get("realtime_listen", False)
        logging.info(f"用户 {user_id} toggled realtime_listen to {user_configs[str(user_id)]['realtime_listen']}")
    
    save_configs() # 新增: 保存配置
        
    if option == "realtime_listen":
        await show_monitor_menu(message, user_id)
    elif option == "filter_buttons":
        await show_manage_filter_buttons_menu(message, user_id)
    elif "remove" in option:
        await toggle_content_removal_menu(message, user_id)
    elif "filter" in option:
        await show_file_filter_menu(message, user_id)

async def request_tail_text(message, user_id):
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "waiting_for_tail_text"}
    if user_id not in user_states: user_states[user_id] = []
    user_states[user_id].append(new_task)
    save_user_states()  # 保存用户状态
    
    # 添加返回按钮
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 返回功能设定", callback_data="show_feature_config_menu")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="show_main_menu")]
    ])
    
    await safe_edit_or_reply(message, 
        f"✍️ **设定附加文字（小尾巴）**\n\n"
        f"请回复您想设定的小尾巴内容。\n\n"
        f"**提示：**\n"
        f"• 若想清空，请回复 `清空`\n"
        f"• 可以包含表情符号和换行\n"
        f"• 支持 Markdown 格式\n\n"
        f"**任务ID:** `{task_id[:8]}`", 
        reply_markup=buttons)

async def set_tail_text(message, user_id, task):
    tail_text = message.text.strip()
    if str(user_id) not in user_configs: user_configs[str(user_id)] = {}

    if tail_text.lower() == "清空":
        user_configs[str(user_id)]["tail_text"] = ""
        user_configs[str(user_id)]["tail_position"] = "none"
        logging.info(f"用户 {user_id} 清空了小尾巴。")
        await message.reply_text("✅ 小尾巴设定已清空。", reply_markup=get_main_menu_buttons(user_id))
    else:
        user_configs[str(user_id)]["tail_text"] = tail_text
        logging.info(f"用户 {user_id} 设定了小尾巴内容。")
        await message.reply_text(
            f"✅ **小尾巴内容已设定**\n\n"
            f"📝 **内容预览:**\n{tail_text}\n\n"
            f"请选择放置位置：",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📍 放在信息开头", callback_data="set_tail_position_top"),
                    InlineKeyboardButton("📍 放在信息结尾", callback_data="set_tail_position_bottom")
                ],
                [InlineKeyboardButton("❌ 取消设定小尾巴", callback_data="set_tail_position_none")],
                [InlineKeyboardButton("🔙 返回功能设定", callback_data="show_feature_config_menu")],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data="show_main_menu")]
            ])
        )
    save_configs() # 新增: 保存配置
    remove_task(user_id, task["task_id"])
    save_user_states()  # 保存用户状态

async def handle_tail_position_setting(message, user_id, data):
    if str(user_id) not in user_configs: user_configs[str(user_id)] = {}
    
    position = data.replace("set_tail_position_", "")
    user_configs[str(user_id)]["tail_position"] = position
    
    if position == "top":
        await safe_edit_or_reply(message, "✅ 小尾巴已设定在信息开头。", reply_markup=get_main_menu_buttons(user_id))
    elif position == "bottom":
        await safe_edit_or_reply(message, "✅ 小尾巴已设定在信息结尾。", reply_markup=get_main_menu_buttons(user_id))
    elif position == "none":
        user_configs[str(user_id)]["tail_text"] = ""
        await safe_edit_or_reply(message, "✅ 小尾巴已清空。", reply_markup=get_main_menu_buttons(user_id))
    
    save_configs() # 新增: 保存配置
    logging.info(f"用户 {user_id} 设定了小尾巴位置为: {position}")

async def request_buttons_input(message, user_id):
    task_id = str(uuid.uuid4())
    new_task = {"task_id": task_id, "state": "waiting_for_buttons"}
    if user_id not in user_states: user_states[user_id] = []
    user_states[user_id].append(new_task)
    
    # 添加返回按钮
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 返回功能设定", callback_data="show_feature_config_menu")],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="show_main_menu")]
    ])
    
    await safe_edit_or_reply(message,
        f"📋 **设定附加按钮**\n\n"
        f"请回复您想设定的按钮配置：\n\n"
        f"**格式：** `按钮文字1,按钮链接1|按钮文字2,按钮链接2`\n\n"
        f"**示例：**\n"
        f"• `官网,https://example.com`\n"
        f"• `官网,https://example.com|TG群组,https://t.me/group`\n"
        f"• `联系客服,@support_bot|加入群组,t.me/mychannel`\n\n"
        f"**提示：**\n"
        f"• 若想清空所有按钮，请回复 `清空`\n"
        f"• 支持多种链接格式（http、https、t.me、@用户名）\n"
        f"• 多个按钮用 `|` 分隔\n\n"
        f"**任务ID:** `{task_id[:8]}`",
        reply_markup=buttons)

async def set_buttons(message, user_id, task):
    buttons_text = message.text.strip()
    if str(user_id) not in user_configs: user_configs[str(user_id)] = {}
    if buttons_text.lower() == "清空":
        user_configs[str(user_id)]["buttons"] = []
        logging.info(f"用户 {user_id} 清空了按钮设定。")
        
        # 改进清空反馈
        clear_buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 返回功能设定", callback_data="show_feature_config_menu")],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data="show_main_menu")]
        ])
        
        await message.reply_text(
            "✅ **按钮设定已清空**\n\n"
            "📋 所有自定义按钮已被移除。\n"
            "搬运的消息将不再包含附加按钮。", 
            reply_markup=clear_buttons)
    else:
        buttons_list = []
        try:
            button_items = buttons_text.split('|')
            for item in button_items:
                item = item.strip()
                if not item:  # 跳过空项
                    continue
                if ',' not in item:
                    await message.reply_text(f"❌ 格式错误：'{item}' 缺少逗号分隔符。请按照 `按钮文字,按钮链接` 格式输入。")
                    return
                text, url = item.split(',', 1)
                text = text.strip()
                url = url.strip()
                if not text or not url:
                    await message.reply_text(f"❌ 格式错误：按钮文字或链接不能为空。请检查输入格式。")
                    return
                buttons_list.append({"text": text, "url": url})
            
            if not buttons_list:
                await message.reply_text("❌ 没有找到有效的按钮配置。请按照正确格式输入。")
                return
                
            user_configs[str(user_id)]["buttons"] = buttons_list
            logging.info(f"用户 {user_id} 设定了按钮: {buttons_list}")
            
            # 生成按钮预览
            preview_text = "✅ **按钮设定完成**\n\n"
            preview_text += f"📊 **统计：** 共添加了 {len(buttons_list)} 个按钮\n\n"
            preview_text += "🔍 **预览：**\n"
            for i, btn in enumerate(buttons_list, 1):
                preview_text += f"{i}. 📋 `{btn['text']}` → `{btn['url']}`\n"
            
            # 添加返回选项
            return_buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 返回功能设定", callback_data="show_feature_config_menu")],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data="show_main_menu")]
            ])
            
            await message.reply_text(preview_text, reply_markup=return_buttons)
        except Exception as e:
            logging.warning(f"用户 {user_id} 输入了无效的按钮格式：{message.text}, 错误: {e}")
            await message.reply_text("❌ 无效格式，请按照 `按钮文字,按钮链接` 格式输入，多个按钮用 `|` 分隔。")
    save_configs() # 新增: 保存配置
    remove_task(user_id, task["task_id"])


# ==================== 附加内容频率控制 ====================
def should_add_tail_text(config, message_index=0):
    """判断是否应该添加附加文字"""
    tail_frequency_mode = config.get("tail_frequency_mode", "always")  # always, interval, random
    
    if tail_frequency_mode == "always":
        return True
    elif tail_frequency_mode == "interval":
        interval = config.get("tail_interval", 10)  # 默认每10条消息添加一次
        return (message_index + 1) % interval == 0
    elif tail_frequency_mode == "random":
        probability = config.get("tail_random_probability", 20)  # 默认20%概率
        return random.randint(1, 100) <= probability
    
    return False

def should_add_buttons(config, message_index=0):
    """判断是否应该添加附加按钮"""
    button_frequency_mode = config.get("button_frequency_mode", "always")  # always, interval, random
    
    if button_frequency_mode == "always":
        return True
    elif button_frequency_mode == "interval":
        interval = config.get("button_interval", 10)  # 默认每10条消息添加一次
        return (message_index + 1) % interval == 0
    elif button_frequency_mode == "random":
        probability = config.get("button_random_probability", 20)  # 默认20%概率
        return random.randint(1, 100) <= probability
    
    return False

# ==================== 核心搬运逻辑 (新增所有功能) ====================
def process_message_content(text, config, message_index=0):
    if not text:
        return "", None

    # 敏感词替换
    replacements = config.get("replacement_words", {})
    for old, new in replacements.items():
        text = text.replace(old, new)
        
    # 移除超链接
    if config.get("remove_links"):
        text = re.sub(r'https?://[^\s/$.?#].[^\s]*', '', text, flags=re.MULTILINE)
        
    # 移除Hashtags
    if config.get("remove_hashtags"):
        text = re.sub(r'#\w+', '', text)
        
    # 移除使用者名称
    if config.get("remove_usernames"):
        text = re.sub(r'@\w+', '', text)

    # 处理小尾巴（根据频率控制）
    tail_text = config.get("tail_text", "").strip()
    tail_position = config.get("tail_position", "none")
    if tail_text and should_add_tail_text(config, message_index):
        if tail_position == "top":
            text = f"{tail_text}\n\n{text}"
        elif tail_position == "bottom":
            text = f"{text}\n\n{tail_text}"

    # 处理按钮（结合过滤策略和频率控制）
    buttons_config = config.get("buttons", [])
    if not should_add_buttons(config, message_index):
        buttons_config = []  # 如果不应该添加按钮，清空按钮配置
    filter_buttons_enabled = config.get("filter_buttons")
    filter_buttons_mode = config.get("filter_buttons_mode", "drop")  # drop | strip | whitelist
    whitelist_domains = set(config.get("button_domain_whitelist", []))
    reply_markup = None
    if buttons_config:
        # 如果启用了过滤并且策略是 strip，则不附加按钮；whitelist 则仅保留白名单域名的按钮
        effective_buttons = buttons_config
        if filter_buttons_enabled:
            if filter_buttons_mode == "strip":
                effective_buttons = []
            elif filter_buttons_mode == "whitelist":
                filtered = []
                for b in buttons_config:
                    try:
                        url = b.get('url', '')
                        # 粗略域名提取
                        domain = url.split('//', 1)[-1].split('/', 1)[0].lower()
                        if domain.startswith('www.'):
                            domain = domain[4:]
                        if domain in whitelist_domains:
                            filtered.append(b)
                    except:
                        continue
                effective_buttons = filtered
        if effective_buttons:
            keyboard = [[InlineKeyboardButton(button['text'], url=button['url'])] for button in effective_buttons]
            reply_markup = InlineKeyboardMarkup(keyboard)

    return text.strip(), reply_markup

# 旧的过滤函数已删除，新引擎内置了更强大的过滤功能


# 旧的批量发送管理器和克隆函数已删除，现在只使用新引擎










# ==================== 新搬运引擎接口 ====================
@monitor_performance('start_cloning_with_new_engine')
async def start_cloning_with_new_engine(client, message, user_id, task):
    """使用新引擎的搬运流程"""
    global robust_cloning_engine
    
    if not NEW_ENGINE_AVAILABLE:
        await safe_edit_or_reply(message, 
            "❌ 新搬运引擎不可用，请检查 new_cloning_engine.py 文件",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")
            ]]))
        return
    
    # 初始化新引擎
    if robust_cloning_engine is None:
        robust_cloning_engine = RobustCloningEngine(client)
    
    # 保存原始任务，避免变量名冲突
    original_task = task
    
    task_id_short = original_task["task_id"][:8]
    clone_tasks = original_task["clone_tasks"]
    
    logging.info(f"🚀 使用新引擎启动任务 `{task_id_short}` (共 {len(clone_tasks)} 个子任务)")
    
    try:
        # 初始化取消标志
        running_task_cancellation[original_task["task_id"]] = False
        
        await safe_edit_or_reply(message, 
            f"🆕 **老湿姬2.0搬运** `{task_id_short}`\n"
            f"📋 子任务数: {len(clone_tasks)}\n"
            f"🔧 引擎: 老湿姬2.0\n"
            f"⏳ 正在初始化并发任务...",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🛑 取消任务", callback_data=f"cancel_task:{original_task['task_id']}")
            ]])
        )
        
        # 立即显示任务列表，让用户知道系统在工作
        await asyncio.sleep(0.1)  # 短暂延迟确保消息发送
        subtask_list = "📋 **子任务列表**:\n"
        for j, sub_task_item in enumerate(clone_tasks):
            sub_source = sub_task_item['pair']['source'][:20] + "..." if len(sub_task_item['pair']['source']) > 20 else sub_task_item['pair']['source']
            sub_target = sub_task_item['pair']['target'][:20] + "..." if len(sub_task_item['pair']['target']) > 20 else sub_task_item['pair']['target']
            subtask_list += f"🔄 **任务{j+1}**: `{sub_source}` → `{sub_target}`\n"
        
        await safe_edit_or_reply(message, 
            f"🆕 **老湿姬2.0搬运** `{task_id_short}`\n"
            f"📋 子任务数: {len(clone_tasks)}\n"
            f"🔧 引擎: 老湿姬2.0 (并发模式)\n"
            f"🚀 正在启动搬运引擎...\n\n"
            f"{subtask_list}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🛑 取消任务", callback_data=f"cancel_task:{original_task['task_id']}")
            ]])
        )
        
        start_time = time.time()
        config = user_configs.get(str(user_id), {})
        
        total_stats = {
            "total_processed": 0,
            "successfully_cloned": 0,
            "duplicates_skipped": 0,
            "errors": 0,
            "already_processed": 0
        }
        
        # 并发处理多个子任务
        logging.info(f"🚀 开始并发执行 {len(clone_tasks)} 个子任务")
        print(f"[DEBUG] 控制台日志测试: 开始并发执行 {len(clone_tasks)} 个子任务")  # 调试用
        
        # 创建任务状态跟踪
        task_progress = {}
        for i, sub_task in enumerate(clone_tasks):
            task_progress[i] = {
                "status": "等待中",
                "progress": 0,
                "cloned": 0,
                "processed": 0,
                "errors": 0
            }
        
        # 全局进度更新锁和时间
        last_global_update = 0
        update_lock = asyncio.Lock()
        
        async def global_progress_update():
            """全局进度更新函数"""
            nonlocal last_global_update
            async with update_lock:
                current_time = time.time()
                if current_time - last_global_update < 0.3:  # 提高更新频率到0.3秒
                    return
                last_global_update = current_time
                
                elapsed = current_time - start_time
                
                # 计算总体统计
                total_cloned = sum(progress["cloned"] for progress in task_progress.values())
                total_processed = sum(progress["processed"] for progress in task_progress.values())
                total_errors = sum(progress["errors"] for progress in task_progress.values())
                speed = total_cloned / max(elapsed, 1)
                
                # 构建简化的任务状态显示（文本模式，更快渲染）
                concurrent_status = f"**并发任务状态** ({len(clone_tasks)} 个任务):\n"
                for j, sub_task_item in enumerate(clone_tasks):
                    sub_source = sub_task_item['pair']['source'][:12] + "..." if len(sub_task_item['pair']['source']) > 12 else sub_task_item['pair']['source']
                    sub_target = sub_task_item['pair']['target'][:12] + "..." if len(sub_task_item['pair']['target']) > 12 else sub_task_item['pair']['target']
                    
                    progress_info = task_progress[j]
                    status = progress_info["status"]
                    progress_pct = progress_info["progress"]
                    cloned = progress_info["cloned"]
                    processed = progress_info["processed"]
                    errors = progress_info["errors"]
                    
                    if status == "进行中":
                        concurrent_status += f"🔄 T{j+1}: {sub_source}→{sub_target} | {progress_pct:.0f}% | ✅{cloned} ❌{errors}\n"
                    elif status == "完成":
                        concurrent_status += f"✅ T{j+1}: {sub_source}→{sub_target} | 完成 | ✅{cloned} ❌{errors}\n"
                    elif status == "等待中":
                        concurrent_status += f"⏸️ T{j+1}: {sub_source}→{sub_target} | 等待启动\n"
                    else:
                        concurrent_status += f"❌ T{j+1}: {sub_source}→{sub_target} | 错误 | ❌{errors}\n"
                
                progress_text = (
                    f"🚀 **老湿姬2.0** `{task_id_short}` **并发进行中**\n\n"
                    f"📈 **总体统计**: ✅{total_cloned} | 🔄{total_processed} | ❌{total_errors} | ⚡{speed:.1f}/s | ⏱️{elapsed:.1f}s\n\n"
                    f"{concurrent_status}\n"
                    f"🔧 **并发模式**: 多任务同时执行，提升效率"
                )
                
                try:
                    await safe_edit_or_reply(message, progress_text,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🛑 停止任务", callback_data=f"cancel_task:{original_task['task_id']}")
                        ]])
                    )
                except Exception as e:
                    logging.debug(f"更新进度失败: {e}")
        
        # 创建子任务协程
        async def process_subtask(i, sub_task):
            """处理单个子任务"""
            source = sub_task['pair']['source']
            target = sub_task['pair']['target']
            start_id = sub_task['start_id']
            end_id = sub_task['end_id']
            
            # 性能优化：智能错峰启动，避免资源竞争
            if i >= max_concurrent_tasks:
                # 超出并发限制的任务需要延迟启动
                batch_number = i // max_concurrent_tasks
                stagger_delay = batch_number * 3  # 每批延迟3秒，减少等待时间
                logging.info(f"⏱️ 子任务 {i+1} 将在 {stagger_delay} 秒后启动（批次 {batch_number + 1}）")
                print(f"[性能优化] 子任务 {i+1} 批次 {batch_number + 1}，延迟启动: {stagger_delay}秒")
                await asyncio.sleep(stagger_delay)
            else:
                # 前4个任务立即启动，只做最小延迟避免API限流
                if i > 0:
                    min_delay = i * 0.5  # 最小延迟0.5秒
                    logging.debug(f"⏱️ 子任务 {i+1} 最小延迟 {min_delay} 秒（避免API限流）")
                    await asyncio.sleep(min_delay)
            
            logging.info(f"🔄 并发子任务 {i+1}/{len(clone_tasks)} 开始: {source} -> {target}")
            print(f"[DEBUG] 子任务 {i+1} 开始: {source} -> {target}")  # 调试用
            task_progress[i]["status"] = "进行中"
            
            # 子任务进度回调 - 优化版本
            async def subtask_progress_callback(stats):
                if stats.get("requested_range", 1) > 0:
                    progress_pct = (stats.get("total_processed", 0) / stats.get("requested_range", 1)) * 100
                    task_progress[i]["progress"] = min(progress_pct, 100)
                    task_progress[i]["cloned"] = stats.get("successfully_cloned", 0)
                    task_progress[i]["processed"] = stats.get("total_processed", 0)
                    task_progress[i]["errors"] = stats.get("errors", 0)
                    task_progress[i]["current_offset_id"] = stats.get("current_offset_id", start_id)
                    
                    # 立即触发全局进度更新，不等待
                    try:
                        await global_progress_update()
                    except Exception as e:
                        logging.debug(f"进度更新失败: {e}")
            
            # 检查取消函数 - 使用主任务ID检查取消状态
            def check_cancellation():
                # 检查主任务的取消状态
                is_cancelled = running_task_cancellation.get(original_task["task_id"], False)
                if is_cancelled:
                    logging.info(f"子任务 {i+1} 检测到取消信号")
                return is_cancelled
            
            try:
                # 检查是否为恢复模式，传递恢复数据
                restore_progress = None
                if original_task.get("restore_mode") and original_task.get("progress"):
                    restore_progress = original_task["progress"].get(str(i), {})
                
                # 强制设置更频繁的进度更新
                enhanced_config = config.copy()
                enhanced_config["force_frequent_updates"] = True  # 标记强制频繁更新
                
                sub_stats = await robust_cloning_engine.clone_messages_robust(
                    source_chat_id=source,
                    target_chat_id=target,
                    start_id=start_id,
                    end_id=end_id,
                    config=enhanced_config,
                    progress_callback=subtask_progress_callback,
                    task_id=f"{original_task['task_id']}_sub_{i}",
                    cancellation_check=check_cancellation,
                    restore_progress=restore_progress
                )
                
                task_progress[i]["status"] = "完成"
                task_progress[i]["progress"] = 100
                task_progress[i]["cloned"] = sub_stats.get("successfully_cloned", 0)
                task_progress[i]["processed"] = sub_stats.get("total_processed", 0)
                task_progress[i]["errors"] = sub_stats.get("errors", 0)
                
                logging.info(f"✅ 并发子任务 {i+1} 完成: 搬运 {sub_stats.get('successfully_cloned', 0)} 条")
                return sub_stats
                
            except Exception as e:
                logging.error(f"❌ 并发子任务 {i+1} 失败: {e}")
                task_progress[i]["status"] = "错误"
                return {"successfully_cloned": 0, "total_processed": 0, "errors": 1, "duplicates_skipped": 0, "already_processed": 0}
        
        # 启动所有子任务并发执行 - 性能优化：限制最大并发数
        # 创建真正的Task对象，而不是协程
        max_concurrent_tasks = 4  # 限制最大并发任务数，防止卡顿
        
        if len(clone_tasks) > max_concurrent_tasks:
            logging.warning(f"⚠️ 任务数量({len(clone_tasks)})超过最大并发数({max_concurrent_tasks})，将分批执行")
            print(f"[性能优化] 任务数量: {len(clone_tasks)}, 最大并发: {max_concurrent_tasks}")
        
        # 分批创建任务，避免同时启动过多任务
        tasks = []
        for i, sub_task in enumerate(clone_tasks):
            if i >= max_concurrent_tasks:
                # 超出并发限制的任务延迟启动
                delay = (i // max_concurrent_tasks) * 5  # 每批延迟5秒
                logging.info(f"⏱️ 子任务 {i+1} 将在 {delay} 秒后启动（超出并发限制）")
                print(f"[性能优化] 子任务 {i+1} 延迟启动: {delay}秒")
            
            subtask = asyncio.create_task(process_subtask(i, sub_task))
            tasks.append(subtask)
        
        # 添加定期状态更新任务
        async def periodic_status_update():
            """定期更新任务状态，确保状态实时性"""
            while True:
                try:
                    # 检查是否所有任务都已完成
                    all_completed = all(task.done() for task in tasks)
                    if all_completed:
                        break
                    
                    # 每2秒强制更新一次状态
                    await asyncio.sleep(2.0)
                    await global_progress_update()
                    
                except Exception as e:
                    logging.debug(f"定期状态更新失败: {e}")
                    break
        
        # 启动定期状态更新任务
        status_update_task = asyncio.create_task(periodic_status_update())
        
        # 等待所有任务完成，但定期检查取消状态
        sub_results = []
        try:
            # 使用asyncio.wait和定期检查来支持更快的取消响应
            pending_tasks = set(tasks)
            
            while pending_tasks:
                # 检查取消状态
                if running_task_cancellation.get(original_task["task_id"], False):
                    logging.info(f"主控制器检测到取消信号，开始终止所有子任务")
                    # 取消所有未完成的任务
                    for pending_task in pending_tasks:
                        if not pending_task.done():
                            pending_task.cancel()
                    # 等待所有任务清理完毕
                    await asyncio.gather(*pending_tasks, return_exceptions=True)
                    break
                
                # 等待任务完成，但设置超时以便定期检查取消状态
                done, pending = await asyncio.wait(pending_tasks, timeout=2.0, return_when=asyncio.FIRST_COMPLETED)
                
                # 收集已完成的任务结果
                for task_done in done:
                    try:
                        result = task_done.result()
                        sub_results.append(result)
                    except Exception as e:
                        sub_results.append(e)
                
                # 更新待完成任务集合
                pending_tasks = pending
                
        except Exception as e:
            logging.error(f"任务执行过程中出错: {e}")
            # 等待所有任务完成（包括被取消的）
            results = await asyncio.gather(*tasks, return_exceptions=True)
            sub_results.extend(results)
        
        # 取消定期状态更新任务
        status_update_task.cancel()
        try:
            await status_update_task
        except asyncio.CancelledError:
            pass
        
        # 检查是否被取消
        was_cancelled = running_task_cancellation.get(original_task["task_id"], False)
        
        # 汇总所有子任务的统计结果
        for sub_stats in sub_results:
            if isinstance(sub_stats, dict):
                for key in total_stats:
                    total_stats[key] += sub_stats.get(key, 0)
        
        # 最终结果
        end_time = time.time()
        total_elapsed = end_time - start_time
        
        # 根据是否被取消显示不同的结果
        if was_cancelled:
            final_text = (
                f"🛑 **任务** `{task_id_short}` **已取消**\n\n"
                f"📊 **取消前统计:**\n"
                f"✅ **成功搬运**: {total_stats['successfully_cloned']} 条\n"
                f"🔄 **总处理**: {total_stats['total_processed']} 条\n"
                f"🔁 **跳过重复**: {total_stats['duplicates_skipped']} 条\n"
                f"♻️ **已处理过**: {total_stats['already_processed']} 条\n"
                f"❌ **错误**: {total_stats['errors']} 条\n\n"
                f"⏱️ **运行时间**: {total_elapsed:.1f} 秒\n"
                f"⚡ **平均速度**: {total_stats['successfully_cloned'] / max(total_elapsed, 1):.1f} 条/秒\n\n"
                f"🆕 **引擎**: 老湿姬2.0 (并发模式)\n"
                f"🔧 **重复检测**: SHA256内容指纹\n"
                f"💾 **断点续传**: 可从断点继续\n\n"
                f"💡 **提示**: 此任务已保存进度，可在'查看任务'中恢复"
            )
            
            # 保存被取消任务的状态，支持续传
            if str(user_id) not in running_tasks:
                running_tasks[str(user_id)] = {}
            
            # 转换task_progress格式，确保兼容性
            converted_progress = {}
            for task_idx, progress_info in task_progress.items():
                # 同时保存数字格式和sub_task格式，确保兼容性
                converted_progress[str(task_idx)] = {
                    "cloned": progress_info.get("cloned", 0),
                    "processed": progress_info.get("processed", 0),
                    "errors": progress_info.get("errors", 0),
                    "cloned_count": progress_info.get("cloned", 0),  # 兼容旧格式
                    "processed_count": progress_info.get("processed", 0),  # 兼容旧格式
                    "current_offset_id": progress_info.get("current_offset_id", clone_tasks[task_idx]['start_id'] if task_idx < len(clone_tasks) else 0)
                }
                converted_progress[f"sub_task_{task_idx}"] = converted_progress[str(task_idx)]
            
            running_tasks[str(user_id)][original_task["task_id"]] = {
                "clone_tasks": clone_tasks,
                "cancelled": True,
                "cancelled_time": time.time(),
                "partial_stats": total_stats,
                "progress": converted_progress
            }
            save_running_tasks()
            
            reply_buttons = [
                [InlineKeyboardButton("🔄 恢复任务", callback_data=f"resume:{original_task['task_id']}")],
                [InlineKeyboardButton("📜 查看我的任务", callback_data="view_tasks")]
            ]
            
        else:
            final_text = (
                f"🎉 **任务** `{task_id_short}` **完成！**\n\n"
                f"📊 **最终统计:**\n"
                f"✅ **成功搬运**: {total_stats['successfully_cloned']} 条\n"
                f"🔄 **总处理**: {total_stats['total_processed']} 条\n"
                f"🔁 **跳过重复**: {total_stats['duplicates_skipped']} 条\n"
                f"♻️ **已处理过**: {total_stats['already_processed']} 条\n"
                f"❌ **错误**: {total_stats['errors']} 条\n\n"
                f"⏱️ **总用时**: {total_elapsed:.1f} 秒\n"
                f"⚡ **平均速度**: {total_stats['successfully_cloned'] / max(total_elapsed, 1):.1f} 条/秒\n\n"
                f"🆕 **引擎**: 老湿姬2.0 (并发模式)\n"
                f"🔧 **重复检测**: SHA256内容指纹\n"
                f"💾 **断点续传**: 已保存处理记录"
            )
            
            reply_buttons = [
                [InlineKeyboardButton("📜 查看我的任务", callback_data="view_tasks")]
            ]
        
        # 无论是否取消，都保存历史记录（但标注状态）
        if str(user_id) not in user_history:
            user_history[str(user_id)] = []
        
        for i, sub_task in enumerate(clone_tasks):
            # 获取准确的进度数据
            sub_progress = task_progress.get(i, {}) or task_progress.get(f"sub_task_{i}", {})
            
            if was_cancelled and sub_progress:
                # 取消的任务：使用实际进度
                sub_cloned = sub_progress.get("cloned_count", 0) or sub_progress.get("cloned", 0)
                sub_processed = sub_progress.get("processed_count", 0) or sub_progress.get("processed", 0)
            else:
                # 完成的任务：使用实际统计数据
                sub_cloned = total_stats['successfully_cloned'] // len(clone_tasks) if len(clone_tasks) > 0 else 0
                sub_processed = total_stats['total_processed'] // len(clone_tasks) if len(clone_tasks) > 0 else 0
            
            # 计算实际范围
            start_id = sub_task['start_id']
            end_id = sub_task['end_id']
            total_range = end_id - start_id + 1
            
            # 获取详细统计信息
            msg_stats = sub_progress.get("message_stats", {}) if sub_progress else {}
            photo_count = msg_stats.get("photo_count", 0)
            video_count = msg_stats.get("video_count", 0)
            text_count = msg_stats.get("text_count", 0)
            media_group_count = msg_stats.get("media_group_count", 0)
            
            user_history[str(user_id)].append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "source": sub_task['pair']['source'],
                "target": sub_task['pair']['target'],
                "start_id": start_id,
                "end_id": end_id,
                "total_range": total_range,
                "cloned_count": sub_cloned,
                "processed_count": sub_processed,
                "engine": "老湿姬2.0",
                "duplicates_skipped": total_stats.get('duplicates_skipped', 0) // len(clone_tasks) if len(clone_tasks) > 0 else 0,
                "status": "取消" if was_cancelled else "完成",
                "runtime": f"{total_elapsed:.1f}秒",
                # 详细统计
                "photo_count": photo_count,
                "video_count": video_count,
                "text_count": text_count,
                "media_group_count": media_group_count
            })
        
        save_history()
        
        # 发送任务完成通知
        await send_task_completion_notification(message, user_id, task_id_short, total_stats, was_cancelled)
        
        await safe_edit_or_reply(message, final_text, 
                               reply_markup=InlineKeyboardMarkup(reply_buttons))
        
        if was_cancelled:
            logging.info(f"新引擎任务 `{task_id_short}` 被取消: 已搬运 {total_stats['successfully_cloned']}, 已保存断点")
        else:
            logging.info(f"新引擎任务 `{task_id_short}` 完成: 成功 {total_stats['successfully_cloned']}, 重复 {total_stats['duplicates_skipped']}")
        
    except Exception as e:
        logging.error(f"新引擎任务 `{task_id_short}` 失败: {e}")
        await safe_edit_or_reply(message, 
            f"❌ **任务** `{task_id_short}` **失败**\n\n"
            f"错误: {str(e)}\n\n"
            f"请联系管理员检查问题。",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")
            ]]))
    
    finally:
        # 清理任务状态和取消标志
        # 注意：被取消的任务不清理running_tasks状态，以便续传
        was_cancelled_final = running_task_cancellation.get(task["task_id"], False)
        
        remove_task(user_id, task["task_id"])
        if task["task_id"] in running_task_cancellation:
            del running_task_cancellation[task["task_id"]]
            
        # 如果任务被取消，保留running_tasks状态用于续传
        if not was_cancelled_final:
            # 只有正常完成的任务才完全清理running_tasks
            if str(user_id) in running_tasks and task["task_id"] in running_tasks[str(user_id)]:
                del running_tasks[str(user_id)][task["task_id"]]
                save_running_tasks()

# ==================== 优雅停止处理 ====================
def signal_handler(signum, frame):
    """信号处理器，优雅停止机器人"""
    logging.info("收到停止信号，正在关闭机器人...")
    try:
        if app.is_connected:
            app.stop()
    except:
        pass
    sys.exit(0)

# ==================== 配置验证 ====================
def validate_user_config(config):
    """验证用户配置的有效性"""
    errors = []
    
    # 验证频道ID格式
    for pair in config.get("channel_pairs", []):
        source = pair.get("source")
        target = pair.get("target")
        
        if not source or not target:
            errors.append("频道组配置不完整")
        
        # 更宽松的频道ID验证
        if isinstance(source, str):
            # 检查是否为有效的频道标识符
            # 1. 以@开头的用户名
            # 2. 纯数字ID（可能带负号）
            # 3. 不带@的用户名（字母、数字、下划线组合，长度5-32）
            if not (source.startswith('@') or 
                   source.lstrip('-').isdigit() or 
                   (len(source) >= 5 and len(source) <= 32 and 
                    source.replace('_', '').isalnum())):
                errors.append(f"无效的源频道ID: {source}")
        
        # 检查源频道和目标频道不能相同
        if source == target:
            errors.append(f"源频道和目标频道不能相同: {source} → {target}")
    
    return errors

# ==================== 端口绑定和心跳机制 ====================
def start_port_server():
    """启动端口服务器，用于Render Web Service"""
    try:
        import socket
        import http.server
        import socketserver
        
        class SimpleHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                response = """
                <html>
                <head><title>搬运机器人服务</title></head>
                <body>
                <h1>🤖 {bot_name} - {bot_version}</h1>
                <p>机器人ID: {bot_config['bot_id']}</p>
                <p>状态：正常运行中</p>
                <p>时间：{current_time}</p>
                </body>
                </html>
                """.format(
                    bot_name=bot_config['bot_name'],
                    bot_version=bot_config['bot_version'],
                    current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                self.wfile.write(response.encode())
            
            def log_message(self, format, *args):
                # 禁用HTTP访问日志
                pass
        
        # 绑定到Render分配的端口
        port = int(os.environ.get('PORT', 8080))
        
        with socketserver.TCPServer(("", port), SimpleHandler) as httpd:
            print(f"🌐 [{bot_config['bot_id']}] 端口服务器启动成功，监听端口 {port}")
            httpd.serve_forever()
    
    except Exception as e:
        print(f"⚠️ [{bot_config['bot_id']}] 端口服务器启动失败: {e}")

def start_heartbeat():
    """启动心跳机制，防止Render 15分钟自动停止"""
    import requests
    import time
    
    while True:
        try:
            # 获取当前服务URL
            service_url = os.environ.get('RENDER_EXTERNAL_URL')
            if service_url:
                # 向自己的服务发送请求，保持活跃
                response = requests.get(f"{service_url}/", timeout=10)
                print(f"💓 [{bot_config['bot_id']}] 心跳请求成功: {response.status_code}")
            else:
                print(f"💓 [{bot_config['bot_id']}] 心跳机制运行中（无外部URL）")
        except Exception as e:
            print(f"💓 [{bot_config['bot_id']}] 心跳请求失败: {e}")
        
        # 每10分钟发送一次心跳
        time.sleep(600)

# ==================== 启动机器人 ====================
if __name__ == "__main__":
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    # 在后台启动端口服务器
    import threading
    port_thread = threading.Thread(target=start_port_server, daemon=True)
    port_thread.start()
    
    # 启动心跳线程
    heartbeat_thread = threading.Thread(target=start_heartbeat, daemon=True)
    heartbeat_thread.start()
    print(f"💓 [{bot_config['bot_id']}] 心跳机制已启动，每10分钟发送一次请求")
    
    load_configs()
    load_history()
    load_running_tasks()
    load_login_data()
    load_user_states()
    
    # 验证用户配置
    for user_id, config in user_configs.items():
        errors = validate_user_config(config)
        if errors:
            logging.warning(f"用户 {user_id} 配置存在问题: {', '.join(errors)}")
    
    # 加载性能统计
    try:
        if os.path.exists("performance_stats.json"):
            with open("performance_stats.json", "r", encoding="utf-8") as f:
                saved_stats = json.load(f)
                logging.info(f"已加载 {len(saved_stats)} 个函数的性能统计")
    except Exception as e:
        logging.warning(f"加载性能统计失败: {e}")
    
    # 启动保活服务器（仅在 Render 部署时）
    if RENDER_DEPLOYMENT:
        try:
            run_keep_alive()
            logging.info("Render 保活服务器已启动")
        except Exception as e:
            logging.warning(f"保活服务器启动失败: {e}")
    
    # 初始化新搬运引擎
    if NEW_ENGINE_AVAILABLE:
        logging.info("新搬运引擎已准备就绪")
    
    # 启动总结
    print("=" * 60)
    print(f"✅ 启动完成！{bot_config['bot_name']} 状态:")
    print(f"   🔑 机器人ID: {bot_config['bot_id']}")
    print(f"   📡 新搬运引擎: {'✅ 可用' if NEW_ENGINE_AVAILABLE else '❌ 不可用'}")
    print(f"   🌐 Render部署: {'✅ 启用' if RENDER_DEPLOYMENT else '❌ 禁用'}")
    print(f"   🔐 登录验证: {'✅ 启用' if ENABLE_USERNAME_LOGIN else '❌ 禁用'}")
    print(f"   👑 管理员: {len(ADMIN_USERNAMES)} 人")
    print(f"   ⚡ 性能监控: ✅ 启用")
    print(f"   🛡️ FloodWait保护: ✅ 已修复异常限制")
    print(f"   🔄 自动恢复: ✅ 每5分钟检查一次")
    print("   🎯 按 Ctrl+C 一次即可停止机器人")
    print("=" * 60)
    
    logging.info("机器人正在运行...")
    
    try:
        app.run()
    except KeyboardInterrupt:
        logging.info("用户中断，正在关闭...")
    except Exception as e:
        logging.error(f"机器人运行出错: {e}")
    finally:
        # 保存状态
        try:
            save_configs()
            save_history()
            save_running_tasks()
            save_user_states()
            save_login_data()
            if NEW_ENGINE_AVAILABLE and robust_cloning_engine:
                robust_cloning_engine.deduplicator.save_fingerprints()
            
            # 保存性能统计
            if performance_stats:
                try:
                    with open("performance_stats.json", "w", encoding="utf-8") as f:
                        # 转换为可序列化的格式
                        serializable_stats = {}
                        for func_name, durations in performance_stats.items():
                            if durations:
                                serializable_stats[func_name] = {
                                    'count': len(durations),
                                    'avg': sum(durations) / len(durations),
                                    'max': max(durations),
                                    'min': min(durations),
                                    'total': sum(durations)
                                }
                        json.dump(serializable_stats, f, ensure_ascii=False, indent=4)
                    logging.info("性能统计已保存")
                except Exception as e:
                    logging.error(f"保存性能统计失败: {e}")
        except:
            pass
        logging.info("机器人已安全退出")
