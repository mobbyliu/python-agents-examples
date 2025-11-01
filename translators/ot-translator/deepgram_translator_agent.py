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
from typing import Optional, AsyncIterable
from google.cloud import translate_v2 as translate
import sys
import json
import logging
import asyncio
import time
import os

sys.path.append(str(Path(__file__).parent.parent.parent))

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

logger = logging.getLogger("deepgram-translator")
logger.setLevel(logging.INFO)


class DebouncedTranslator:
    """处理带防抖的翻译请求"""
    
    def __init__(self, debounce_ms: float = 500):
        self.debounce_delay = debounce_ms / 1000
        self.pending_task: Optional[asyncio.Task] = None
        self.translate_client = None
        
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
            
            # 调用 Google Translate API
            result = self.translate_client.translate(
                text,
                target_language=target_language,
                source_language=source_language
            )
            
            translated_text = result['translatedText']
            logger.info(f"Translated ({source_language} -> {target_language}): {text[:50]}... -> {translated_text[:50]}...")
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


class DeepgramTranslationAgent(Agent):
    def __init__(
        self, 
        ctx: Optional[JobContext] = None,
        source_language: str = "en",
        target_language: str = "zh",
        debounce_ms: float = 500
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
            vad=silero.VAD.load()
        )
        
        self.ctx = ctx
        self.source_language = source_language
        self.target_language = target_language
        self.translator = DebouncedTranslator(debounce_ms=debounce_ms)
        
        logger.info(f"DeepgramTranslationAgent initialized: {source_language} -> {target_language}, debounce={debounce_ms}ms")
    
    async def update_config(
        self, 
        source_language: Optional[str] = None, 
        target_language: Optional[str] = None,
        debounce_ms: Optional[float] = None
    ):
        """更新翻译配置"""
        if source_language:
            self.source_language = source_language
            logger.info(f"Source language updated to: {source_language}")
        
        if target_language:
            self.target_language = target_language
            logger.info(f"Target language updated to: {target_language}")
        
        if debounce_ms is not None:
            self.translator.update_debounce_delay(debounce_ms)
    
    async def send_translation_to_frontend(
        self, 
        original_text: str, 
        original_language: str, 
        translated_text: Optional[str], 
        is_final: bool
    ):
        """通过 RPC 发送翻译数据到前端"""
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
            
            # 准备翻译数据
            translation_data = {
                "type": "final" if is_final else "interim",
                "original": {
                    "text": original_text,
                    "language": original_language
                },
                "translation": {
                    "text": translated_text,
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
            
            log_type = "FINAL" if is_final else "INTERIM"
            logger.debug(f"[{log_type}] Sent to frontend: {original_language} -> {self.target_language}")
            
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
                                # FINAL 结果：立即翻译并发送
                                logger.info(f"[FINAL] Original ({self.source_language}): {transcript}")
                                
                                # 先发送原文（无翻译）到前端，让用户立即看到
                                await self.send_translation_to_frontend(
                                    original_text=transcript,
                                    original_language=self.source_language,
                                    translated_text=None,
                                    is_final=False
                                )
                                
                                # 执行翻译（不使用防抖）
                                translated = await self.translator.translate_text(
                                    transcript,
                                    self.source_language,
                                    self.target_language
                                )
                                
                                # 发送最终的翻译结果
                                await self.send_translation_to_frontend(
                                    original_text=transcript,
                                    original_language=self.source_language,
                                    translated_text=translated,
                                    is_final=True
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
    await ctx.connect()
    
    # 默认配置：英语到中文，500ms 防抖
    source_language = os.getenv("TRANSLATION_SOURCE_LANGUAGE", "en")
    target_language = os.getenv("TRANSLATION_TARGET_LANGUAGE", "zh")
    debounce_ms = float(os.getenv("TRANSLATION_DEBOUNCE_MS", "500"))
    
    # 创建带上下文的 agent
    agent = DeepgramTranslationAgent(
        ctx=ctx,
        source_language=source_language,
        target_language=target_language,
        debounce_ms=debounce_ms
    )
    
    session = AgentSession()
    
    # 注册 RPC 方法：接收前端的配置更新
    async def handle_update_config(data: rtc.RpcInvocationData) -> str:
        try:
            config = json.loads(data.payload)
            await agent.update_config(
                source_language=config.get('source'),
                target_language=config.get('target'),
                debounce_ms=config.get('debounce')
            )
            return json.dumps({"status": "success", "message": "Configuration updated"})
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return json.dumps({"status": "error", "message": str(e)})
    
    ctx.room.local_participant.register_rpc_method(
        "update_translation_config",
        handle_update_config
    )
    
    await session.start(
        agent=agent,
        room=ctx.room
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

