#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化后的监听功能
集成内存管理和连接池优化
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any
from pyrogram import Client, filters
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo, InlineKeyboardMarkup, InlineKeyboardButton

from optimization_manager import get_cache_manager, get_connection_pool, get_memory_manager

class OptimizedListener:
    """优化后的监听器"""
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.connection_pool = get_connection_pool()
        self.memory_manager = get_memory_manager()
        
        # 媒体组缓存和定时器管理
        self.media_group_cache = {}
        self.media_group_timers = {}  # 存储每个媒体组的定时器
        self.media_group_locks = {}   # 防止并发处理
        
        logging.info("优化监听器初始化完成")
    
    async def _handle_media_group(self, client: Client, message: Message, pair: Dict, cfg: Dict, uid: str):
        """处理媒体组消息 - 优化版本"""
        key = (message.chat.id, message.media_group_id)
        
        # 获取或创建锁
        if key not in self.media_group_locks:
            self.media_group_locks[key] = asyncio.Lock()
        
        async with self.media_group_locks[key]:
            # 初始化缓存
            if key not in self.media_group_cache:
                self.media_group_cache[key] = []
            
            # 添加消息到缓存
            self.media_group_cache[key].append(message)
            
            # 只有第一个消息设置定时器
            if len(self.media_group_cache[key]) == 1:
                # 取消之前的定时器（如果存在）
                if key in self.media_group_timers:
                    self.media_group_timers[key].cancel()
                
                # 创建新的定时器
                timer = asyncio.create_task(self._process_media_group_after_delay(client, key, pair, cfg, uid))
                self.media_group_timers[key] = timer
            
            # 智能检测：如果消息ID不连续，可能媒体组已完整
            elif self._is_media_group_complete(self.media_group_cache[key]):
                # 取消定时器，立即处理
                if key in self.media_group_timers:
                    self.media_group_timers[key].cancel()
                    del self.media_group_timers[key]
                
                await self._process_complete_media_group(client, key, pair, cfg, uid)
    
    def _is_media_group_complete(self, messages: List[Message]) -> bool:
        """检测媒体组是否完整（基于消息ID连续性）"""
        if len(messages) < 2:
            return False
        
        # 按ID排序
        sorted_messages = sorted(messages, key=lambda m: m.id)
        
        # 检查ID是否连续
        for i in range(1, len(sorted_messages)):
            if sorted_messages[i].id - sorted_messages[i-1].id > 1:
                # ID不连续，可能还有消息未到达
                return False
        
        # 如果已有3个或更多消息且ID连续，认为可能完整
        return len(messages) >= 3
    
    async def _process_media_group_after_delay(self, client: Client, key: tuple, pair: Dict, cfg: Dict, uid: str):
        """延迟处理媒体组"""
        try:
            # 等待2.5秒收集更多消息
            await asyncio.sleep(2.5)
            
            # 处理媒体组
            await self._process_complete_media_group(client, key, pair, cfg, uid)
            
        except asyncio.CancelledError:
            # 定时器被取消，说明媒体组已被其他方式处理
            pass
        except Exception as e:
            logging.error(f"延迟处理媒体组失败: {e}")
        finally:
            # 清理定时器记录
            if key in self.media_group_timers:
                del self.media_group_timers[key]
    
    async def _process_complete_media_group(self, client: Client, key: tuple, pair: Dict, cfg: Dict, uid: str):
        """处理完整的媒体组"""
        if key not in self.media_group_cache:
            return
        
        # 获取并清理缓存
        group_messages = sorted(self.media_group_cache.pop(key), key=lambda m: m.id)
        
        # 清理锁
        if key in self.media_group_locks:
            del self.media_group_locks[key]
        
        # 过滤检查
        if any(self._should_filter_message(m, cfg) for m in group_messages):
            logging.info(f"媒体组 {key[1]} 被过滤，跳过")
            return
        
        # 去重检查
        if not await self._check_media_group_dedupe(group_messages[0], pair):
            return
        
        # 构建媒体列表
        media_list, caption, reply_markup = await self._build_media_group(group_messages, cfg)
        
        if media_list:
            logging.info(f"✅ 处理完整媒体组: {len(group_messages)} 条消息 (ID: {key[1]})")
            await self._send_media_group_with_retry(client, pair['target'], media_list, reply_markup, uid)
        else:
            logging.warning(f"⚠️ 媒体组无有效媒体: {len(group_messages)} 条消息 (ID: {key[1]})")
    
    async def process_message(self, client: Client, message: Message, user_configs: Dict, matched_pairs: List):
        """处理监听到的消息"""
        try:
            # 使用连接池获取健康连接
            connection = await self.connection_pool.get_healthy_connection(client)
            
            try:
                # 处理消息
                await self._handle_message(connection, message, user_configs, matched_pairs)
                
            finally:
                # 释放连接
                self.connection_pool.release_connection(connection)
                
        except Exception as e:
            logging.error(f"处理监听消息失败: {e}")
    
    async def _handle_message(self, client: Client, message: Message, user_configs: Dict, matched_pairs: List):
        """处理单条消息"""
        for uid, pair in matched_pairs:
            try:
                # 获取用户配置
                cfg = self._get_effective_config(user_configs, uid, pair)
                if not cfg:
                    continue
                
                # 检查频道组是否启用
                if not pair.get("enabled", True):
                    continue
                
                # 处理媒体组消息
                if message.media_group_id:
                    await self._handle_media_group(client, message, pair, cfg, uid)
                else:
                    await self._handle_single_message(client, message, pair, cfg, uid)
                    
            except Exception as e:
                logging.error(f"处理用户 {uid} 的频道组失败: {e}")
    
    async def _handle_single_message(self, client: Client, message: Message, pair: Dict, cfg: Dict, uid: str):
        """处理单条消息"""
        # 过滤检查
        if self._should_filter_message(message, cfg):
            logging.info(f"消息 {message.id} 被过滤，跳过")
            return
        
        # 去重检查
        if not await self._check_message_dedupe(message, pair, cfg):
            return
        
        # 处理消息内容
        processed_text, reply_markup = self._process_message_content(message, cfg)
        
        # 发送消息
        await self._send_message_with_retry(client, message, pair['target'], processed_text, reply_markup, uid)
    
    def _get_effective_config(self, user_configs: Dict, uid: str, pair: Dict) -> Optional[Dict]:
        """获取有效的用户配置"""
        try:
            user_config = user_configs.get(str(uid), {})
            if not user_config:
                return None
            
            # 检查是否有频道组专用配置
            channel_pairs = user_config.get("channel_pairs", [])
            for cp in channel_pairs:
                if cp.get('source') == pair.get('source') and cp.get('target') == pair.get('target'):
                    # 合并全局配置和专用配置
                    config = user_config.copy()
                    config.update(cp)
                    return config
            
            # 返回全局配置
            return user_config
            
        except Exception as e:
            logging.error(f"获取用户配置失败: {e}")
            return None
    
    def _should_filter_message(self, message: Message, cfg: Dict) -> bool:
        """检查消息是否应该被过滤"""
        try:
            # 新增：评论区搬运控制
            enable_comment_forwarding = cfg.get("enable_comment_forwarding", False)
            
            # 如果关闭评论区搬运，只搬运频道主发布的内容
            if not enable_comment_forwarding:
                # 检查消息是否来自频道主
                # 频道主发布的消息通常没有 from_user 字段，或者 from_user 是频道本身
                if hasattr(message, 'from_user') and message.from_user:
                    # 如果消息有发送者信息，说明可能是评论或回复
                    logging.debug(f"消息 {message.id} 被评论区过滤: 非频道主发布 (from_user: {message.from_user.id})")
                    return True
                else:
                    # 没有 from_user 字段，通常是频道主发布的内容
                    logging.debug(f"消息 {message.id} 通过评论区过滤: 频道主发布")
            
            # 新增：只搬运频道主信息
            if cfg.get("channel_owner_only", False):
                # 检查消息是否来自频道主
                if hasattr(message, 'from_user') and message.from_user:
                    # 如果消息有发送者信息，说明不是频道主发布的
                    logging.debug(f"消息 {message.id} 被频道主过滤: 非频道主发布")
                    return True
            
            # 新增：只搬运媒体内容
            if cfg.get("media_only_mode", False):
                # 检查消息是否包含媒体内容
                has_media = any([
                    message.photo,
                    message.video,
                    message.video_note,
                    message.animation,
                    message.document,
                    message.audio,
                    message.voice,
                    message.sticker
                ])
                
                if not has_media:
                    logging.debug(f"消息 {message.id} 被媒体过滤: 不包含媒体内容")
                    return True
            
            # 关键词过滤
            filter_keywords = cfg.get("filter_keywords", [])
            if filter_keywords:
                text_content = (message.caption or message.text or "").lower()
                if any(keyword.lower() in text_content for keyword in filter_keywords):
                    return True
            
            # 文件类型过滤
            filter_extensions = cfg.get("file_filter_extensions", [])
            if filter_extensions and message.document:
                filename = getattr(message.document, 'file_name', '')
                if filename and '.' in filename:
                    ext = filename.lower().rsplit('.', 1)[1]
                    if ext in filter_extensions:
                        return True
            
            # 媒体类型过滤
            if message.photo and cfg.get("filter_photo"):
                return True
            if message.video and cfg.get("filter_video"):
                return True
            
            # 按钮过滤
            filter_buttons = cfg.get("filter_buttons", False)
            if filter_buttons and getattr(message, "reply_markup", None):
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"过滤检查失败: {e}")
            return False
    
    async def _check_media_group_dedupe(self, message: Message, pair: Dict) -> bool:
        """检查媒体组去重"""
        try:
            cache_key = f"media_group_{message.chat.id}_{pair['target']}"
            dedup_key = f"media_group_{message.media_group_id}"
            
            # 使用智能缓存管理器
            if self.cache_manager.get(dedup_key):
                logging.debug(f"跳过重复媒体组: {message.media_group_id}")
                return False
            
            # 添加到缓存，TTL为1小时
            self.cache_manager.add(dedup_key, True, ttl=3600)
            return True
            
        except Exception as e:
            logging.error(f"媒体组去重检查失败: {e}")
            return True  # 出错时允许通过
    
    async def _check_message_dedupe(self, message: Message, pair: Dict, cfg: Dict) -> bool:
        """检查消息去重"""
        try:
            # 生成去重键
            dedup_key = self._generate_dedupe_key(message, cfg)
            if not dedup_key:
                return True
            
            cache_key = f"message_{message.chat.id}_{pair['target']}"
            
            # 使用智能缓存管理器
            if self.cache_manager.get(dedup_key):
                logging.debug(f"跳过重复消息: {message.id}")
                return False
            
            # 添加到缓存，TTL为1小时
            self.cache_manager.add(dedup_key, True, ttl=3600)
            return True
            
        except Exception as e:
            logging.error(f"消息去重检查失败: {e}")
            return True  # 出错时允许通过
    
    def _generate_dedupe_key(self, message: Message, cfg: Dict) -> Optional[str]:
        """生成去重键"""
        try:
            # 文本消息去重
            if message.text or message.caption:
                text_content = (message.caption or message.text or "").strip()
                if text_content:
                    return f"text_{hash(text_content)}"
            
            # 媒体消息去重
            if message.photo:
                return f"photo_{message.photo.file_id}"
            elif message.video:
                return f"video_{message.video.file_id}"
            elif message.document:
                return f"document_{message.document.file_id}"
            
            return None
            
        except Exception as e:
            logging.error(f"生成去重键失败: {e}")
            return None
    
    async def _build_media_group(self, group_messages: List[Message], cfg: Dict):
        """构建媒体组"""
        try:
            media_list = []
            caption = ""
            reply_markup = None
            
            # 收集文本内容
            full_text_content = ""
            for m in group_messages:
                if m.caption or m.text:
                    text_content = m.caption or m.text
                    if text_content.strip() and text_content not in full_text_content:
                        if full_text_content:
                            full_text_content += "\n\n" + text_content
                        else:
                            full_text_content = text_content
            
            # 处理文本内容
            if full_text_content:
                caption, reply_markup = self._process_message_content_text(full_text_content, cfg)
            
            # 构建媒体列表
            for i, m in enumerate(group_messages):
                if m.photo:
                    media_list.append(InputMediaPhoto(
                        m.photo.file_id, 
                        caption=caption if i == 0 else ""
                    ))
                elif m.video:
                    media_list.append(InputMediaVideo(
                        m.video.file_id, 
                        caption=caption if i == 0 else ""
                    ))
            
            return media_list, caption, reply_markup
            
        except Exception as e:
            logging.error(f"构建媒体组失败: {e}")
            return [], "", None
    
    def _process_message_content(self, message: Message, cfg: Dict):
        """处理消息内容"""
        try:
            text_content = message.caption or message.text or ""
            return self._process_message_content_text(text_content, cfg)
        except Exception as e:
            logging.error(f"处理消息内容失败: {e}")
            return text_content, None
    
    def _process_message_content_text(self, text: str, cfg: Dict):
        """处理文本内容"""
        try:
            import re
            processed_text = text
            
            # 定义各种链接的正则表达式
            http_pattern = r'https?://[^\s/$.?#].[^\s]*'
            magnet_pattern = r'magnet:\?[^\s]*'
            ftp_pattern = r'ftp://[^\s]*'
            telegram_pattern = r't\.me/[^\s]*'
            
            # 移除所有类型链接
            if cfg.get("remove_all_links", False):
                remove_mode = cfg.get("remove_links_mode", "links_only")
                all_links_pattern = f'({http_pattern}|{magnet_pattern}|{ftp_pattern}|{telegram_pattern})'
                
                if remove_mode == "whole_text":
                    if re.search(all_links_pattern, processed_text, flags=re.MULTILINE | re.IGNORECASE):
                        processed_text = ""
                        logging.info(f"🌐 所有链接过滤: 文本包含链接，整个文本被移除")
                else:
                    processed_text = re.sub(all_links_pattern, '', processed_text, flags=re.MULTILINE | re.IGNORECASE)
                    logging.info(f"🌐 所有链接过滤: 移除所有类型链接，保留其他文本")
            else:
                # 单独处理各种链接类型
                if cfg.get("remove_links", False):
                    remove_mode = cfg.get("remove_links_mode", "links_only")
                    if remove_mode == "whole_text":
                        if re.search(http_pattern, processed_text, flags=re.MULTILINE):
                            processed_text = ""
                            logging.info(f"🔗 HTTP链接过滤: 文本包含HTTP链接，整个文本被移除")
                        else:
                            processed_text = re.sub(http_pattern, '', processed_text, flags=re.MULTILINE)
                            logging.info(f"🔗 HTTP链接过滤: 只移除HTTP链接，保留其他文本")
                    
                    if cfg.get("remove_magnet_links", False):
                        remove_mode = cfg.get("remove_links_mode", "links_only")
                        if remove_mode == "whole_text":
                            if re.search(magnet_pattern, processed_text, flags=re.MULTILINE | re.IGNORECASE):
                                processed_text = ""
                                logging.info(f"🧲 磁力链接过滤: 文本包含磁力链接，整个文本被移除")
                            else:
                                processed_text = re.sub(magnet_pattern, '', processed_text, flags=re.MULTILINE | re.IGNORECASE)
                                logging.info(f"🧲 磁力链接过滤: 只移除磁力链接，保留其他文本")
            
            # 移除用户名
            if cfg.get("remove_usernames", False):
                processed_text = re.sub(r'@\w+', '', processed_text)
            
            # 移除井号标签
            if cfg.get("remove_hashtags", False):
                processed_text = re.sub(r'#\w+', '', processed_text)
            
            # 敏感词替换
            replacement_words = cfg.get("replacement_words", {})
            for old_word, new_word in replacement_words.items():
                processed_text = processed_text.replace(old_word, new_word)
            
            # 添加尾巴文字
            tail_text = cfg.get("tail_text", "")
            if tail_text:
                tail_position = cfg.get("tail_position", "end")
                if tail_position == "start":
                    processed_text = tail_text + "\n\n" + processed_text
                else:
                    processed_text = processed_text + "\n\n" + tail_text
            
            # 处理按钮
            reply_markup = self._build_custom_buttons(cfg)
            
            return processed_text.strip(), reply_markup
            
        except Exception as e:
            logging.error(f"处理文本内容失败: {e}")
            return text, None
    
    def _build_custom_buttons(self, cfg: Dict) -> Optional[InlineKeyboardMarkup]:
        """构建自定义按钮"""
        try:
            custom_buttons = cfg.get("buttons", [])
            if not custom_buttons:
                return None
            
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
                return InlineKeyboardMarkup(button_rows)
            
            return None
            
        except Exception as e:
            logging.error(f"构建按钮失败: {e}")
            return None
    
    async def _send_media_group_with_retry(self, client: Client, target: str, media_list: List, reply_markup, uid: str):
        """发送媒体组（带重试）"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await client.send_media_group(chat_id=target, media=media_list)
                
                # 发送按钮（如果需要）
                if reply_markup:
                    await client.send_message(
                        chat_id=target, 
                        text="📋", 
                        reply_markup=reply_markup
                    )
                
                logging.info(f"用户 {uid} 成功发送媒体组到 {target}")
                return
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logging.error(f"发送媒体组最终失败: {e}")
                    raise
                else:
                    retry_delay = 2 ** attempt
                    logging.warning(f"发送媒体组重试 {attempt + 1}/{max_retries}: {e}")
                    await asyncio.sleep(retry_delay)
    
    async def _send_message_with_retry(self, client: Client, message: Message, target: str, text: str, reply_markup, uid: str):
        """发送消息（带重试）"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                is_text_only = (message.text and not (
                    message.photo or message.video or message.document or 
                    message.animation or message.audio or message.voice or message.sticker
                ))
                
                if is_text_only:
                    await client.send_message(
                        chat_id=target,
                        text=text,
                        reply_markup=reply_markup
                    )
                else:
                    await client.copy_message(
                        chat_id=target,
                        from_chat_id=message.chat.id,
                        message_id=message.id,
                        caption=text,
                        reply_markup=reply_markup
                    )
                
                logging.info(f"用户 {uid} 成功发送消息到 {target}")
                return
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logging.error(f"发送消息最终失败: {e}")
                    raise
                else:
                    retry_delay = 2 ** attempt
                    logging.warning(f"发送消息重试 {attempt + 1}/{max_retries}: {e}")
                    await asyncio.sleep(retry_delay)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取监听器统计信息"""
        return {
            'cache': self.cache_manager.get_stats(),
            'connections': self.connection_pool.get_stats(),
            'memory': self.memory_manager.get_stats(),
            'media_group_cache_size': len(self.media_group_cache)
        }

# 全局优化监听器实例
optimized_listener = OptimizedListener()

# 便捷访问函数
def get_optimized_listener() -> OptimizedListener:
    return optimized_listener

def get_listener_stats() -> Dict[str, Any]:
    return optimized_listener.get_stats()
