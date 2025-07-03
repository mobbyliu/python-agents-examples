import logging
from dotenv import load_dotenv

from livekit.agents import JobContext, WorkerOptions, cli, AgentSession

# Import our modular components
from core.game_state import GameUserData
from agents.narrator_agent import NarratorAgent

logger = logging.getLogger("agents-and-storms")
logger.setLevel(logging.INFO)

load_dotenv()


async def entrypoint(ctx: JobContext):
    """Main entry point for the game"""
    await ctx.connect()
    
    # Initialize user data
    userdata = GameUserData(ctx=ctx)
    
    # Create initial agent
    narrator_agent = NarratorAgent()
    
    # Create session with user data
    session = AgentSession[GameUserData](userdata=userdata)
    
    userdata.session = session
    
    # Start with narrator agent
    await session.start(agent=narrator_agent, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))