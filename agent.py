import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


# ---- First run: do some work, capture the session id ----
async def first_run():
    session_id = None
    async for message in query(
        prompt="Read utils.py and note what each function does.",
        options=ClaudeAgentOptions(allowed_tools=["Read", "Glob"], cwd="."),
    ):
        if isinstance(message, ResultMessage):
            session_id = message.session_id        # <- here it is
    print(f"Save this: {session_id}")
    return session_id


# ---- Later / new process: resume that exact conversation ----
async def second_run(session_id):
    async for message in query(
        prompt="Now write unit tests based on what you found earlier.",
        options=ClaudeAgentOptions(
            resume=session_id,                     # <- continue that session
            allowed_tools=["Read", "Write", "Glob"],
            permission_mode="acceptEdits",
            cwd=".",
        ),
    ):
        if isinstance(message, ResultMessage):
            print(f"Done: {message.subtype}")


asyncio.run(second_run("46109861-b3a9-4369-8313-4ca292c8fd52"))
