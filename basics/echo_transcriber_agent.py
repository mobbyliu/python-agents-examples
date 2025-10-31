"""
---
title: Echo Transcriber Agent
category: basics
tags: [echo, transcriber, deepgram, silero]
difficulty: beginner
description: Shows how to create an agent that can transcribe audio and echo it back.
demonstrates:
  - Transcribing audio
  - Echoing audio back that's stored in a buffer
---
"""
import logging
import asyncio
from pathlib import Path
from typing import AsyncIterable, Optional
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession, room_io
from livekit.agents.vad import VADEventType
from livekit.plugins import silero, noise_cancellation

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

logger = logging.getLogger("echo-transcriber")
logger.setLevel(logging.INFO)

class EchoTranscriberAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="You are a real-time transcriber that shows live transcription as the user speaks.",
            stt="assemblyai/universal-streaming",
            vad=None,
            allow_interruptions=False
        )
        
        # We'll set these after initialization
        self.ctx = None
        self.current_transcript = ""
        self.custom_vad = silero.VAD.load(
            min_speech_duration=0.1,  # 快速检测语音开始
            min_silence_duration=0.3,  # 适中的静音检测
        )
        self.vad_stream = self.custom_vad.stream()
        self.is_speaking = False
    
    async def on_enter(self):
        # Override to prevent default TTS greeting
        pass
    
    def set_context(self, ctx: JobContext):
        self.ctx = ctx
    
    async def stt_node(self, audio: AsyncIterable[rtc.AudioFrame], model_settings: Optional[dict] = None) -> Optional[AsyncIterable[str]]:
        """Pass through audio while doing VAD detection"""
        
        async def audio_with_vad():
            """Pass through audio while processing with VAD"""
            async for frame in audio:
                # 进行VAD检测
                self.vad_stream.push_frame(frame)
                yield frame
        
        return super().stt_node(audio_with_vad(), model_settings)

async def entrypoint(ctx: JobContext):
    await ctx.room.local_participant.set_attributes({"lk.agent.state": "listening"})
    
    session = AgentSession()
    agent = EchoTranscriberAgent()
    agent.set_context(ctx)
    
    @session.on("user_input_transcribed")
    def on_transcript(transcript):
        # 实时显示转录文本
        if transcript.is_final:
            # 最终结果：完整句子
            agent.current_transcript = transcript.transcript
            logger.info(f"Final: {transcript.transcript}")
            # 更新房间属性显示最终转录
            asyncio.create_task(ctx.room.local_participant.set_attributes({
                "lk.agent.transcript": transcript.transcript,
                "lk.agent.state": "transcribed"
            }))
        else:
            # 中间结果：实时更新
            logger.info(f"Live: {transcript.transcript}")
            # 更新房间属性显示实时转录
            asyncio.create_task(ctx.room.local_participant.set_attributes({
                "lk.agent.transcript": transcript.transcript,
                "lk.agent.state": "transcribing"
            }))
    
    async def process_vad():
        """Process VAD events for state tracking"""
        async for vad_event in agent.vad_stream:
            if vad_event.type == VADEventType.START_OF_SPEECH:
                agent.is_speaking = True
                logger.info("VAD: Start of speech detected")
                await ctx.room.local_participant.set_attributes({"lk.agent.state": "speaking"})
                    
            elif vad_event.type == VADEventType.END_OF_SPEECH:
                agent.is_speaking = False
                logger.info("VAD: End of speech detected")
                await ctx.room.local_participant.set_attributes({"lk.agent.state": "listening"})
    
    # Start VAD processing
    vad_task = asyncio.create_task(process_vad())
    
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=room_io.RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
            audio_sample_rate=48000,
            audio_num_channels=1,
        )
    )
    
    # Keep VAD task running
    await vad_task

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))