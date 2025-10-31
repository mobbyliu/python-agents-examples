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

sys.path.append(str(Path(__file__).parent.parent))

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

class TranslationDisplayAgent(Agent):
    def __init__(self):
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
    
    async def stt_node(self, audio: AsyncIterable[rtc.AudioFrame], model_settings: Optional[dict] = None) -> Optional[AsyncIterable[str]]:
        """拦截 STT 原始事件以获取翻译数据"""
        parent_stream = super().stt_node(audio, model_settings)
        
        if parent_stream is None:
            return None
        
        async def process_stream():
            # 跟踪最近的原始转录（非中文），用于与后续的翻译关联
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
                                            print(f"原始 ({last_non_zh_transcript['language']}): {last_non_zh_transcript['text']}")
                                            print(f"✓ 翻译 (中文): {transcript}")
                                            # 清除已处理的转录
                                            last_non_zh_transcript = None
                                        else:
                                            # 这是原始中文输入
                                            print(f"最终转录 (中文): {transcript}")
                                    elif is_interim:
                                        print(f"→ 实时转录 (中文): {transcript}")
                                else:
                                    # 这是非中文的原始转录
                                    if is_final:
                                        # 保存原始转录信息，等待翻译事件
                                        last_non_zh_transcript = {
                                            'text': transcript,
                                            'language': language
                                        }
                                        print(f"原始转录 ({language}): {transcript}")
                                        if language != target_language:
                                            print(f"  → 等待翻译到 {target_language}...")
                                    elif is_interim:
                                        print(f"→ 实时转录 ({language}): {transcript}")
                
                yield event
        
        return process_stream()

async def entrypoint(ctx: JobContext):
    session = AgentSession()
    
    await session.start(
        agent=TranslationDisplayAgent(),
        room=ctx.room
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))