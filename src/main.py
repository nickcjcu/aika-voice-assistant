
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession
from livekit.plugins import openai


# Load credentials from the local .env file.
load_dotenv()


class AikaAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
            You are AIKA+, a friendly AI kitchen assistant.

            Help users with cooking, recipes, ingredient substitutions,
            food preparation and kitchen questions.

            Keep spoken responses clear, natural and concise.
            Do not claim to have performed an action unless you have.
            If a request is unclear, ask a short follow up question.
            """
        )


server = AgentServer()


@server.rtc_session(agent_name="aika-assistant")
async def aika_assistant(ctx: agents.JobContext):
    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            voice="marin",
        ),
    )

    await session.start(
        room=ctx.room,
        agent=AikaAssistant(),
    )

    await session.generate_reply(
        instructions="Greet the user and briefly introduce yourself as AIKA+, their kitchen assistant."
    )


if __name__ == "__main__":
    agents.cli.run_app(server)