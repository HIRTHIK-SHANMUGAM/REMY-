"""
REMY — Voice Agent (MCP-powered, optional)
==========================================
LiveKit voice pipeline: STT (Sarvam Saaras) → LLM (swappable) → TTS (OpenAI).
Connects to the REMY MCP server as its tool source, so every voice-triggered
action still passes the permission layer.

Voice is optional: REMY runs fully via the text/dashboard UI (remy/api.py)
without any LiveKit credentials. Install extras: pip install "remy[voice]"

Run:
  uv run agent_remy.py dev      – LiveKit Cloud mode
  uv run agent_remy.py console  – text-only console mode
"""

import logging
import os

from dotenv import load_dotenv

from remy.config import config
from remy.identity import build_system_prompt

load_dotenv()

logger = logging.getLogger("remy-agent")
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Provider config
# ---------------------------------------------------------------------------

STT_PROVIDER = "sarvam"
LLM_PROVIDER = os.getenv("REMY_VOICE_LLM", "gemini")   # gemini | openai
TTS_PROVIDER = "openai"

GEMINI_LLM_MODEL = "gemini-2.5-flash"
OPENAI_LLM_MODEL = "gpt-4o"
OPENAI_TTS_MODEL = "tts-1"
OPENAI_TTS_VOICE = "nova"
TTS_SPEED = 1.15
SARVAM_TTS_LANGUAGE = "en-IN"
SARVAM_TTS_SPEAKER = "rahul"

VOICE_ADDENDUM = """
# VOICE MODE

You are speaking aloud right now.
- Two to four sentences per reply. No lists, no markdown, no tool names.
- Call tools silently — never narrate function calls; say something natural
  like "give me a second" first if a call may take time.
- If a tool reports [PERMISSION], tell the user plainly what you wanted to do
  and that it needs their approval on the REMY dashboard.
""".strip()


def _mcp_server_url() -> str:
    url = f"http://{config.BIND_HOST}:{config.MCP_PORT}/sse"
    logger.info("MCP Server URL: %s", url)
    return url


# ---------------------------------------------------------------------------
# LiveKit wiring (imported lazily so text-only installs work)
# ---------------------------------------------------------------------------

def _build_agent_components():
    from livekit.plugins import google as lk_google, openai as lk_openai, sarvam

    if STT_PROVIDER == "sarvam":
        stt = sarvam.STT(language="unknown", model="saaras:v3",
                         mode="transcribe", flush_signal=True, sample_rate=16000)
    else:
        stt = lk_openai.STT(model="whisper-1")

    if LLM_PROVIDER == "gemini":
        llm = lk_google.LLM(model=GEMINI_LLM_MODEL,
                            api_key=os.getenv("GOOGLE_API_KEY"))
    else:
        llm = lk_openai.LLM(model=OPENAI_LLM_MODEL)

    tts = lk_openai.TTS(model=OPENAI_TTS_MODEL, voice=OPENAI_TTS_VOICE,
                        speed=TTS_SPEED)
    return stt, llm, tts


async def entrypoint(ctx):
    from livekit.agents.llm import mcp
    from livekit.agents.voice import Agent, AgentSession
    from livekit.plugins import silero

    logger.info("REMY online – room: %s | STT=%s | LLM=%s | TTS=%s",
                ctx.room.name, STT_PROVIDER, LLM_PROVIDER, TTS_PROVIDER)

    stt, llm, tts = _build_agent_components()

    class RemyAgent(Agent):
        def __init__(self) -> None:
            super().__init__(
                instructions=build_system_prompt(VOICE_ADDENDUM),
                stt=stt,
                llm=llm,
                tts=tts,
                vad=silero.VAD.load(),
                mcp_servers=[
                    mcp.MCPServerHTTP(
                        url=_mcp_server_url(),
                        transport_type="sse",
                        client_session_timeout_seconds=30,
                    ),
                ],
            )

        async def on_enter(self) -> None:
            from datetime import datetime
            hour = datetime.now().hour
            if hour >= 22 or hour < 4:
                text = f"Up late tonight, {config.USER_NAME}? What are we working on?"
            elif hour < 12:
                text = f"Good morning, {config.USER_NAME}. What's first today?"
            elif hour < 17:
                text = f"Good afternoon, {config.USER_NAME}. What do you need?"
            else:
                text = f"Good evening, {config.USER_NAME}. What are you up to?"
            await self.session.generate_reply(
                instructions=f"Greet the user with: '{text}' — in your current "
                             f"personality settings.")

    session = AgentSession(
        turn_detection="stt" if STT_PROVIDER == "sarvam" else "vad",
        min_endpointing_delay=0.07 if STT_PROVIDER == "sarvam" else 0.3,
    )
    await session.start(agent=RemyAgent(), room=ctx.room)


def main():
    from livekit.agents import WorkerOptions, cli
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


def dev():
    """Wrapper to run the agent in dev mode automatically."""
    import sys
    if len(sys.argv) == 1:
        sys.argv.append("dev")
    main()


if __name__ == "__main__":
    main()
