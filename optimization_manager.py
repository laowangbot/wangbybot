#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存管理和连接池优化管理器
提升机器人性能和稳定性
"""

import asyncio
import time
import logging
import weakref
from collections import OrderedDict
from typing import Dict, List, Optional, Any
import psutil
import gc

class SmartCache:
    """智能缓存管理器 - 防止内存泄漏"""
    
    def __init__(self, max_size=5000, cleanup_interval=300):
        self.max_size = max_size
        self.cache = OrderedDict()
        self.access_count = {}
        self.last_access = {}
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = time.time()
        
        # 启动自动清理任务
        asyncio.create_task(self._auto_cleanup())
    
    def add(self, key: str, value: Any, ttl: int = 3600):
        """添加缓存项，支持TTL（生存时间）"""
        current_time = time.time()
        
        # 检查是否需要清理
        if len(self.cache) >= self.max_size:
            self._smart_cleanup()
        
        # 添加新项
        self.cache[key] = {
            'value': value,
            'created': current_time,
            'ttl': ttl,
            'access_count': 0
        }
        self.access_count[key] = 0
        self.last_access[key] = current_time
        
        logging.debug(f"缓存添加: {key}, 当前缓存大小: {len(self.cache)}")
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项，更新访问统计"""
        if key in self.cache:
            item = self.cache[key]
            current_time = time.time()
            
            # 检查TTL
            if current_time - item['created'] > item['ttl']:
                self.remove(key)
                return None
            
            # 更新访问统计
            item['access_count'] += 1
            self.access_count[key] = item['access_count']
            self.last_access[key] = current_time
            
            # 移动到末尾（最近访问）
            self.cache.move_to_end(key)
            
            return item['value']
        return None
    
    def remove(self, key: str):
        """移除缓存项"""
        if key in self.cache:
            del self.cache[key]
            if key in self.access_count:
                del self.access_count[key]
            if key in self.last_access:
                del self.last_access[key]
            logging.debug(f"缓存移除: {key}")
    
    def _smart_cleanup(self):
        """智能清理策略"""
        if len(self.cache) < self.max_size * 0.8:  # 如果缓存使用率低于80%，不清理
            return
        
        current_time = time.time()
        
        # 计算清理数量（清理20%）
        cleanup_count = max(1, int(len(self.cache) * 0.2))
        
        # 策略1：清理过期项
        expired_keys = []
        for key, item in self.cache.items():
            if current_time - item['created'] > item['ttl']:
                expired_keys.append(key)
        
        # 策略2：清理最少访问的项
        if len(expired_keys) < cleanup_count:
            remaining = cleanup_count - len(expired_keys)
            sorted_keys = sorted(self.access_count.items(), key=lambda x: x[1])
            least_used_keys = [key for key, _ in sorted_keys[:remaining]]
            expired_keys.extend(least_used_keys)
        
        # 执行清理
        for key in expired_keys:
            self.remove(key)
        
        logging.info(f"智能清理完成: 清理了 {len(expired_keys)} 个缓存项")
    
    async def _auto_cleanup(self):
        """自动清理任务"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                self._smart_cleanup()
            except Exception as e:
                logging.error(f"自动清理任务出错: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        current_time = time.time()
        expired_count = sum(
            1 for item in self.cache.values() 
            if current_time - item['created'] > item['ttl']
        )
        
        return {
            'total_items': len(self.cache),
            'max_size': self.max_size,
            'usage_percent': (len(self.cache) / self.max_size) * 100,
            'expired_items': expired_count,
            'avg_access_count': sum(self.access_count.values()) / max(len(self.access_count), 1)
        }

class TelegramConnectionPool:
    """Telegram连接池管理器"""
    
    def __init__(self, max_connections=3, health_check_interval=60):
        self.max_connections = max_connections
        self.connections = []
        self.connection_info = {}  # 连接信息：创建时间、健康状态、使用次数
        self.health_check_interval = health_check_interval
        self.last_health_check = time.time()
        self.connection_lock = asyncio.Lock()
        
        # 启动健康检查任务
        asyncio.create_task(self._health_check_task())
    
    async def get_healthy_connection(self, client):
        """获取健康的连接"""
        async with self.connection_lock:
            # 检查现有连接
            for i, conn_info in enumerate(self.connection_info):
                if conn_info['healthy'] and not conn_info['in_use']:
                    conn_info['in_use'] = True
                    conn_info['use_count'] += 1
                    conn_info['last_used'] = time.time()
                    return self.connections[i]
            
            # 如果没有可用连接，创建新的
            if len(self.connections) < self.max_connections:
                return await self._create_new_connection(client)
            
            # 如果达到最大连接数，等待可用连接
            return await self._wait_for_available_connection()
    
    async def _create_new_connection(self, client):
        """创建新连接"""
        try:
            # 创建新的客户端连接
            new_client = client.copy()
            await new_client.start()
            
            # 添加到连接池
            self.connections.append(new_client)
            self.connection_info[len(self.connections) - 1] = {
                'created': time.time(),
                'healthy': True,
                'in_use': True,
                'use_count': 1,
                'last_used': time.time(),
                'last_health_check': time.time()
            }
            
            logging.info(f"创建新连接，当前连接数: {len(self.connections)}")
            return new_client
            
        except Exception as e:
            logging.error(f"创建新连接失败: {e}")
            raise
    
    async def _wait_for_available_connection(self):
        """等待可用连接"""
        max_wait_time = 30  # 最大等待30秒
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            for i, conn_info in enumerate(self.connection_info):
                if conn_info['healthy'] and not conn_info['in_use']:
                    conn_info['in_use'] = True
                    conn_info['use_count'] += 1
                    conn_info['last_used'] = time.time()
                    return self.connections[i]
            
            await asyncio.sleep(1)
        
        raise TimeoutError("等待可用连接超时")
    
    def release_connection(self, client):
        """释放连接"""
        for i, conn in enumerate(self.connections):
            if conn == client:
                if i in self.connection_info:
                    self.connection_info[i]['in_use'] = False
                    logging.debug(f"连接已释放: {i}")
                break
    
    async def _health_check_task(self):
        """连接健康检查任务"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._check_all_connections()
            except Exception as e:
                logging.error(f"健康检查任务出错: {e}")
    
    async def _check_all_connections(self):
        """检查所有连接的健康状态"""
        current_time = time.time()
        
        for i, conn in enumerate(self.connections):
            if i not in self.connection_info:
                continue
            
            conn_info = self.connection_info[i]
            
            # 如果连接正在使用中，跳过检查
            if conn_info['in_use']:
                continue
            
            try:
                # 发送ping测试连接
                await conn.ping()
                conn_info['healthy'] = True
                conn_info['last_health_check'] = current_time
                logging.debug(f"连接 {i} 健康检查通过")
                
            except Exception as e:
                conn_info['healthy'] = False
                logging.warning(f"连接 {i} 健康检查失败: {e}")
                
                # 如果连接不健康，尝试重新初始化
                await self._reinitialize_connection(i, conn)
    
    async def _reinitialize_connection(self, index, client):
        """重新初始化连接"""
        try:
            logging.info(f"尝试重新初始化连接 {index}")
            
            # 停止旧连接
            try:
                await client.stop()
            except:
                pass
            
            # 创建新连接
            new_client = client.copy()
            await new_client.start()
            
            # 更新连接池
            self.connections[index] = new_client
            self.connection_info[index]['healthy'] = True
            self.connection_info[index]['last_health_check'] = time.time()
            
            logging.info(f"连接 {index} 重新初始化成功")
            
        except Exception as e:
            logging.error(f"连接 {index} 重新初始化失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        healthy_connections = sum(1 for info in self.connection_info.values() if info['healthy'])
        in_use_connections = sum(1 for info in self.connection_info.values() if info['in_use'])
        
        return {
            'total_connections': len(self.connections),
            'max_connections': self.max_connections,
            'healthy_connections': healthy_connections,
            'in_use_connections': in_use_connections,
            'available_connections': healthy_connections - in_use_connections,
            'usage_percent': (len(self.connections) / self.max_connections) * 100
        }

class MemoryManager:
    """内存管理器"""
    
    def __init__(self, memory_threshold=80, cleanup_threshold=90):
        self.memory_threshold = memory_threshold  # 内存使用率阈值
        self.cleanup_threshold = cleanup_threshold  # 强制清理阈值
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5分钟检查一次
        
        # 启动内存监控任务
        asyncio.create_task(self._memory_monitor_task())
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """获取内存使用情况"""
        try:
            memory_info = psutil.virtual_memory()
            return {
                'total': memory_info.total / (1024**3),  # GB
                'available': memory_info.available / (1024**3),  # GB
                'used': memory_info.used / (1024**3),  # GB
                'percent': memory_info.percent,
                'free': memory_info.free / (1024**3)  # GB
            }
        except Exception as e:
            logging.error(f"获取内存信息失败: {e}")
            return {}
    
    def get_gc_stats(self) -> Dict[str, Any]:
        """获取垃圾回收统计"""
        try:
            gc_stats = gc.get_stats()
            return {
                'generation_0': gc_stats[0]['collections'],
                'generation_1': gc_stats[1]['collections'],
                'generation_2': gc_stats[2]['collections'],
                'total_collections': sum(stat['collections'] for stat in gc_stats)
            }
        except Exception as e:
            logging.error(f"获取GC统计失败: {e}")
            return {}
    
    async def _memory_monitor_task(self):
        """内存监控任务"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._check_memory_usage()
            except Exception as e:
                logging.error(f"内存监控任务出错: {e}")
    
    async def _check_memory_usage(self):
        """检查内存使用情况"""
        memory_info = self.get_memory_usage()
        if not memory_info:
            return
        
        current_percent = memory_info['percent']
        
        if current_percent >= self.cleanup_threshold:
            # 强制清理
            logging.warning(f"内存使用率过高: {current_percent:.1f}%，执行强制清理")
            await self._force_cleanup()
            
        elif current_percent >= self.memory_threshold:
            # 建议清理
            logging.info(f"内存使用率较高: {current_percent:.1f}%，建议清理")
            await self._suggest_cleanup()
    
    async def _force_cleanup(self):
        """强制清理内存"""
        try:
            # 执行垃圾回收
            collected = gc.collect()
            logging.info(f"强制垃圾回收完成，清理了 {collected} 个对象")
            
            # 清理缓存（如果有的话）
            if hasattr(self, 'cache_manager'):
                self.cache_manager._smart_cleanup()
            
            # 记录清理时间
            self.last_cleanup = time.time()
            
        except Exception as e:
            logging.error(f"强制清理失败: {e}")
    
    async def _suggest_cleanup(self):
        """建议清理内存"""
        try:
            # 执行垃圾回收
            collected = gc.collect()
            if collected > 0:
                logging.info(f"建议清理完成，清理了 {collected} 个对象")
            
            # 记录清理时间
            self.last_cleanup = time.time()
            
        except Exception as e:
            logging.error(f"建议清理失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取内存管理统计信息"""
        memory_info = self.get_memory_usage()
        gc_stats = self.get_gc_stats()
        
        return {
            'memory': memory_info,
            'gc': gc_stats,
            'last_cleanup': self.last_cleanup,
            'cleanup_interval': self.cleanup_interval
        }

class OptimizationManager:
    """优化管理器 - 统一管理所有优化功能"""
    
    def __init__(self):
        self.cache_manager = SmartCache(max_size=5000)
        self.connection_pool = TelegramConnectionPool(max_connections=5)  # 从3改为5
        self.memory_manager = MemoryManager()
        
        logging.info("优化管理器初始化完成")
    
    def get_cache_manager(self) -> SmartCache:
        """获取缓存管理器"""
        return self.cache_manager
    
    def get_connection_pool(self) -> TelegramConnectionPool:
        """获取连接池管理器"""
        return self.connection_pool
    
    def get_memory_manager(self) -> MemoryManager:
        """获取内存管理器"""
        return self.memory_manager
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """获取整体统计信息"""
        return {
            'cache': self.cache_manager.get_stats(),
            'connections': self.connection_pool.get_stats(),
            'memory': self.memory_manager.get_stats(),
            'timestamp': time.time()
        }
    
    async def cleanup_all(self):
        """清理所有资源"""
        try:
            # 清理缓存
            self.cache_manager._smart_cleanup()
            
            # 执行垃圾回收
            collected = gc.collect()
            
            logging.info(f"全局清理完成，清理了 {collected} 个对象")
            
        except Exception as e:
            logging.error(f"全局清理失败: {e}")

# 全局优化管理器实例
optimization_manager = OptimizationManager()

# 便捷访问函数
def get_cache_manager() -> SmartCache:
    return optimization_manager.get_cache_manager()

def get_connection_pool() -> TelegramConnectionPool:
    return optimization_manager.get_connection_pool()

def get_memory_manager() -> MemoryManager:
    return optimization_manager.get_memory_manager()

def get_optimization_stats() -> Dict[str, Any]:
    return optimization_manager.get_overall_stats()

async def cleanup_resources():
    """清理所有资源"""
    await optimization_manager.cleanup_all()
