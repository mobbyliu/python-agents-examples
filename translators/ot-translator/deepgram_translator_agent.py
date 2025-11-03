"""
---
title: Deepgram + Google Translate Real-time Translator
category: translation
tags: [translation, deepgram-stt, google-translate, streaming, debounce]
difficulty: advanced
description: Real-time streaming translation system using Deepgram STT and Google Cloud Translate API
demonstrates:
  - Deepgram STT integration for multi-language speech recognition
  - Google Cloud Translate API for text translation
  - Debounced interim translation to optimize API calls
  - Configurable source and target languages via RPC
  - Real-time translation updates with final corrections
---
"""

from pathlib import Path
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import silero, deepgram
from livekit import rtc
from typing import Optional, AsyncIterable, List, Callable, Dict
from google.cloud import translate_v2 as translate
import sys
import json
import logging
import asyncio
import time
import os
from dataclasses import dataclass

sys.path.append(str(Path(__file__).parent.parent.parent))

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

logger = logging.getLogger("deepgram-translator")
logger.setLevel(logging.INFO)


@dataclass
class PendingSentence:
    """待翻译的句子"""
    sequence: int          # 全局序号
    text: str             # 原文
    timestamp: float      # 接收时间


class AdaptiveBatchCollector:
    """
    自适应批量收集器
    - 批次为空：立即翻译（无额外延迟）
    - 批次有句子：加入批量（利用批量优势）
    """
    
    def __init__(
        self, 
        batch_size: int = 3,
        batch_timeout_ms: float = 500,
        translate_callback: Callable = None
    ):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout_ms / 1000
        self.translate_callback = translate_callback
        
        self.pending_batch: List[PendingSentence] = []
        self.batch_timer: Optional[asyncio.Task] = None
        self.lock = asyncio.Lock()
    
    async def add_sentence(self, sequence: int, text: str):
        """
        添加句子到批次
        
        核心逻辑：
        1. 如果批次为空 → 立即触发翻译
        2. 如果批次不为空 → 加入批次，等待触发
        """
        async with self.lock:
            sentence = PendingSentence(
                sequence=sequence,
                text=text,
                timestamp=time.time()
            )
            
            # 🔑 关键判断：批次是否为空
            is_batch_empty = len(self.pending_batch) == 0
            
            self.pending_batch.append(sentence)
            
            if is_batch_empty:
                # 情况1：批次为空，说明没有积压
                # → 立即翻译，不等待
                logger.info(f"[ADAPTIVE] seq={sequence}, batch empty, immediate translation")
                await self._flush_batch()
            else:
                # 情况2：批次已有句子，说明有积压
                # → 利用批量优势
                logger.info(f"[ADAPTIVE] seq={sequence}, batch has {len(self.pending_batch)} sentences")
                
                if len(self.pending_batch) >= self.batch_size:
                    # 达到批次大小，立即批量翻译
                    logger.info(f"[ADAPTIVE] Batch size reached, flushing")
                    await self._flush_batch()
                else:
                    # 启动定时器，超时后批量翻译
                    if self.batch_timer:
                        self.batch_timer.cancel()
                    self.batch_timer = asyncio.create_task(self._delayed_flush())
    
    async def _delayed_flush(self):
        """延迟触发批量翻译"""
        await asyncio.sleep(self.batch_timeout)
        async with self.lock:
            if self.pending_batch:
                logger.info(f"[ADAPTIVE] Batch timeout, flushing {len(self.pending_batch)} sentences")
                await self._flush_batch()
    
    async def _flush_batch(self):
        """执行批量翻译"""
        if not self.pending_batch:
            return
        
        batch = self.pending_batch
        self.pending_batch = []
        
        # 取消定时器
        if self.batch_timer:
            self.batch_timer.cancel()
            self.batch_timer = None
        
        # 调用翻译回调
        if self.translate_callback:
            await self.translate_callback(batch)


class BatchTranslator:
    """批量翻译器：调用Google Translate批量API"""
    
    def __init__(self, translate_client):
        self.translate_client = translate_client
    
    async def translate_batch(
        self,
        texts: List[str],
        source_language: str,
        target_language: str
    ) -> List[Optional[str]]:
        """
        批量翻译多个文本
        
        Args:
            texts: 文本列表 ["Hello", "How are you", ...]
            
        Returns:
            翻译结果列表 ["你好", "你好吗", ...]
        """
        if not texts:
            return []
        
        if source_language == target_language:
            return texts
        
        try:
            start_time = time.time()
            
            # ✅ 批量调用 Google Translate API
            # API支持传入列表
            results = self.translate_client.translate(
                texts,
                target_language=target_language,
                source_language=source_language
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            # 提取翻译结果
            translations = []
            if isinstance(results, list):
                for result in results:
                    translations.append(result.get('translatedText'))
            else:
                # 单个结果的情况
                translations.append(results.get('translatedText'))
            
            logger.info(
                f"[BATCH] Translated {len(texts)} texts in {elapsed_ms:.0f}ms "
                f"(avg {elapsed_ms/len(texts):.0f}ms per text)"
            )
            
            return translations
            
        except Exception as e:
            logger.error(f"Batch translation error: {e}")
            # 失败时返回None列表
            return [None] * len(texts)


class OrderedDispatcher:
    """
    顺序分发器：确保翻译结果按序号发送到前端
    
    问题场景：
    - 句子1（长文本）：翻译需要800ms
    - 句子2（短文本）：翻译只需200ms
    - 如果句子2先完成，也要等句子1发送后再发送
    """
    
    def __init__(self, send_callback: Callable):
        self.send_callback = send_callback
        self.next_sequence = 0  # 下一个应该发送的序号
        self.pending_results: Dict[int, tuple] = {}  # {sequence: (original, translated)}
        self.lock = asyncio.Lock()
    
    async def add_result(
        self,
        sequence: int,
        original_text: str,
        translated_text: Optional[str]
    ):
        """添加翻译结果"""
        async with self.lock:
            self.pending_results[sequence] = (original_text, translated_text)
            logger.debug(f"[DISPATCHER] Added seq={sequence}, next={self.next_sequence}")
            await self._flush_results()
    
    async def _flush_results(self):
        """按顺序发送所有可发送的结果"""
        while self.next_sequence in self.pending_results:
            original, translated = self.pending_results.pop(self.next_sequence)
            
            logger.info(f"[DISPATCHER] Sending seq={self.next_sequence}")
            
            # 调用回调发送到前端
            await self.send_callback(
                original_text=original,
                translated_text=translated,
                is_final=True
            )
            
            self.next_sequence += 1


class DebouncedTranslator:
    """处理带防抖的翻译请求"""
    
    def __init__(self, debounce_ms: float = 500, enabled: bool = True):
        self.debounce_delay = debounce_ms / 1000
        self.pending_task: Optional[asyncio.Task] = None
        self.translate_client = None
        self.enabled = enabled
        
        # 初始化 Google Cloud Translate 客户端
        try:
            self.translate_client = translate.Client()
            logger.info("Google Cloud Translate client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Translate client: {e}")
            logger.error("Make sure GOOGLE_APPLICATION_CREDENTIALS is set correctly")
    
    def update_debounce_delay(self, debounce_ms: float):
        """更新防抖延迟时间"""
        self.debounce_delay = debounce_ms / 1000
        logger.info(f"Debounce delay updated to {debounce_ms}ms")
    
    def update_enabled(self, enabled: bool):
        """启用或禁用防抖翻译"""
        if self.enabled == enabled:
            return

        self.enabled = enabled

        # 如果关闭防抖，取消任何待处理的任务
        if not enabled and self.pending_task and not self.pending_task.done():
            self.pending_task.cancel()
            self.pending_task = None

        status = "enabled" if enabled else "disabled"
        logger.info(f"Debounced translation {status}")

    async def translate_text(
        self, 
        text: str, 
        source_language: str, 
        target_language: str
    ) -> Optional[str]:
        """调用 Google Cloud Translate API 翻译文本"""
        if not self.translate_client:
            logger.error("Translate client not initialized")
            return None
        
        try:
            # 如果源语言和目标语言相同，不需要翻译
            if source_language == target_language:
                return text
            
            # 记录开始时间
            start_time = time.time()
            
            # 调用 Google Translate API
            result = self.translate_client.translate(
                text,
                target_language=target_language,
                source_language=source_language
            )
            
            # 计算耗时
            elapsed_ms = (time.time() - start_time) * 1000
            
            translated_text = result['translatedText']
            logger.info(
                "Translated (%s -> %s) in %.0fms: %s -> %s",
                source_language,
                target_language,
                elapsed_ms,
                text,
                translated_text,
            )
            return translated_text
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return None
    
    async def translate_debounced(
        self,
        text: str,
        source_language: str,
        target_language: str,
        callback
    ):
        """带防抖的翻译：取消之前的请求，延迟执行新请求"""
        # 禁用防抖时，直接执行翻译
        if not self.enabled:
            if self.pending_task and not self.pending_task.done():
                self.pending_task.cancel()
                self.pending_task = None

            translated = await self.translate_text(text, source_language, target_language)

            if translated:
                await callback(text, source_language, translated, is_final=False)
            return

        # 取消之前的待处理任务
        if self.pending_task and not self.pending_task.done():
            self.pending_task.cancel()

        async def delayed_translate():
            try:
                # 等待防抖延迟
                await asyncio.sleep(self.debounce_delay)
                
                # 执行翻译
                translated = await self.translate_text(text, source_language, target_language)
                
                # 通过回调发送结果
                if translated:
                    await callback(text, source_language, translated, is_final=False)
                    
            except asyncio.CancelledError:
                logger.debug(f"Debounced translation cancelled for: {text[:30]}...")
            except Exception as e:
                logger.error(f"Error in debounced translation: {e}")
        
        # 创建新的待处理任务
        self.pending_task = asyncio.create_task(delayed_translate())
    
    def cancel_pending_interim(self):
        """取消待处理的interim翻译（由final调用）"""
        if self.pending_task and not self.pending_task.done():
            self.pending_task.cancel()
            logger.info("✅ Cancelled pending interim translation (final arrived)")
            return True
        return False


class DeepgramTranslationAgent(Agent):
    def __init__(
        self, 
        ctx: Optional[JobContext] = None,
        source_language: str = "en",
        target_language: str = "zh",
        debounce_ms: float = 500,
        debounce_enabled: bool = True,
        batch_size: int = 3,
        batch_timeout_ms: float = 500
    ):
        # 配置 Deepgram STT
        # 注意：Deepgram 支持的语言代码可能与 Google Translate 不同
        # 需要根据实际情况调整
        super().__init__(
            instructions="You are a real-time translation assistant using Deepgram STT and Google Translate.",
            stt=deepgram.STT(
                language=source_language,  # Deepgram 的语言参数
                interim_results=True,  # 启用 interim results
            ),
            allow_interruptions=False,
            vad=silero.VAD.load(
                min_speech_duration=0.3,  # 增加最小语音持续时间，减少 VAD 触发频率
                min_silence_duration=0.5,  # 增加最小静音持续时间，优化性能
            )
        )
        
        self.ctx = ctx
        self.source_language = source_language
        self.target_language = target_language
        self.debounce_enabled = debounce_enabled
        self.translator = DebouncedTranslator(debounce_ms=debounce_ms, enabled=debounce_enabled)
        
        # 用于跟踪上一次发送的完整文本，以计算增量
        self.last_sent_original = ""
        self.last_sent_translation = ""
        
        # ═══════════════════════════════════════════════
        # 自适应批量翻译组件
        # ═══════════════════════════════════════════════
        
        # 句子序号计数器
        self.sentence_sequence = 0
        
        # 批量翻译器
        self.batch_translator = BatchTranslator(
            translate_client=self.translator.translate_client
        )
        
        # 顺序分发器
        self.dispatcher = OrderedDispatcher(
            send_callback=self._send_to_frontend_final
        )
        
        # 自适应批量收集器
        self.batch_collector = AdaptiveBatchCollector(
            batch_size=batch_size,
            batch_timeout_ms=batch_timeout_ms,
            translate_callback=self._handle_batch_translation
        )
        
        logger.info(
            "DeepgramTranslationAgent initialized: %s -> %s, debounce_ms=%s, debounce_enabled=%s, "
            "batch_size=%s, batch_timeout_ms=%s",
            source_language,
            target_language,
            debounce_ms,
            debounce_enabled,
            batch_size,
            batch_timeout_ms,
        )
    
    def compute_delta(self, prev_text: str, current_text: str) -> str:
        """
        计算两个文本之间的差异（delta）
        使用最长公共前缀方法，返回新增或修改的部分
        """
        if not prev_text:
            return current_text
        
        if not current_text:
            return ""
        
        # 找到最长公共前缀
        common_prefix_len = 0
        min_len = min(len(prev_text), len(current_text))
        
        while common_prefix_len < min_len and prev_text[common_prefix_len] == current_text[common_prefix_len]:
            common_prefix_len += 1
        
        # 返回新增/修改的部分
        delta = current_text[common_prefix_len:]
        return delta
    
    async def update_config(
        self, 
        source_language: Optional[str] = None, 
        target_language: Optional[str] = None
    ):
        """更新翻译配置（语言对）
        
        注意：防抖配置（debounce_ms 和 debounce_enabled）通过后端环境变量控制：
        - TRANSLATION_DEBOUNCE_MS: 防抖延迟（毫秒）
        - TRANSLATION_DEBOUNCE_ENABLED: 是否启用防抖
        """
        if source_language:
            self.source_language = source_language
            logger.info(f"Source language updated to: {source_language}")
        
        if target_language:
            self.target_language = target_language
            logger.info(f"Target language updated to: {target_language}")
    
    async def _handle_batch_translation(self, batch: List[PendingSentence]):
        """处理一批句子的翻译"""
        if not batch:
            return
        
        # 提取文本列表和序号
        texts = [s.text for s in batch]
        sequences = [s.sequence for s in batch]
        
        logger.info(
            f"[BATCH] Translating {len(batch)} sentences: "
            f"seq={sequences}, texts={[t[:20]+'...' for t in texts]}"
        )
        
        # 批量翻译
        translations = await self.batch_translator.translate_batch(
            texts=texts,
            source_language=self.source_language,
            target_language=self.target_language
        )
        
        # 添加到顺序分发器
        for i, sentence in enumerate(batch):
            await self.dispatcher.add_result(
                sequence=sentence.sequence,
                original_text=sentence.text,
                translated_text=translations[i] if i < len(translations) else None
            )
    
    async def _send_to_frontend_final(
        self,
        original_text: str,
        translated_text: Optional[str],
        is_final: bool
    ):
        """发送final结果到前端（内部方法）"""
        await self.send_translation_to_frontend(
            original_text=original_text,
            original_language=self.source_language,
            translated_text=translated_text,
            is_final=is_final
        )
    
    async def send_translation_to_frontend(
        self, 
        original_text: str, 
        original_language: str, 
        translated_text: Optional[str], 
        is_final: bool
    ):
        """
        通过 RPC 发送翻译数据到前端
        同时发送 full_text 和 delta，支持增量渲染和纠错
        """
        if not self.ctx or not self.ctx.room:
            logger.debug("No room context available for RPC")
            return
        
        try:
            # 获取远程参与者（前端客户端）
            remote_participants = list(self.ctx.room.remote_participants.values())
            if not remote_participants:
                logger.debug("No remote participants found to send translation")
                return
            
            # 发送到第一个远程参与者（前端）
            client_participant = remote_participants[0]
            
            # 计算原文的 delta
            original_delta = self.compute_delta(self.last_sent_original, original_text)
            
            # 计算译文的 delta
            translation_delta = ""
            if translated_text:
                translation_delta = self.compute_delta(self.last_sent_translation, translated_text)
            
            # 准备翻译数据（包含 full_text 和 delta）
            translation_data = {
                "type": "final" if is_final else "interim",
                "original": {
                    "full_text": original_text,
                    "delta": original_delta,
                    "language": original_language
                },
                "translation": {
                    "full_text": translated_text,
                    "delta": translation_delta,
                    "language": self.target_language
                } if translated_text else None,
                "timestamp": time.time()
            }
            
            # 通过 RPC 发送
            await self.ctx.room.local_participant.perform_rpc(
                destination_identity=client_participant.identity,
                method="receive_translation",
                payload=json.dumps(translation_data)
            )
            
            # 更新已发送的文本（用于下一次 delta 计算）
            if is_final:
                # final 时重置，开始新的句子
                self.last_sent_original = ""
                self.last_sent_translation = ""
            else:
                # interim 时累积
                self.last_sent_original = original_text
                if translated_text:
                    self.last_sent_translation = translated_text
            
            log_type = "FINAL" if is_final else "INTERIM"
            logger.debug(f"[{log_type}] Sent to frontend: {original_language} -> {self.target_language}, delta: {len(original_delta)} chars")
            
        except Exception as e:
            logger.warning(f"Failed to send translation via RPC: {e}")
    
    async def stt_node(
        self, 
        audio: AsyncIterable[rtc.AudioFrame], 
        model_settings: Optional[dict] = None
    ) -> Optional[AsyncIterable[str]]:
        """拦截 STT 事件以处理 interim 和 final 转录结果"""
        parent_stream = super().stt_node(audio, model_settings)
        
        if parent_stream is None:
            return None
        
        async def process_stream():
            # 跟踪最近的 interim 文本，用于去重和优化
            last_interim_text = ""
            
            async def translation_callback(original: str, source: str, translated: str, is_final: bool):
                """翻译完成后的回调"""
                await self.send_translation_to_frontend(
                    original_text=original,
                    original_language=source,
                    translated_text=translated,
                    is_final=is_final
                )
            
            async for event in parent_stream:
                # 处理 Deepgram 的转录事件
                if hasattr(event, 'alternatives') and event.alternatives:
                    for alt in event.alternatives:
                        if hasattr(alt, 'text') and alt.text:
                            transcript = alt.text.strip()
                            
                            if not transcript:
                                continue
                            
                            # 判断是 interim 还是 final
                            is_final = False
                            if hasattr(event, 'type'):
                                event_type = str(event.type)
                                is_final = 'FINAL' in event_type or 'final' in event_type.lower()
                            elif hasattr(event, 'is_final'):
                                is_final = event.is_final
                            elif hasattr(alt, 'is_final'):
                                is_final = alt.is_final
                            
                            if is_final:
                                # ═══════════════════════════════
                                # FINAL 结果：自适应批量翻译
                                # ═══════════════════════════════
                                
                                # 分配全局序号
                                sequence = self.sentence_sequence
                                self.sentence_sequence += 1
                                
                                logger.info(
                                    f"[FINAL] seq={sequence}, "
                                    f"text='{transcript[:50]}...'"
                                )
                                
                                # ✅ 优化1：取消无效的interim翻译
                                cancelled = self.translator.cancel_pending_interim()
                                if cancelled:
                                    logger.debug(
                                        f"[FINAL] Cancelled interim for '{transcript[:30]}...'"
                                    )
                                
                                # ✅ 优化2：加入自适应批量收集器（不阻塞）
                                asyncio.create_task(
                                    self.batch_collector.add_sentence(sequence, transcript)
                                )
                                
                                # 清除 interim 缓存
                                last_interim_text = ""
                                
                            else:
                                # INTERIM 结果：使用防抖机制
                                # 避免重复处理相同的文本
                                if transcript == last_interim_text:
                                    continue
                                
                                last_interim_text = transcript
                                logger.debug(f"[INTERIM] Original ({self.source_language}): {transcript[:50]}...")
                                
                                # 先发送原文到前端（实时显示）
                                await self.send_translation_to_frontend(
                                    original_text=transcript,
                                    original_language=self.source_language,
                                    translated_text=None,
                                    is_final=False
                                )
                                
                                # 使用防抖机制翻译 interim 结果
                                await self.translator.translate_debounced(
                                    text=transcript,
                                    source_language=self.source_language,
                                    target_language=self.target_language,
                                    callback=translation_callback
                                )
                
                yield event
        
        return process_stream()


async def entrypoint(ctx: JobContext):
    # 默认配置：英语到中文，500ms 防抖
    source_language = os.getenv("TRANSLATION_SOURCE_LANGUAGE", "en")
    target_language = os.getenv("TRANSLATION_TARGET_LANGUAGE", "zh")
    debounce_ms = float(os.getenv("TRANSLATION_DEBOUNCE_MS", "500"))
    debounce_enabled_env = os.getenv("TRANSLATION_DEBOUNCE_ENABLED", "true")
    debounce_enabled = debounce_enabled_env.strip().lower() in {"1", "true", "yes", "on"}
    
    # 批量翻译配置
    batch_size = int(os.getenv("TRANSLATION_BATCH_SIZE", "3"))
    batch_timeout_ms = float(os.getenv("TRANSLATION_BATCH_TIMEOUT_MS", "2000"))  # 2秒，匹配实际语速
    
    # 创建带上下文的 agent
    agent = DeepgramTranslationAgent(
        ctx=ctx,
        source_language=source_language,
        target_language=target_language,
        debounce_ms=debounce_ms,
        debounce_enabled=debounce_enabled,
        batch_size=batch_size,
        batch_timeout_ms=batch_timeout_ms
    )
    
    session = AgentSession()
    
    # 先连接房间
    await ctx.connect()
    
    # 注册 RPC 方法：接收前端的语言配置更新
    async def handle_update_config(data: rtc.RpcInvocationData) -> str:
        try:
            config = json.loads(data.payload)
            await agent.update_config(
                source_language=config.get('source'),
                target_language=config.get('target')
            )
            return json.dumps({"status": "success", "message": "Configuration updated"})
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return json.dumps({"status": "error", "message": str(e)})
    
    ctx.room.local_participant.register_rpc_method(
        "update_translation_config",
        handle_update_config
    )
    
    # 在连接后启动 session（处理音频）
    await session.start(
        agent=agent,
        room=ctx.room
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

