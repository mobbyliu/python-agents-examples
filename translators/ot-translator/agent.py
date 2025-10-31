"""
---
title: TTS Translator with Gladia STT
category: translation
tags: [translation, gladia-stt, multilingual, code-switching, event-handling]
difficulty: advanced
description: Advanced translation system using Gladia STT with code switching and event handling
demonstrates:
  - Gladia STT integration with multiple languages
  - Code switching between French and English
  - Translation event handling and processing
  - Custom STT configuration with translation capabilities
  - Event-driven transcription and speech synthesis
  - Advanced multilingual processing pipeline
---
"""

from pathlib import Path
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import silero, gladia
from livekit import rtc
from typing import Optional, AsyncIterable
import sys
import json
import logging
import asyncio
import time

sys.path.append(str(Path(__file__).parent.parent.parent))

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

logger = logging.getLogger("ot-translator")
logger.setLevel(logging.INFO)

class TranslationDisplayAgent(Agent):
    def __init__(self, ctx: Optional[JobContext] = None):
        super().__init__(
            instructions="You are a helpful assistant that displays translations.",
            stt=gladia.STT(
                languages=["fr", "en", "zh"],  # Support French, English, and Chinese input
                code_switching=True,
                sample_rate=16000,
                bit_depth=16,
                channels=1,
                encoding="wav/pcm",
                translation_enabled=True,
                translation_target_languages=["zh"],  # Only translate to Chinese
                translation_model="base",
                translation_match_original_utterances=True
            ),
            # 移除 TTS，因为我们只显示文本，不进行语音合成
            allow_interruptions=False,
            vad=silero.VAD.load()
        )
        self.ctx = ctx  # Store context for RPC access
    
    async def send_translation_to_frontend(
        self, 
        original_text: str, 
        original_language: str, 
        translated_text: Optional[str], 
        is_final: bool
    ):
        """Send translation data to frontend via RPC"""
        if not self.ctx or not self.ctx.room:
            logger.debug("No room context available for RPC")
            return
        
        try:
            # Get remote participants (frontend clients)
            remote_participants = list(self.ctx.room.remote_participants.values())
            if not remote_participants:
                logger.debug("No remote participants found to send translation")
                return
            
            # Send to the first remote participant (the frontend)
            client_participant = remote_participants[0]
            
            # Prepare translation data
            translation_data = {
                "type": "final" if is_final else "interim",
                "original": {
                    "text": original_text,
                    "language": original_language
                },
                "translation": {
                    "text": translated_text,
                    "language": "zh"
                } if translated_text else None,
                "timestamp": time.time()
            }
            
            # Send via RPC
            await self.ctx.room.local_participant.perform_rpc(
                destination_identity=client_participant.identity,
                method="receive_translation",
                payload=json.dumps(translation_data)
            )
            logger.info(f"Sent translation to frontend: {original_language} -> zh (final={is_final})")
        except Exception as e:
            logger.warning(f"Failed to send translation via RPC: {e}")
    
    async def stt_node(self, audio: AsyncIterable[rtc.AudioFrame], model_settings: Optional[dict] = None) -> Optional[AsyncIterable[str]]:
        """拦截 STT 原始事件以获取翻译数据"""
        parent_stream = super().stt_node(audio, model_settings)
        
        if parent_stream is None:
            return None
        
        async def process_stream():
            # 跟踪最近的原始转录（非中文），用于与后续的翻译关联
            # 包括 interim 和 final 状态
            last_non_zh_transcript = None
            
            async for event in parent_stream:
                if hasattr(event, 'alternatives') and event.alternatives:
                    for alt in event.alternatives:
                        if hasattr(alt, 'text') and alt.text:
                            transcript = alt.text.strip()
                            language = getattr(alt, 'language', None)
                            is_final = hasattr(event, 'type') and 'FINAL' in str(event.type)
                            is_interim = hasattr(event, 'type') and 'INTERIM' in str(event.type)
                            target_language = "zh"
                            
                            # 只处理最终和中间事件
                            if is_final or is_interim:
                                if language == target_language:
                                    # 这是中文事件
                                    if is_final:
                                        # 检查是否有待处理的非中文转录
                                        if last_non_zh_transcript and last_non_zh_transcript.get('language') != target_language:
                                            # 这是翻译结果
                                            original_text = last_non_zh_transcript['text']
                                            original_lang = last_non_zh_transcript['language']
                                            
                                            logger.info(f"原始 ({original_lang}): {original_text}")
                                            logger.info(f"✓ 翻译 (中文): {transcript}")
                                            
                                            # 发送配对后的原始文本和翻译到前端
                                            asyncio.create_task(
                                                self.send_translation_to_frontend(
                                                    original_text=original_text,
                                                    original_language=original_lang,
                                                    translated_text=transcript,
                                                    is_final=True
                                                )
                                            )
                                            
                                            # 清除已处理的转录
                                            last_non_zh_transcript = None
                                        else:
                                            # 这是原始中文输入，没有翻译
                                            logger.info(f"最终转录 (中文): {transcript}")
                                            
                                            # 发送到前端（仅原始文本，无翻译）
                                            asyncio.create_task(
                                                self.send_translation_to_frontend(
                                                    original_text=transcript,
                                                    original_language="zh",
                                                    translated_text=None,
                                                    is_final=True
                                                )
                                            )
                                    elif is_interim:
                                        # 实时中文转录（interim）
                                        # 只有在有配对 non-zh 转录时才发送（说明是翻译）
                                        if last_non_zh_transcript and last_non_zh_transcript.get('language') != target_language:
                                            # 这是实时翻译，配对发送
                                            asyncio.create_task(
                                                self.send_translation_to_frontend(
                                                    original_text=last_non_zh_transcript['text'],
                                                    original_language=last_non_zh_transcript['language'],
                                                    translated_text=transcript,
                                                    is_final=False
                                                )
                                            )
                                        # 如果没有配对，不发送（可能是原始中文输入的interim，等待final）
                                else:
                                    # 这是非中文的原始转录（英语、法语等）
                                    if is_final:
                                        # 保存原始转录信息，等待翻译事件
                                        # 重要：不立即发送，等待配对翻译后再发送
                                        last_non_zh_transcript = {
                                            'text': transcript,
                                            'language': language
                                        }
                                        logger.info(f"原始转录 ({language}): {transcript}")
                                        if language != target_language:
                                            logger.info(f"  → 等待翻译到 {target_language}...")
                                        # 不发送，等待翻译事件
                                    elif is_interim:
                                        # 实时非中文转录（interim）
                                        # 保存到 last_non_zh_transcript，用于后续配对
                                        last_non_zh_transcript = {
                                            'text': transcript,
                                            'language': language
                                        }
                                        logger.debug(f"→ 实时转录 ({language}): {transcript}")
                                        # 发送实时更新（只有原文，等待翻译）
                                        asyncio.create_task(
                                            self.send_translation_to_frontend(
                                                original_text=transcript,
                                                original_language=language,
                                                translated_text=None,
                                                is_final=False
                                            )
                                        )
                
                yield event
        
        return process_stream()

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    
    # Create agent with context for RPC access
    agent = TranslationDisplayAgent(ctx=ctx)
    session = AgentSession()
    
    await session.start(
        agent=agent,
        room=ctx.room
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))