# ==================== 全新的搬运引擎 ====================
# 专门解决重复消息问题的重新设计版本

import asyncio
import logging
import time
import hashlib
import json
import os
import re
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

@dataclass
class MessageFingerprint:
    """消息指纹 - 用于精确去重"""
    message_id: int
    chat_id: int
    content_hash: str
    media_type: str
    file_id: Optional[str]
    timestamp: float
    
    def __hash__(self):
        """使对象可以被哈希，可以放入set中"""
        return hash((self.content_hash, self.media_type, self.file_id))
    
    def __eq__(self, other):
        """定义相等比较"""
        if not isinstance(other, MessageFingerprint):
            return False
        return (self.content_hash == other.content_hash and 
                self.media_type == other.media_type and 
                self.file_id == other.file_id)
    
    def to_dict(self):
        return {
            'message_id': self.message_id,
            'chat_id': self.chat_id,
            'content_hash': self.content_hash,
            'media_type': self.media_type,
            'file_id': self.file_id,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)

class MessageDeduplicator:
    """高精度消息去重器"""
    
    def __init__(self, max_cache_size: int = 1000):
        self.fingerprints: Dict[str, Set[MessageFingerprint]] = {}
        self.max_cache_size = max_cache_size  # 限制缓存大小，防止内存溢出
        self.cache_stats = {"hits": 0, "misses": 0, "evictions": 0}
        self.load_fingerprints()
    
    def _generate_content_hash(self, message: Message, processed_text: str = None) -> str:
        """生成内容哈希 - 简化版本提高性能"""
        # 快速特征提取
        text_content = processed_text or message.text or message.caption or ""
        
        # 基础特征
        features = [f"id:{message.id}"]
        
        if text_content.strip():
            # 只使用文本长度和前50字符，提高性能
            features.append(f"text_hash:{hash(text_content[:50])}")
            features.append(f"len:{len(text_content)}")
        
        # 增加更多特征以提高去重精度
        if message.forward_from:
            features.append(f"fwd:{message.forward_from.id}")
        if message.reply_to_message:
            features.append(f"reply:{message.reply_to_message.id}")
        
        # 简化的媒体特征
        if message.photo:
            features.append(f"photo:{message.photo.file_id[-10:]}")
        elif message.video:
            features.append(f"video:{message.video.file_id[-10:]}")
        elif message.document:
            features.append(f"doc:{message.document.file_id[-10:]}")
        elif message.animation:
            features.append(f"gif:{message.animation.file_id[-10:]}")
        
        # 快速哈希
        combined = "|".join(features)
        return hashlib.md5(combined.encode('utf-8')).hexdigest()[:16]  # 使用MD5并截取16位，更快
    
    def _get_media_info(self, message: Message) -> Tuple[str, Optional[str]]:
        """获取媒体类型和文件ID"""
        if message.photo:
            return "photo", message.photo.file_id
        elif message.video:
            return "video", message.video.file_id
        elif message.document:
            return "document", message.document.file_id
        elif message.animation:
            return "animation", message.animation.file_id
        elif message.audio:
            return "audio", message.audio.file_id
        elif message.voice:
            return "voice", message.voice.file_id
        elif message.sticker:
            return "sticker", message.sticker.file_id
        elif message.text or message.caption:
            return "text", None
        else:
            return "unknown", None
    
    def create_fingerprint(self, message: Message, processed_text: str = None) -> Optional[MessageFingerprint]:
        """创建消息指纹"""
        # 安全检查
        if not message or not hasattr(message, 'id') or not hasattr(message, 'chat'):
            logging.warning("无法为无效消息创建指纹")
            return None
            
        try:
            content_hash = self._generate_content_hash(message, processed_text)
            media_type, file_id = self._get_media_info(message)
            
            return MessageFingerprint(
                message_id=message.id,
                chat_id=message.chat.id,
                content_hash=content_hash,
                media_type=media_type,
                file_id=file_id,
                timestamp=time.time()
            )
        except Exception as e:
            logging.error(f"创建消息指纹失败: {e}")
            return None
    
    def is_duplicate(self, source_chat_id: int, target_chat_id: int, fingerprint: MessageFingerprint) -> bool:
        """检查是否为重复消息 - 优化版本"""
        key = f"{source_chat_id}_{target_chat_id}"
        
        if key not in self.fingerprints:
            self.fingerprints[key] = set()
            return False
        
        # 快速检查：直接检查指纹对象是否存在（利用__eq__方法）
        if fingerprint in self.fingerprints[key]:
            logging.debug(f"发现重复消息: {fingerprint.content_hash[:8]}...")
            return True
        
        return False
    
    def add_fingerprint(self, source_chat_id: int, target_chat_id: int, fingerprint: MessageFingerprint):
        """添加消息指纹"""
        from collections import OrderedDict
        
        # 建议：使用LRU缓存替代简单的大小限制
        if not hasattr(self, '_lru_cache'):
            self._lru_cache = OrderedDict()
        
        key = f"{source_chat_id}_{target_chat_id}"
        
        if key not in self.fingerprints:
            self.fingerprints[key] = set()
        
        self.fingerprints[key].add(fingerprint)
        
        # LRU缓存管理
        self._lru_cache[key] = fingerprint
        self._lru_cache.move_to_end(key)
        
        if len(self._lru_cache) > self.max_cache_size:
            self._lru_cache.popitem(last=False)
        
        # 限制缓存大小 - 性能优化版本
        if len(self.fingerprints[key]) > self.max_cache_size:
            # 保留最新的50%指纹，清理旧的
            current_size = len(self.fingerprints[key])
            sorted_fps = sorted(self.fingerprints[key], key=lambda x: x.timestamp, reverse=True)
            keep_count = self.max_cache_size // 2
            
            self.fingerprints[key] = set(sorted_fps[:keep_count])
            self.cache_stats["evictions"] += 1
            
            logging.info(f"🧹 清理去重缓存: {key} {current_size} -> {len(self.fingerprints[key])} 条指纹")
            print(f"[性能优化] 缓存清理: {key} 保留最新 {keep_count} 条")
    
    def save_fingerprints(self):
        """保存指纹到文件"""
        try:
            data = {}
            current_time = time.time()
            for key, fps in self.fingerprints.items():
                # 只保存最近12小时的指纹，减少磁盘写入
                recent_fps = [fp for fp in fps if current_time - fp.timestamp < 43200]
                
                # 限制每个频道的保存数量
                if len(recent_fps) > self.max_cache_size:
                    recent_fps.sort(key=lambda x: x.timestamp, reverse=True)
                    recent_fps = recent_fps[:self.max_cache_size]
                
                data[key] = [fp.to_dict() for fp in recent_fps]
            
            with open("message_fingerprints.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logging.info("消息指纹已保存")
        except Exception as e:
            logging.error(f"保存消息指纹失败: {e}")
    
    def load_fingerprints(self):
        """从文件加载指纹"""
        try:
            if os.path.exists("message_fingerprints.json"):
                with open("message_fingerprints.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                current_time = time.time()
                for key, fps_data in data.items():
                    fps = []
                    for fp_data in fps_data:
                        fp = MessageFingerprint.from_dict(fp_data)
                        # 只加载最近12小时的指纹，减少内存占用
                        if current_time - fp.timestamp < 43200:  # 12小时 = 43200秒
                            fps.append(fp)
                        
                        # 限制每个频道的最大指纹数量
                        if len(fps) >= self.max_cache_size:
                            break
                    
                    if fps:
                        # 只保留最新的指纹
                        fps.sort(key=lambda x: x.timestamp, reverse=True)
                        self.fingerprints[key] = set(fps[:self.max_cache_size])
                        logging.info(f"加载指纹缓存: {key} 加载 {len(self.fingerprints[key])} 条")
                
                logging.info("消息指纹已加载")
        except Exception as e:
            logging.error(f"加载消息指纹失败: {e}")

class RobustCloningEngine:
    """鲁棒的搬运引擎"""
    
    def __init__(self, client: Client, source_entity=None, target_entity=None, performance_mode="balanced", flood_wait_manager=None, silent_mode=True):
        self.client = client
        self.source_entity = source_entity
        self.target_entity = target_entity
        self.deduplicator = MessageDeduplicator()
        self.processed_message_ids: Dict[str, Set[int]] = {}  # 记录已处理的消息ID
        self.performance_mode = performance_mode
        self.silent_mode = silent_mode
        self.batch_progress_enabled = not silent_mode
        
        # 🔧 新增：统一的FloodWait管理器
        self.flood_wait_manager = flood_wait_manager
        
        # 根据静默模式和性能模式设置参数
        if silent_mode:
            # 静默模式下使用更大的批次以提高效率
            if performance_mode == "balanced":
                self.batch_size_range = (20, 50)
                self.batch_delay_range = (0.1, 0.3)
            else:
                self.batch_size_range = (10, 30)
                self.batch_delay_range = (0.1, 0.3)
            self.media_group_delay = 0.1
            self.message_delay_media = 0.05
            self.message_delay_text = 0.05
            self.save_frequency = 100
            self.log_frequency = 50
        else:
            # 正常模式保持原有设置
            if performance_mode == "ultra_conservative":
                self.batch_size_range = (20, 40)    # 极小批次大小，确保24小时稳定运行
                self.batch_delay_range = (5.0, 8.0) # 极长延迟，最大化稳定性
                self.media_group_delay = 5.0         # 媒体组超长延迟
                self.message_delay_media = 3.0       # 媒体消息超长延迟
                self.message_delay_text = 2.0        # 文本消息超长延迟
                self.save_frequency = 10             # 最频繁保存
                self.log_frequency = 3               # 最频繁日志
            elif performance_mode == "conservative":
                self.batch_size_range = (50, 100)   # 进一步减少批次大小（从100-200减少到50-100）
                self.batch_delay_range = (2.0, 4.0) # 增加延迟范围（从1.0-2.0增加到2.0-4.0）
                self.media_group_delay = 3.0         # 增加媒体组延迟（从1.0增加到3.0）
                self.message_delay_media = 1.5       # 增加媒体消息延迟（从0.6增加到1.5）
                self.message_delay_text = 1.0        # 增加文本消息延迟（从0.4增加到1.0）
                self.save_frequency = 20             # 更频繁保存（从30减少到20）
                self.log_frequency = 5               # 更频繁日志（从8减少到5）
            elif performance_mode == "balanced":
                self.batch_size_range = (200, 400)  # 平衡性能和内存
                self.batch_delay_range = (0.3, 1.0)
                self.media_group_delay = 0.5
                self.message_delay_text = 0.15
                self.save_frequency = 50
                self.log_frequency = 20
            else:  # aggressive
                self.batch_size_range = (300, 600)  # 限制最大批次，防止内存溢出
                self.batch_delay_range = (0.1, 0.2)
                self.media_group_delay = 0.2
                self.message_delay_media = 0.15
                self.message_delay_text = 0.08
                self.save_frequency = 100
                self.log_frequency = 40
        
        # 支持强制频繁更新模式
        self.force_frequent_updates = False
        
        # 🔧 新增：按钮和小尾巴频率计数器
        self.button_counter = 0
        self.tail_counter = 0
    
    def _load_processed_ids(self, task_key: str):
        """加载已处理的消息ID列表"""
        filename = f"processed_ids_{task_key}.json"
        try:
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    data = json.load(f)
                    self.processed_message_ids[task_key] = set(data)
                logging.info(f"加载已处理消息ID: {len(self.processed_message_ids[task_key])} 条")
        except Exception as e:
            logging.error(f"加载已处理消息ID失败: {e}")
            self.processed_message_ids[task_key] = set()
    
    def _save_processed_ids(self, task_key: str):
        """保存已处理的消息ID列表"""
        filename = f"processed_ids_{task_key}.json"
        try:
            if task_key in self.processed_message_ids:
                data = list(self.processed_message_ids[task_key])
                with open(filename, "w") as f:
                    json.dump(data, f)
        except Exception as e:
            logging.error(f"保存已处理消息ID失败: {e}")
    
    def _is_message_processed(self, task_key: str, message_id: int) -> bool:
        """检查消息是否已被处理"""
        return message_id in self.processed_message_ids.get(task_key, set())
    
    def _mark_message_processed(self, task_key: str, message_id: int):
        """标记消息为已处理"""
        if task_key not in self.processed_message_ids:
            self.processed_message_ids[task_key] = set()
        self.processed_message_ids[task_key].add(message_id)
    
    async def clone_messages_robust(
        self,
        source_chat_id: str,
        target_chat_id: str,
        start_id: int,
        end_id: int,
        config: Dict[str, Any],
        progress_callback: Optional[callable] = None,
        task_id: str = None,
        cancellation_check: callable = None,
        restore_progress: Dict = None
    ) -> Dict[str, Any]:
        """鲁棒的消息搬运函数"""
        
        # 应用配置中的强制频繁更新设置
        if config.get("force_frequent_updates"):
            self.force_frequent_updates = True
            logging.info("启用强制频繁更新模式，进度回调频率提升")
        
        # 添加调试信息
        if progress_callback:
            logging.info(f"🔍 进度回调已设置，任务ID: {task_id}")
        else:
            logging.warning(f"⚠️ 进度回调未设置，任务ID: {task_id}")
        
        task_key = f"{source_chat_id}_{target_chat_id}_{start_id}_{end_id}"
        self._load_processed_ids(task_key)
        
        stats = {
            "total_processed": 0,
            "successfully_cloned": 0,
            "duplicates_skipped": 0,
            "errors": 0,
            "already_processed": 0,
            "invalid_messages": 0,
            "filtered_messages": 0,
            "requested_range": end_id - start_id + 1,
            "current_offset_id": start_id  # 添加当前处理的消息ID
        }
        
        # 如果是恢复模式，继承之前的进度
        if restore_progress:
            for key in stats:
                if key in restore_progress:
                    stats[key] = restore_progress[key]
            logging.info(f"恢复模式: 继承进度 - 已搬运 {stats['successfully_cloned']}, 已处理 {stats['total_processed']}")
        
        logging.info(f"开始鲁棒搬运: {source_chat_id} -> {target_chat_id}, 范围: {start_id}-{end_id}")
        
        try:
            # 使用性能模式配置的批量大小
            task_hash = hash(task_id) if task_id else 0
            min_batch, max_batch = self.batch_size_range
            batch_size = min_batch + (task_hash % (max_batch - min_batch + 1))
            current_id = start_id
            
            while current_id <= end_id:
                # 检查是否被取消（提高检查频率）
                if cancellation_check and cancellation_check():
                    logging.info(f"搬运任务 {task_id} 被取消，立即退出")
                    # 立即返回当前进度
                    return stats
                
                # 安全检查：确保不会无限循环
                if current_id > end_id + 10000:
                    logging.error(f"❌ 检测到异常ID值: {current_id}, 目标: {end_id}, 可能存在无限循环")
                    break
                    
                batch_end = min(current_id + batch_size - 1, end_id)
                message_ids = list(range(current_id, batch_end + 1))
                
                # 更新当前处理的ID
                stats["current_offset_id"] = current_id
                
                # 调试日志：显示当前处理进度
                if current_id % 100 == 0 or current_id == start_id or current_id == end_id:
                    progress = ((current_id - start_id) / (end_id - start_id + 1)) * 100
                    logging.info(f"🔄 处理进度: {progress:.1f}% | 当前ID: {current_id} | 目标ID: {end_id}")
                
                try:
                    # 使用性能模式配置的延迟
                    if task_id:
                        min_delay, max_delay = self.batch_delay_range
                        delay = min_delay + (hash(task_id) % int((max_delay - min_delay) * 10)) / 10
                        await asyncio.sleep(delay)
                    
                    # 获取一批消息
                    messages = await self.client.get_messages(source_chat_id, message_ids)
                    if not isinstance(messages, list):
                        messages = [messages]
                    
                    # 过滤掉无效消息
                    valid_messages = [msg for msg in messages if msg is not None]
                    invalid_count = len(messages) - len(valid_messages)
                    if invalid_count > 0:
                        stats["invalid_messages"] += invalid_count
                        logging.debug(f"过滤了 {invalid_count} 个无效消息")
                    
                    # 检查是否整个批次都是无效消息
                    if not valid_messages:
                        logging.warning(f"⚠️ 批次 {current_id}-{batch_end} 全部无效，可能存在ID跳跃")
                        
                        # 检查是否已经超过范围末尾
                        if current_id > end_id:
                            # 如果已经超过末尾，任务完成
                            logging.info(f"已超过范围末尾 {end_id}，任务完成")
                            break
                        else:
                            # 继续处理下一个批次
                            current_id = batch_end + 1
                            continue
                    
                    # 媒体组聚合处理
                    media_groups = {}  # {media_group_id: [messages]}
                    standalone_messages = []  # 单独的消息
                    
                    # 分类消息：媒体组 vs 单独消息
                    for message in valid_messages:
                        if hasattr(message, 'media_group_id') and message.media_group_id:
                            if message.media_group_id not in media_groups:
                                media_groups[message.media_group_id] = []
                            media_groups[message.media_group_id].append(message)
                        else:
                            standalone_messages.append(message)
                    
                    # 处理媒体组
                    for media_group_id, group_messages in media_groups.items():
                        await self._process_media_group(
                            group_messages, target_chat_id, config, stats, task_key
                        )
                        
                        # 媒体组处理完成后立即触发进度回调
                        if progress_callback:
                            try:
                                logging.debug(f"🔍 媒体组进度回调: 触发进度回调 (处理:{stats['total_processed']}, 成功:{stats['successfully_cloned']})")
                                await progress_callback(stats)
                            except Exception as e:
                                logging.debug(f"媒体组进度回调失败: {e}")
                        else:
                            logging.warning(f"⚠️ 媒体组处理完成但进度回调未设置")
                        
                        # 使用性能模式配置的媒体组延迟
                        await asyncio.sleep(self.media_group_delay)
                    
                    # 处理单独消息 - 使用批量处理
                    if standalone_messages:
                        # 将消息分成小批次处理
                        batch_size = 10  # 每批处理10条消息
                        for i in range(0, len(standalone_messages), batch_size):
                            batch = standalone_messages[i:i + batch_size]
                            
                            # 检查取消状态
                            if cancellation_check and cancellation_check():
                                logging.info(f"搬运任务 {task_id} 在批量处理中被取消")
                                return stats
                            
                            # 批量处理这一批消息
                            await self._process_messages_batch(
                                batch, target_chat_id, config, stats, task_key
                            )
                            
                            # 批次间进度回调
                            if progress_callback:
                                try:
                                    await progress_callback(stats)
                                except Exception as e:
                                    logging.debug(f"批量处理进度回调失败: {e}")
                            
                            # 批次间短暂延迟
                            await asyncio.sleep(0.05)
                
                except Exception as e:
                    logging.error(f"获取消息批次失败 {current_id}-{batch_end}: {e}")
                    stats["errors"] += batch_size
                
                # 更新ID - 修复ID跳跃问题
                if valid_messages:
                    # 如果有有效消息，使用最后一条消息的ID + 1
                    last_message_id = max(msg.id for msg in valid_messages if msg and hasattr(msg, 'id') and msg.id is not None)
                    current_id = last_message_id + 1
                    
                    # 检查是否出现ID跳跃
                    expected_next_id = batch_end + 1
                    if current_id > expected_next_id + 100:  # 如果跳跃超过100个ID
                        logging.warning(f"⚠️ 检测到ID跳跃！当前ID: {current_id}, 预期ID: {expected_next_id}, 跳跃: {current_id - expected_next_id}")
                        
                        # 如果跳跃过大，尝试跳回到合理范围
                        if current_id > end_id + 1000:
                            logging.warning(f"⚠️ ID跳跃过大，尝试跳回到合理范围")
                            current_id = min(current_id, end_id + 100)
                else:
                    # 如果没有有效消息，正常递增
                    current_id = batch_end + 1
                
                # 使用性能模式配置的保存频率
                if stats["total_processed"] % self.save_frequency == 0:
                    self._save_processed_ids(task_key)
                    self.deduplicator.save_fingerprints()
        
        finally:
            # 最终保存
            self._save_processed_ids(task_key)
            self.deduplicator.save_fingerprints()
        
        # 强制范围完整性检查 - 确保任务处理到真正的end_id
        if stats["current_offset_id"] < end_id:
            logging.warning(f"⚠️ 任务提前结束！当前ID: {stats['current_offset_id']}, 目标ID: {end_id}")
            logging.warning(f"⚠️ 尝试强制处理剩余范围: {stats['current_offset_id'] + 1} - {end_id}")
            
            try:
                # 强制处理剩余范围
                remaining_start = stats["current_offset_id"] + 1
                remaining_end = end_id
                
                if remaining_start <= remaining_end:
                    logging.info(f"🔄 强制处理剩余范围: {remaining_start} - {remaining_end}")
                    
                    # 获取剩余范围的消息
                    remaining_messages = await self.client.get_messages(
                        source_chat_id, 
                        list(range(remaining_start, remaining_end + 1))
                    )
                    
                    if remaining_messages:
                        valid_remaining = [msg for msg in remaining_messages if msg is not None]
                        if valid_remaining:
                            logging.info(f"✅ 找到剩余范围的有效消息: {len(valid_remaining)} 条")
                            
                            # 处理剩余消息
                            for message in valid_remaining:
                                if cancellation_check and cancellation_check():
                                    logging.info(f"强制处理过程中被取消")
                                    break
                                
                                # 检查是否已处理过
                                if self._is_message_processed(task_key, message.id):
                                    stats["already_processed"] += 1
                                    continue
                                
                                # 检查是否应该被过滤
                                if self._should_filter_message(message, config):
                                    stats["filtered_messages"] += 1
                                    continue
                                
                                stats["total_processed"] += 1
                                
                                try:
                                    # 处理消息内容
                                    processed_text, reply_markup = self._process_message_content(message, config)
                                    
                                    # 创建消息指纹
                                    fingerprint = self.deduplicator.create_fingerprint(message, processed_text)
                                    if not fingerprint:
                                        stats["errors"] += 1
                                        continue
                                    
                                    # 检查重复
                                    if self.deduplicator.is_duplicate(message.chat.id, target_chat_id, fingerprint):
                                        stats["duplicates_skipped"] += 1
                                        self._mark_message_processed(task_key, message.id)
                                        continue
                                    
                                    # 发送消息
                                    success = await self._send_message_safe(
                                        message, target_chat_id, processed_text, reply_markup
                                    )
                                    
                                    if success:
                                        self._mark_message_processed(task_key, message.id)
                                        self.deduplicator.add_fingerprint(message.chat.id, target_chat_id, fingerprint)
                                        stats["successfully_cloned"] += 1
                                    else:
                                        stats["errors"] += 1
                                        
                                except Exception as e:
                                    logging.error(f"强制处理消息 {message.id} 失败: {e}")
                                    stats["errors"] += 1
                            
                            # 更新最终ID
                            if valid_remaining:
                                final_id = max(msg.id for msg in valid_remaining if msg and hasattr(msg, 'id') and msg.id is not None)
                                stats["current_offset_id"] = final_id
                                logging.info(f"✅ 强制处理完成，最终ID: {final_id}")
                        else:
                            logging.info(f"ℹ️ 剩余范围 {remaining_start}-{remaining_end} 没有有效消息")
                    else:
                        logging.info(f"ℹ️ 剩余范围 {remaining_start}-{remaining_end} 无法获取消息")
                        
            except Exception as e:
                logging.warning(f"⚠️ 强制处理剩余范围失败: {e}")
        
        # 范围完整性检查
        actual_range_covered = stats["current_offset_id"] - start_id + 1
        requested_range = end_id - start_id + 1
        
        if actual_range_covered < requested_range:
            logging.warning(f"⚠️ 范围完整性检查: 请求范围 {start_id}-{end_id} ({requested_range} 条), 实际覆盖到 {stats['current_offset_id']} ({actual_range_covered} 条)")
            logging.warning(f"⚠️ 可能存在ID跳跃或消息缺失，建议检查源频道状态")
        else:
            logging.info(f"✅ 范围完整性检查通过: 完整处理了 {start_id}-{end_id} 范围")
        
        # 输出详细统计
        success_rate = 0
        if stats["total_processed"] > 0:
            success_rate = (stats["successfully_cloned"] / stats["total_processed"]) * 100
        
        # 计算跳过的消息
        total_skipped = stats["invalid_messages"] + stats["duplicates_skipped"] + stats["already_processed"]
        
        logging.info("=" * 50)
        logging.info("🎯 老湿姬2.0 搬运完成统计:")
        logging.info(f"   📊 请求范围: {stats['requested_range']} 条")
        logging.info(f"   🔍 实际检查: {stats['total_processed']} 条")
        logging.info(f"   ✅ 成功搬运: {stats['successfully_cloned']} 条")
        logging.info(f"   ⏭️ 跳过消息: {total_skipped} 条")
        logging.info(f"      🔄 重复: {stats['duplicates_skipped']} 条")
        logging.info(f"      📋 已处理: {stats['already_processed']} 条")
        logging.info(f"      ❌ 无效: {stats['invalid_messages']} 条")
        logging.info(f"   ❌ 处理失败: {stats['errors']} 条")
        logging.info(f"   📈 成功率: {success_rate:.1f}%")
        logging.info(f"   🎯 范围覆盖: {start_id}-{stats['current_offset_id']} ({actual_range_covered} 条)")
        logging.info("=" * 50)
        
        return stats
    
    def _should_filter_message(self, message: Message, config: Dict[str, Any]) -> bool:
        """检查消息是否应该被过滤 - 从主程序移植"""
        # 关键字过滤
        filter_keywords = config.get("filter_keywords", [])
        text_to_check = ""
        if message.caption:
            text_to_check += message.caption.lower()
        if message.text:
            text_to_check += message.text.lower()
        if any(keyword.lower() in text_to_check for keyword in filter_keywords):
            logging.debug(f"消息 {message.id} 被关键字过滤: {filter_keywords}")
            return True

        # 过滤带按钮的消息（支持策略）
        filter_buttons_enabled = config.get("filter_buttons")
        filter_buttons_mode = config.get("filter_buttons_mode", "drop")  # drop | strip | whitelist
        if filter_buttons_enabled and getattr(message, "reply_markup", None):
            if filter_buttons_mode == "drop":
                logging.debug(f"消息 {message.id} 被按钮过滤")
                return True

        # 文件类型过滤
        filter_extensions = config.get("file_filter_extensions", [])
        if message.document and filter_extensions:
            filename = getattr(message.document, 'file_name', '')
            if filename and '.' in filename:
                ext = filename.lower().rsplit('.', 1)[1]
                if ext in filter_extensions:
                    logging.debug(f"消息 {message.id} 被文件类型过滤: {ext}")
                    return True

        # 媒体类型过滤
        if message.photo and config.get("filter_photo"):
            logging.debug(f"消息 {message.id} 被图片过滤")
            return True
        if message.video and config.get("filter_video"):
            logging.debug(f"消息 {message.id} 被视频过滤")
            return True

        return False
    
    def _process_message_content(self, message: Message, config: Dict[str, Any]) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
        """处理消息内容 - 使用完整的文本处理逻辑"""
        # 避免循环导入，直接在这里实现完整的处理逻辑
        try:
            # 获取原始文本
            text = message.text or message.caption or ""
            
            # 调用完整的文本处理功能
            processed_text, reply_markup = self._advanced_process_content(text, config)
            return processed_text, reply_markup
            
        except Exception as e:
            logging.error(f"处理消息内容时出错: {e}")
            return self._simple_process_content(message, config)
    
    def _simple_process_content(self, message: Message, config: Dict[str, Any]) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
        """简化的消息内容处理"""
        text = message.text or message.caption or ""
        
        # 基础文本处理
        if config.get("remove_links", False):
            import re
            # 修复：使用正确的正则表达式
            text = re.sub(r'https?://[^\s/$.?#].[^\s]*', '', text, flags=re.MULTILINE)
        
        # 添加尾巴文本（简化版本）
        tail_text = config.get("tail_text", "")
        if tail_text:
            if not text.strip():
                # 如果原始文本为空，直接使用小尾巴文本
                text = tail_text
            else:
                # 如果原始文本不为空，添加到末尾
                text = f"{text}\n\n{tail_text}"
        
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
        
        return text.strip(), reply_markup
    
    def _advanced_process_content(self, text: str, config: Dict[str, Any]) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
        """完整的文本处理逻辑（从主程序复制）"""
        import re
        from urllib.parse import urlparse
        
        # 文本处理
        processed_text = text
        
        # 移除链接
        if config.get("remove_links", False):
            # 修复：使用正确的正则表达式
            processed_text = re.sub(r'https?://[^\s/$.?#].[^\s]*', '', processed_text, flags=re.MULTILINE)
        
        # 移除用户名
        if config.get("remove_usernames", False):
            processed_text = re.sub(r'@\w+', '', processed_text)
        
        # 移除井号标签
        if config.get("remove_hashtags", False):
            processed_text = re.sub(r'#\w+', '', processed_text)
        
        # 替换词汇 - 支持两种配置名称
        replacements = config.get("replacements", {}) or config.get("replacement_words", {})
        for old_word, new_word in replacements.items():
            processed_text = processed_text.replace(old_word, new_word)
        
        # 添加尾巴文本
        tail_text = config.get("tail_text", "")
        tail_position = config.get("tail_position", "end")
        
        if tail_text and self._should_add_tail_text(config):
            if not processed_text.strip():
                # 如果原始文本为空，直接使用小尾巴文本
                processed_text = tail_text
            else:
                # 如果原始文本不为空，按位置添加小尾巴
                if tail_position == "start":
                    processed_text = f"{tail_text}\n\n{processed_text}"
                else:  # end
                    processed_text = f"{processed_text}\n\n{tail_text}"
        
        # 添加自定义按钮
        reply_markup = None
        if self._should_add_buttons(config):
            custom_buttons = config.get("buttons", [])
            if custom_buttons:
                button_rows = []
                for button_config in custom_buttons:
                    text_btn = button_config.get("text", "")
                    url_btn = button_config.get("url", "")
                    if text_btn and url_btn:
                        # 处理URL格式
                        url_btn = self._normalize_button_url(url_btn)
                        if url_btn:
                            button_rows.append([InlineKeyboardButton(text_btn, url=url_btn)])
                
                if button_rows:
                    reply_markup = InlineKeyboardMarkup(button_rows)
        
        return processed_text.strip(), reply_markup
    
    def _should_add_tail_text(self, config: Dict[str, Any]) -> bool:
        """检查是否应该添加尾巴文本"""
        tail_frequency = config.get("tail_frequency", {})
        mode = tail_frequency.get("mode", "always")
        
        if mode == "never":
            return False
        elif mode == "always":
            return True
        elif mode == "interval":
            # 🔧 修复：实现正确的间隔逻辑
            interval = tail_frequency.get("interval", 5)
            self.tail_counter += 1
            
            if self.tail_counter >= interval:
                self.tail_counter = 0  # 重置计数器
                return True
            return False
        elif mode == "probability":
            import random
            probability = tail_frequency.get("probability", 50)
            return random.randint(1, 100) <= probability
        
        return True
    
    def _should_add_buttons(self, config: Dict[str, Any]) -> bool:
        """检查是否应该添加按钮"""
        button_frequency = config.get("button_frequency", {})
        mode = button_frequency.get("mode", "always")
        
        if mode == "never":
            return False
        elif mode == "always":
            return True
        elif mode == "interval":
            # 🔧 修复：实现正确的间隔逻辑
            interval = button_frequency.get("interval", 5)
            self.button_counter += 1
            
            if self.button_counter >= interval:
                self.button_counter = 0  # 重置计数器
                return True
            return False
        elif mode == "probability":
            import random
            probability = button_frequency.get("probability", 50)
            return random.randint(1, 100) <= probability
        
        return True
    
    def _normalize_button_url(self, url: str) -> str:
        """标准化按钮URL"""
        if not url:
            return ""
        
        # 处理@username格式
        if url.startswith("@"):
            return f"t.me/{url[1:]}"
        
        # 处理纯用户名
        if not url.startswith(("http://", "https://", "t.me/")):
            return f"t.me/{url}"
        
        # 验证URL
        if url.startswith(("http://", "https://", "t.me/")):
            return url
        
        return ""
    
    async def _process_media_group(
        self, 
        group_messages: list, 
        target_chat_id: str, 
        config: dict, 
        stats: dict, 
        task_key: str
    ) -> bool:
        """处理媒体组，集成统一FloodWait管理"""
        try:
            # 🔧 新增：发送前检查全局FloodWait限制
            if self.flood_wait_manager:
                await self.flood_wait_manager.wait_if_needed('send_media_group')
            
            if not group_messages:
                return False
            
            # 检查是否所有消息都已处理过
            all_processed = all(
                self._is_message_processed(task_key, msg.id) for msg in group_messages
            )
            if all_processed:
                stats["already_processed"] += len(group_messages)
                logging.debug(f"跳过已处理的媒体组: {[msg.id for msg in group_messages]}")
                return True
            
            # 按消息ID排序，确保顺序正确
            group_messages.sort(key=lambda x: x.id)
            
            # 准备媒体列表
            media_list = []
            
            # 收集所有消息的文本内容
            all_texts = []
            for message in group_messages:
                text_content = message.text or message.caption or ""
                if text_content.strip():
                    all_texts.append(text_content.strip())
            
            # 合并所有文本并处理（包括小尾巴）
            combined_text = "\n\n".join(all_texts) if all_texts else ""
            processed_caption, reply_markup = self._advanced_process_content(combined_text, config)
            
            for i, message in enumerate(group_messages):
                # 检查是否为服务消息（无法复制）
                if hasattr(message, 'service') and message.service:
                    logging.warning(f"⚠️ 跳过媒体组中的服务消息 {message.id}（无法复制）")
                    continue
                
                # 只在第一个消息添加处理后的文本和按钮
                caption = processed_caption if i == 0 else ""
                
                # 根据消息类型创建媒体对象
                if message.photo:
                    from pyrogram.types import InputMediaPhoto
                    media_list.append(InputMediaPhoto(
                        media=message.photo.file_id,
                        caption=caption
                    ))
                elif message.video:
                    from pyrogram.types import InputMediaVideo
                    media_list.append(InputMediaVideo(
                        media=message.video.file_id,
                        caption=caption
                    ))
                elif message.document:
                    from pyrogram.types import InputMediaDocument
                    media_list.append(InputMediaDocument(
                        media=message.document.file_id,
                        caption=caption
                    ))
                elif message.audio:
                    from pyrogram.types import InputMediaAudio
                    media_list.append(InputMediaAudio(
                        media=message.audio.file_id,
                        caption=caption
                    ))
            
            if not media_list:
                logging.warning(f"媒体组无有效媒体: {[msg.id for msg in group_messages]}")
                stats["errors"] += len(group_messages)
                return False
            
            # 发送媒体组
            results = await self.client.send_media_group(
                chat_id=target_chat_id,
                media=media_list
            )
            
            # 如果有按钮需要添加，直接发送按钮（不添加额外文本）
            if reply_markup and results:
                try:
                    await self.client.send_message(
                        chat_id=target_chat_id,
                        text="",  # 空文本，只显示按钮
                        reply_markup=reply_markup
                    )
                except Exception as button_error:
                    logging.warning(f"发送媒体组按钮失败: {button_error}")
            
            if results:
                # 标记所有消息为已处理
                for message in group_messages:
                    self._mark_message_processed(task_key, message.id)
                    
                    # 创建并添加指纹（防止重复）
                    processed_text, _ = self._process_message_content(message, config)
                    fingerprint = self.deduplicator.create_fingerprint(message, processed_text)
                    if fingerprint:
                        self.deduplicator.add_fingerprint(message.chat.id, target_chat_id, fingerprint)
                
                stats["successfully_cloned"] += len(group_messages)
                stats["total_processed"] += len(group_messages)
                logging.info(f"✅ 成功搬运媒体组: {len(group_messages)} 条消息")
                return True
            else:
                stats["errors"] += len(group_messages)
                stats["total_processed"] += len(group_messages)
                logging.error(f"❌ 媒体组发送失败: {[msg.id for msg in group_messages]}")
                return False
                
        except Exception as e:
            # 特殊处理 CHAT_WRITE_FORBIDDEN 错误
            if "CHAT_WRITE_FORBIDDEN" in str(e):
                logging.error(f"❌ 目标频道 {target_chat_id} 权限不足，无法发送消息")
                # 记录权限错误，避免重复尝试
                if not hasattr(self, '_permission_errors'):
                    self._permission_errors = set()
                self._permission_errors.add(target_chat_id)
                stats["errors"] += len(group_messages)
                stats["total_processed"] += len(group_messages)
                return False
            
            # 🔧 优化：统一的FloodWait处理
            if "FLOOD_WAIT" in str(e):
                import re
                wait_match = re.search(r'wait of (\d+) seconds', str(e))
                if wait_match:
                    wait_time = int(wait_match.group(1))
                    
                    # 🔧 新增：使用统一的FloodWait管理器
                    if self.flood_wait_manager:
                        # 设置FloodWait限制
                        self.flood_wait_manager.set_flood_wait('send_media_group', wait_time)
                        
                        # 检查是否应该重试
                        if wait_time <= 60:
                            logging.warning(f"⏳ 媒体组遇到FloodWait，通过统一管理器等待 {wait_time} 秒")
                            
                            # 使用统一管理器的等待机制
                            await self.flood_wait_manager.wait_if_needed('send_media_group')
                            
                            # 重试一次
                            try:
                                results = await self.client.send_media_group(
                                    chat_id=target_chat_id,
                                    media=media_list
                                )
                                
                                # 如果有按钮需要添加，直接发送按钮（不添加额外文本）
                                if reply_markup and results:
                                    try:
                                        await self.client.send_message(
                                            chat_id=target_chat_id,
                                            text="",  # 空文本，只显示按钮
                                            reply_markup=reply_markup
                                        )
                                    except Exception as button_error:
                                        logging.warning(f"发送媒体组按钮失败(统一管理器重试): {button_error}")
                                
                                if results:
                                    for message in group_messages:
                                        self._mark_message_processed(task_key, message.id)
                                    stats["successfully_cloned"] += len(group_messages)
                                    stats["total_processed"] += len(group_messages)
                                    logging.info(f"✅ 媒体组通过统一管理器重试成功: {len(group_messages)} 条消息")
                                    return True
                            except Exception as retry_e:
                                logging.error(f"❌ 媒体组统一管理器重试失败: {retry_e}")
                        else:
                            logging.warning(f"⚠️ FloodWait时间过长({wait_time}秒)，跳过媒体组")
                    else:
                        # 兼容模式：如果没有FloodWaitManager，使用原有逻辑
                        if wait_time <= 60:
                            logging.warning(f"⏳ 媒体组遇到FloodWait，需要等待 {wait_time} 秒（兼容模式）")
                            
                            # 智能等待策略：等待 Telegram 要求的时间
                            try:
                                logging.info(f"⏳ 等待 {wait_time} 秒后重试...")
                                await asyncio.sleep(wait_time)
                                
                                # 重试一次
                                results = await self.client.send_media_group(
                                    chat_id=target_chat_id,
                                    media=media_list
                                )
                                
                                # 如果有按钮需要添加，直接发送按钮（不添加额外文本）
                                if reply_markup and results:
                                    try:
                                        await self.client.send_message(
                                            chat_id=target_chat_id,
                                            text="",  # 空文本，只显示按钮
                                            reply_markup=reply_markup
                                        )
                                    except Exception as button_error:
                                        logging.warning(f"发送媒体组按钮失败(重试): {button_error}")
                                
                                if results:
                                    for message in group_messages:
                                        self._mark_message_processed(task_key, message.id)
                                    stats["successfully_cloned"] += len(group_messages)
                                    stats["total_processed"] += len(group_messages)
                                    logging.info(f"✅ 媒体组重试成功: {len(group_messages)} 条消息")
                                    return True
                            except Exception as retry_e:
                                logging.error(f"❌ 媒体组重试失败: {retry_e}")
                        else:
                            logging.error(f"❌ 媒体组流量限制时间过长 ({wait_time}秒)，跳过")
                else:
                    logging.error(f"❌ 媒体组FLOOD_WAIT格式解析失败: {e}")
            else:
                logging.error(f"❌ 处理媒体组失败: {e}")
            
            stats["errors"] += len(group_messages)
            stats["total_processed"] += len(group_messages)
            return False

    async def _send_message_safe(
        self, 
        original_message: Message, 
        target_chat_id: str, 
        processed_text: str, 
        reply_markup: Optional[InlineKeyboardMarkup]
    ) -> bool:
        """安全发送消息，集成统一的FloodWait管理"""
        try:
            # 检查是否为服务消息（无法复制）
            if hasattr(original_message, 'service') and original_message.service:
                logging.warning(f"⚠️ 跳过服务消息 {original_message.id}（无法复制）")
                return False
            
            # 🔧 新增：发送前检查全局FloodWait限制
            if self.flood_wait_manager:
                await self.flood_wait_manager.wait_if_needed('send_message')
            
            # 判断消息类型
            is_text_only = (original_message.text and not (
                original_message.photo or original_message.video or 
                original_message.document or original_message.animation or 
                original_message.audio or original_message.voice or original_message.sticker
            ))
            
            logging.debug(f"准备发送消息 {original_message.id}: is_text_only={is_text_only}")
            
            if is_text_only:
                result = await self.client.send_message(
                    chat_id=target_chat_id,
                    text=processed_text or "（空消息）",
                    reply_markup=reply_markup
                )
                logging.debug(f"文本消息发送结果: {result.id if result else 'None'}")
            else:
                result = await self.client.copy_message(
                    chat_id=target_chat_id,
                    from_chat_id=original_message.chat.id,
                    message_id=original_message.id,
                    caption=processed_text,
                    reply_markup=reply_markup
                )
                logging.debug(f"媒体消息复制结果: {result.id if result else 'None'}")
            
            # 检查发送结果
            if result and hasattr(result, 'id'):
                logging.debug(f"✅ 消息 {original_message.id} 成功发送到 {target_chat_id}")
                return True
            else:
                logging.warning(f"❌ 消息 {original_message.id} 发送返回空结果")
                return False
            
        except Exception as e:
            # 特殊处理 CHAT_WRITE_FORBIDDEN 错误
            if "CHAT_WRITE_FORBIDDEN" in str(e):
                logging.error(f"❌ 目标频道 {target_chat_id} 权限不足，无法发送消息")
                # 记录权限错误，避免重复尝试
                if not hasattr(self, '_permission_errors'):
                    self._permission_errors = set()
                self._permission_errors.add(target_chat_id)
                return False
            
            # 🔧 优化：统一的FloodWait处理
            if "FLOOD_WAIT" in str(e):
                import re
                # 提取等待时间
                wait_match = re.search(r'wait of (\d+) seconds', str(e))
                if wait_match:
                    wait_time = int(wait_match.group(1))
                    
                    # 🔧 新增：使用统一的FloodWait管理器
                    if self.flood_wait_manager:
                        # 设置FloodWait限制
                        self.flood_wait_manager.set_flood_wait('send_message', wait_time)
                        
                        # 检查是否应该重试
                        if wait_time <= 60:  # 与主代码保持一致的60秒限制
                            logging.warning(f"⏳ 消息 {original_message.id} 遇到FloodWait，通过统一管理器等待 {wait_time} 秒")
                            
                            # 使用统一管理器的等待机制
                            await self.flood_wait_manager.wait_if_needed('send_message')
                            
                            # 重试一次
                            try:
                                if original_message.text and not (
                                    original_message.photo or original_message.video or 
                                    original_message.document or original_message.animation or 
                                    original_message.audio or original_message.voice or original_message.sticker
                                ):
                                    result = await self.client.send_message(
                                        chat_id=target_chat_id,
                                        text=processed_text or "（空消息）",
                                        reply_markup=reply_markup
                                    )
                                else:
                                    result = await self.client.copy_message(
                                        chat_id=target_chat_id,
                                        from_chat_id=original_message.chat.id,
                                        message_id=original_message.id,
                                        caption=processed_text,
                                        reply_markup=reply_markup
                                    )
                                
                                if result and hasattr(result, 'id'):
                                    logging.info(f"✅ 消息 {original_message.id} 通过统一管理器重试成功")
                                    return True
                            except Exception as retry_e:
                                logging.error(f"❌ 消息 {original_message.id} 统一管理器重试失败: {retry_e}")
                        else:
                            logging.warning(f"⚠️ FloodWait时间过长({wait_time}秒)，跳过消息 {original_message.id}")
                    else:
                        # 兼容模式：如果没有FloodWaitManager，使用原有逻辑
                        if wait_time <= 60:
                            logging.warning(f"⏳ 消息 {original_message.id} 遇到FloodWait，需要等待 {wait_time} 秒（兼容模式）")
                            
                            # 智能等待策略：等待 Telegram 要求的时间
                            try:
                                logging.info(f"⏳ 等待 {wait_time} 秒后重试...")
                                await asyncio.sleep(wait_time)
                                
                                # 重试一次
                                if original_message.text and not (
                                    original_message.photo or original_message.video or 
                                    original_message.document or original_message.animation or 
                                    original_message.audio or original_message.voice or original_message.sticker
                                ):
                                    result = await self.client.send_message(
                                        chat_id=target_chat_id,
                                        text=processed_text or "（空消息）",
                                        reply_markup=reply_markup
                                    )
                                else:
                                    result = await self.client.copy_message(
                                        chat_id=target_chat_id,
                                        from_chat_id=original_message.chat.id,
                                        message_id=original_message.id,
                                        caption=processed_text,
                                        reply_markup=reply_markup
                                    )
                                
                                if result and hasattr(result, 'id'):
                                    logging.info(f"✅ 消息 {original_message.id} 重试成功")
                                    return True
                            except Exception as retry_e:
                                logging.error(f"❌ 消息 {original_message.id} 重试失败: {retry_e}")
                        else:
                            logging.error(f"❌ 消息 {original_message.id} 流量限制时间过长 ({wait_time}秒)，跳过")
                else:
                    logging.error(f"❌ 消息 {original_message.id} FLOOD_WAIT 格式解析失败: {e}")
            else:
                logging.error(f"❌ 发送消息 {original_message.id} 失败: {e}")
            return False
    
    async def _process_messages_batch(self, messages: List[Message], target_chat_id: str, config: dict, stats: dict, task_key: str) -> None:
        """批量处理消息，提升处理效率"""
        if not messages:
            return
        
        # 第一步：批量预处理和验证
        valid_messages = []
        for message in messages:
            # 批量有效性检查
            if not hasattr(message, 'id') or message.id is None:
                stats["invalid_messages"] += 1
                continue
            if not hasattr(message, 'chat') or message.chat is None:
                stats["invalid_messages"] += 1
                continue
            
            stats["total_processed"] += 1
            
            # 批量已处理检查
            if self._is_message_processed(task_key, message.id):
                stats["already_processed"] += 1
                continue
            
            # 批量过滤检查
            if self._should_filter_message(message, config):
                stats["filtered_messages"] += 1
                continue
                
            valid_messages.append(message)
        
        # 第二步：批量内容处理
        processed_messages = []
        for message in valid_messages:
            try:
                processed_text, reply_markup = self._process_message_content(message, config)
                
                # 创建消息指纹
                fingerprint = self.deduplicator.create_fingerprint(message, processed_text)
                if not fingerprint:
                    stats["errors"] += 1
                    continue
                
                # 检查重复
                if self.deduplicator.is_duplicate(message.chat.id, target_chat_id, fingerprint):
                    stats["duplicates_skipped"] += 1
                    self._mark_message_processed(task_key, message.id)
                    continue
                
                processed_messages.append({
                    'message': message,
                    'processed_text': processed_text,
                    'reply_markup': reply_markup,
                    'fingerprint': fingerprint
                })
            except Exception as e:
                logging.error(f"❌ 预处理消息 {message.id} 时出错: {e}")
                stats["errors"] += 1
        
        # 第三步：批量发送（使用并发）
        if processed_messages:
            # 创建发送任务
            send_tasks = []
            for item in processed_messages:
                task = self._send_message_batch_item(
                    item['message'], target_chat_id, 
                    item['processed_text'], item['reply_markup'],
                    item['fingerprint'], stats, task_key
                )
                send_tasks.append(task)
            
            # 并发执行发送任务（限制并发数）
            batch_size = min(5, len(send_tasks))  # 最多5个并发
            for i in range(0, len(send_tasks), batch_size):
                batch = send_tasks[i:i + batch_size]
                await asyncio.gather(*batch, return_exceptions=True)
                
                # 批次间短暂延迟，避免过于频繁
                if i + batch_size < len(send_tasks):
                    await asyncio.sleep(0.1)
    
    async def _send_message_batch_item(self, message: Message, target_chat_id: str, 
                                     processed_text: str, reply_markup, fingerprint, 
                                     stats: dict, task_key: str) -> bool:
        """批量发送中的单个消息处理"""
        try:
            success = await self._send_message_safe(
                message, target_chat_id, processed_text, reply_markup
            )
            
            if success:
                self._mark_message_processed(task_key, message.id)
                self.deduplicator.add_fingerprint(message.chat.id, target_chat_id, fingerprint)
                stats["successfully_cloned"] += 1
                logging.debug(f"✅ 批量发送成功: {message.id}")
            else:
                stats["errors"] += 1
                logging.warning(f"❌ 批量发送失败: {message.id}")
            
            return success
        except Exception as e:
            logging.error(f"❌ 批量发送消息 {message.id} 时出错: {e}")
            stats["errors"] += 1
            return False

# 使用示例
async def example_usage():
    """使用示例"""
    from pyrogram import Client
    
    # 初始化客户端
    app = Client("session", api_id=123456, api_hash="your_hash", bot_token="your_token")
    
    # 创建搬运引擎
    engine = RobustCloningEngine(app)
    
    # 配置
    config = {
        "remove_links": False,
        "buttons": [
            {"text": "联系客服", "url": "@support_bot"}
        ]
    }
    
    # 进度回调
    async def progress_callback(stats):
        print(f"进度: 已处理 {stats['total_processed']}, 成功 {stats['successfully_cloned']}")
    
    # 开始搬运
    async with app:
        result = await engine.clone_messages_robust(
            source_chat_id="source_channel",
            target_chat_id="target_channel", 
            start_id=1,
            end_id=100,
            config=config,
            progress_callback=progress_callback
        )
        
        print(f"搬运结果: {result}")
