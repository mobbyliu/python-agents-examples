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
            logger.info("No room context available for RPC")
            return
        
        try:
            # Get remote participants (frontend clients)
            remote_participants = list(self.ctx.room.remote_participants.values())
            if not remote_participants:
                logger.info("No remote participants found to send translation")
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
            # Gladia 的翻译行为：
            # 1. 发送多个 INTERIM 原文（英文/法语等）
            # 2. 直接发送 FINAL 翻译（中文），不发送 FINAL 原文
            # 因此我们需要跟踪最近的 INTERIM 非中文转录，用来配对 FINAL 中文
            
            # 使用队列保存最近的 INTERIM 转录，避免被覆盖
            from collections import deque
            interim_queue = deque(maxlen=20)  # 保留最近 20 条 INTERIM
            target_language = "zh"
            
            def find_best_match(queue, timeout=5.0):
                """从队列中找到最合适的 INTERIM 转录进行配对"""
                if not queue:
                    return None
                
                current_time = time.time()
                # 过滤掉超时的条目
                valid_items = [
                    item for item in queue 
                    if current_time - item['timestamp'] < timeout
                ]
                
                if not valid_items:
                    return None
                
                # 选择最长的（最完整的）转录
                # Gladia 通常在发送 FINAL 翻译前的最后一个 INTERIM 是最完整的
                best_match = max(valid_items, key=lambda x: len(x['text']))
                return best_match
            
            async for event in parent_stream:
                if hasattr(event, 'alternatives') and event.alternatives:
                    for alt in event.alternatives:
                        if hasattr(alt, 'text') and alt.text:
                            transcript = alt.text.strip()
                            language = getattr(alt, 'language', None)
                            
                            # 尝试直接获取 is_final（如果 LiveKit 保留了 Gladia 的原始字段）
                            # 否则通过 event.type 判断
                            if hasattr(event, 'is_final'):
                                is_final = event.is_final
                                is_interim = not event.is_final
                            elif hasattr(alt, 'is_final'):
                                is_final = alt.is_final
                                is_interim = not alt.is_final
                            else:
                                # 回退到通过 event.type 判断（当前方式）
                                is_final = hasattr(event, 'type') and 'FINAL' in str(event.type)
                                is_interim = hasattr(event, 'type') and 'INTERIM' in str(event.type)
                            
                            # 调试：打印事件结构（首次运行时）
                            if not hasattr(process_stream, '_debug_logged'):
                                logger.info(f"Event structure: type={getattr(event, 'type', None)}, "
                                           f"has is_final={hasattr(event, 'is_final')}, "
                                           f"alt has is_final={hasattr(alt, 'is_final')}, "
                                           f"event dir={[x for x in dir(event) if not x.startswith('_')]}")
                                process_stream._debug_logged = True
                            
                            # 只处理最终和中间事件
                            if is_final or is_interim:
                                if language == target_language:
                                    # 这是中文事件
                                    if is_final:
                                        # FINAL 中文 - 可能是翻译，也可能是原始中文输入
                                        # 从队列中找到最佳匹配的 INTERIM 非中文转录
                                        best_match = find_best_match(interim_queue, timeout=5.0)
                                        
                                        if best_match and best_match['language'] != target_language:
                                            # 这是翻译！配对发送
                                            original_text = best_match['text']
                                            original_lang = best_match['language']
                                            
                                            logger.info(f"原始 ({original_lang}): {original_text}")
                                            logger.info(f"✓ 翻译 (中文): {transcript}")
                                            logger.info(f"   匹配置信度: 原文长度={len(original_text)}, 队列中有 {len(interim_queue)} 条记录")
                                            
                                            # 发送配对后的原始文本和翻译到前端
                                            asyncio.create_task(
                                                self.send_translation_to_frontend(
                                                    original_text=original_text,
                                                    original_language=original_lang,
                                                    translated_text=transcript,
                                                    is_final=True
                                                )
                                            )
                                            
                                            # 清除队列中已处理的转录（只保留更新的）
                                            interim_queue.clear()
                                        else:
                                            # 这是原始中文输入（不需要翻译）
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
                                        # INTERIM 中文 - 可能是实时翻译，也可能是原始中文
                                        # 只有在有配对 non-zh 转录时才发送（说明是翻译）
                                        best_match = find_best_match(interim_queue, timeout=5.0)
                                        
                                        if best_match and best_match['language'] != target_language:
                                            # 这是实时翻译，配对发送
                                            asyncio.create_task(
                                                self.send_translation_to_frontend(
                                                    original_text=best_match['text'],
                                                    original_language=best_match['language'],
                                                    translated_text=transcript,
                                                    is_final=False
                                                )
                                            )
                                        # 如果没有配对，不发送（等待 final）
                                else:
                                    # 这是非中文的原始转录（英语、法语等）
                                    if is_interim:
                                        # 将 INTERIM 非中文转录添加到队列
                                        interim_item = {
                                            'text': transcript,
                                            'language': language,
                                            'timestamp': time.time()
                                        }
                                        interim_queue.append(interim_item)
                                        logger.info(f"→ 实时转录 ({language}): {transcript[:50]}... [队列: {len(interim_queue)}]")
                                        
                                        # 发送实时更新（只有原文，等待翻译）
                                        asyncio.create_task(
                                            self.send_translation_to_frontend(
                                                original_text=transcript,
                                                original_language=language,
                                                translated_text=None,
                                                is_final=False
                                            )
                                        )
                                    elif is_final:
                                        # FINAL 非中文 - 罕见情况（Gladia 通常不发送）
                                        # 如果收到了，说明没有翻译，直接发送原文
                                        logger.info(f"最终转录 ({language}): {transcript}")
                                        
                                        asyncio.create_task(
                                            self.send_translation_to_frontend(
                                                original_text=transcript,
                                                original_language=language,
                                                translated_text=None,
                                                is_final=True
                                            )
                                        )
                                        
                                        # 清除 interim 队列
                                        interim_queue.clear()
                
                yield event
        
        return process_stream()

async def entrypoint(ctx: JobContext):
    # Create agent with context for RPC access
    agent = TranslationDisplayAgent(ctx=ctx)
    session = AgentSession()
    
    await session.start(
        agent=agent,
        room=ctx.room
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))