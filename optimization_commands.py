#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化管理命令
提供查看和管理优化状态的功能
"""

import asyncio
import time
from typing import Dict, Any
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from optimization_manager import get_optimization_stats, cleanup_resources
from optimized_listener import get_listener_stats

async def show_optimization_status(message, user_id):
    """显示优化状态"""
    try:
        # 获取优化统计信息
        stats = get_optimization_stats()
        listener_stats = get_listener_stats()
        
        # 格式化显示
        text = "🚀 **系统优化状态**\n\n"
        
        # 缓存状态
        cache_stats = stats.get('cache', {})
        text += "💾 **智能缓存状态:**\n"
        text += f"• 缓存项数: {cache_stats.get('total_items', 0)} / {cache_stats.get('max_size', 5000)}\n"
        text += f"• 使用率: {cache_stats.get('usage_percent', 0):.1f}%\n"
        text += f"• 过期项: {cache_stats.get('expired_items', 0)} 个\n"
        text += f"• 平均访问: {cache_stats.get('avg_access_count', 0):.1f} 次\n\n"
        
        # 连接池状态
        conn_stats = stats.get('connections', {})
        text += "🔌 **连接池状态:**\n"
        text += f"• 总连接: {conn_stats.get('total_connections', 0)} / {conn_stats.get('max_connections', 3)}\n"
        text += f"• 健康连接: {conn_stats.get('healthy_connections', 0)} 个\n"
        text += f"• 使用中: {conn_stats.get('in_use_connections', 0)} 个\n"
        text += f"• 可用: {conn_stats.get('available_connections', 0)} 个\n"
        text += f"• 使用率: {conn_stats.get('usage_percent', 0):.1f}%\n\n"
        
        # 内存状态
        memory_stats = stats.get('memory', {})
        if memory_stats:
            memory_info = memory_stats.get('memory', {})
            gc_info = memory_stats.get('gc', {})
            
            text += "🧠 **内存管理状态:**\n"
            text += f"• 总内存: {memory_info.get('total', 0):.2f} GB\n"
            text += f"• 已用: {memory_info.get('used', 0):.2f} GB\n"
            text += f"• 可用: {memory_info.get('available', 0):.2f} GB\n"
            text += f"• 使用率: {memory_info.get('percent', 0):.1f}%\n"
            text += f"• 垃圾回收: {gc_info.get('total_collections', 0)} 次\n"
            text += f"• 最后清理: {time.strftime('%H:%M:%S', time.localtime(memory_stats.get('last_cleanup', 0)))}\n\n"
        
        # 监听器状态
        text += "👂 **监听器状态:**\n"
        text += f"• 媒体组缓存: {listener_stats.get('media_group_cache_size', 0)} 个\n\n"
        
        # 性能建议
        text += "💡 **性能建议:**\n"
        
        cache_usage = cache_stats.get('usage_percent', 0)
        if cache_usage > 80:
            text += "⚠️ 缓存使用率较高，建议清理\n"
        elif cache_usage > 60:
            text += "🟡 缓存使用率适中\n"
        else:
            text += "✅ 缓存使用率正常\n"
        
        conn_usage = conn_stats.get('usage_percent', 0)
        if conn_usage > 80:
            text += "⚠️ 连接池使用率较高，可能需要增加连接数\n"
        elif conn_usage > 60:
            text += "🟡 连接池使用率适中\n"
        else:
            text += "✅ 连接池使用率正常\n"
        
        memory_usage = memory_info.get('percent', 0) if memory_info else 0
        if memory_usage > 80:
            text += "🚨 内存使用率过高，建议立即清理\n"
        elif memory_usage > 60:
            text += "⚠️ 内存使用率较高，建议清理\n"
        else:
            text += "✅ 内存使用率正常\n"
        
        # 按钮
        buttons = [
            [InlineKeyboardButton("🧹 清理所有资源", callback_data="optimization_cleanup_all")],
            [InlineKeyboardButton("🔄 刷新状态", callback_data="optimization_refresh")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]
        ]
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        error_text = f"❌ 获取优化状态失败: {e}"
        buttons = [[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]
        await message.edit_text(error_text, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_optimization_callback(callback_query, data):
    """处理优化相关的回调"""
    try:
        if data == "optimization_cleanup_all":
            await callback_query.answer("🧹 正在清理资源...")
            
            # 执行清理
            await cleanup_resources()
            
            # 显示清理完成消息
            await callback_query.message.edit_text(
                "✅ **资源清理完成！**\n\n"
                "已清理:\n"
                "• 过期缓存项\n"
                "• 垃圾回收对象\n"
                "• 无效连接\n\n"
                "系统性能已优化！",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 查看状态", callback_data="optimization_refresh")
                ]])
            )
            
        elif data == "optimization_refresh":
            await callback_query.answer("🔄 刷新中...")
            await show_optimization_status(callback_query.message, callback_query.from_user.id)
            
    except Exception as e:
        await callback_query.answer(f"❌ 操作失败: {e}")

async def show_performance_metrics(message, user_id):
    """显示性能指标"""
    try:
        stats = get_optimization_stats()
        
        text = "📊 **性能指标详情**\n\n"
        
        # 缓存性能
        cache_stats = stats.get('cache', {})
        text += "💾 **缓存性能:**\n"
        text += f"• 命中率: {cache_stats.get('avg_access_count', 0):.1f} 次/项\n"
        text += f"• 清理效率: {cache_stats.get('expired_items', 0)} 个过期项\n"
        text += f"• 内存占用: {cache_stats.get('usage_percent', 0):.1f}%\n\n"
        
        # 连接性能
        conn_stats = stats.get('connections', {})
        text += "🔌 **连接性能:**\n"
        text += f"• 连接利用率: {conn_stats.get('usage_percent', 0):.1f}%\n"
        text += f"• 健康状态: {conn_stats.get('healthy_connections', 0)}/{conn_stats.get('total_connections', 0)}\n"
        text += f"• 可用性: {conn_stats.get('available_connections', 0)} 个\n\n"
        
        # 内存性能
        memory_stats = stats.get('memory', {})
        if memory_stats:
            memory_info = memory_stats.get('memory', {})
            gc_info = memory_stats.get('gc', {})
            
            text += "🧠 **内存性能:**\n"
            text += f"• 内存效率: {memory_info.get('percent', 0):.1f}%\n"
            text += f"• 垃圾回收: {gc_info.get('total_collections', 0)} 次\n"
            text += f"• 代数0: {gc_info.get('generation_0', 0)} 次\n"
            text += f"• 代数1: {gc_info.get('generation_1', 0)} 次\n"
            text += f"• 代数2: {gc_info.get('generation_2', 0)} 次\n\n"
        
        # 性能评估
        text += "🎯 **性能评估:**\n"
        
        # 缓存评分
        cache_score = 100 - cache_stats.get('usage_percent', 0)
        if cache_score >= 80:
            text += "💚 缓存性能: 优秀\n"
        elif cache_score >= 60:
            text += "🟡 缓存性能: 良好\n"
        else:
            text += "🔴 缓存性能: 需要优化\n"
        
        # 连接评分
        conn_score = 100 - conn_stats.get('usage_percent', 0)
        if conn_score >= 80:
            text += "💚 连接性能: 优秀\n"
        elif conn_score >= 60:
            text += "🟡 连接性能: 良好\n"
        else:
            text += "🔴 连接性能: 需要优化\n"
        
        # 内存评分
        memory_score = 100 - memory_info.get('percent', 0) if memory_info else 100
        if memory_score >= 80:
            text += "💚 内存性能: 优秀\n"
        elif memory_score >= 60:
            text += "🟡 内存性能: 良好\n"
        else:
            text += "🔴 内存性能: 需要优化\n"
        
        # 总体评分
        overall_score = (cache_score + conn_score + memory_score) / 3
        if overall_score >= 80:
            text += f"\n🏆 **总体评分: {overall_score:.1f}/100 (优秀)**"
        elif overall_score >= 60:
            text += f"\n🟡 **总体评分: {overall_score:.1f}/100 (良好)**"
        else:
            text += f"\n🔴 **总体评分: {overall_score:.1f}/100 (需要优化)**"
        
        # 按钮
        buttons = [
            [InlineKeyboardButton("🧹 优化系统", callback_data="optimization_cleanup_all")],
            [InlineKeyboardButton("📊 查看状态", callback_data="optimization_status")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]
        ]
        
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        error_text = f"❌ 获取性能指标失败: {e}"
        buttons = [[InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]]
        await message.edit_text(error_text, reply_markup=InlineKeyboardMarkup(buttons))

# 添加到主菜单的函数
def get_optimization_menu_buttons():
    """获取优化管理菜单按钮"""
    return [
        [InlineKeyboardButton("📊 优化状态", callback_data="optimization_status")],
        [InlineKeyboardButton("📈 性能指标", callback_data="performance_metrics")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="show_main_menu")]
    ]

# 回调处理映射
OPTIMIZATION_CALLBACKS = {
    "optimization_status": show_optimization_status,
    "performance_metrics": show_performance_metrics,
    "optimization_cleanup_all": handle_optimization_callback,
    "optimization_refresh": handle_optimization_callback
}
