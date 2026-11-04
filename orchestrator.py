import asyncio
import json
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    HookMatcher,
    AssistantMessage,
    ResultMessage,
)

TRACE = Path("agent_trace.jsonl")


# ---------------------------------------------------------------------------
# Per-reviewer tracing hooks.
# A factory bakes the reviewer's name into the hook so every trace line is
# unambiguously tagged — this is what gives clean per-agent traces.
# ---------------------------------------------------------------------------
def make_hooks(reviewer: str):
    def _log(event, input_data, tool_use_id):
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "reviewer": reviewer,                 # <- which agent this call belongs to
            "event": event,
            "tool": input_data.get("tool_name"),
            "tool_use_id": tool_use_id,
        }
        with TRACE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    async def pre_tool(input_data, tool_use_id, context):
        _log("pre", input_data, tool_use_id)
        return {}

    async def post_tool(input_data, tool_use_id, context):
        _log("post", input_data, tool_use_id)
        return {}

    return {
        "PreToolUse": [HookMatcher(hooks=[pre_tool])],
        "PostToolUse": [HookMatcher(hooks=[post_tool])],
    }


# ---------------------------------------------------------------------------
# One reviewer = one query(). YOU collect its output and return it as a string.
# ---------------------------------------------------------------------------
async def run_reviewer(name: str, instructions: str) -> str:
    options = ClaudeAgentOptions(
        system_prompt=instructions,
        allowed_tools=["Read", "Glob", "Grep"],   # read-only
        max_turns=8,                               # <- EACH reviewer bounded on its own
        hooks=make_hooks(name),                    # <- EACH reviewer traced on its own
        cwd=".",
    )

    findings = ""
    try:
        async for message in query(
            prompt="Review all the Python files in this folder as instructed.",
            options=options,
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "text"):
                        findings += block.text + "\n"
            elif isinstance(message, ResultMessage):
                # Prefer the SDK's final result text when present.
                if getattr(message, "result", None):
                    findings = message.result
        return findings.strip() or "(no findings returned)"
    except Exception as e:
        # Graceful degradation: one dead reviewer doesn't sink the report.
        return f"(reviewer '{name}' failed: {e})"


# ---------------------------------------------------------------------------
# The orchestrator: YOUR code runs the reviewers, collects, and writes.
# ---------------------------------------------------------------------------
async def main():
    TRACE.unlink(missing_ok=True)   # fresh trace each run

    reviewers = {
        "correctness": (
            "You review ONLY for correctness: bugs, crashes, unhandled inputs "
            "(None, empty, wrong type), and logic errors. Read the Python files "
            "and report concrete issues with file names and the problematic code. "
            "Ignore style."
        ),
        "style": (
            "You review ONLY for style and readability: naming, docstrings, PEP 8, "
            "structure. Read the Python files and list concrete suggestions with "
            "file names. Ignore bugs and tests."
        ),
        "tests": (
            "You review ONLY test coverage. Read the source and any test files, and "
            "report which functions lack tests and which edge cases are untested. "
            "Be specific about file and function names."
        ),
    }

    # Run all three in parallel; collect their findings into a dict.
    names = list(reviewers.keys())
    results = await asyncio.gather(
        *(run_reviewer(n, reviewers[n]) for n in names)
    )
    findings = dict(zip(names, results))

    # YOUR code writes the report — deterministic, can't stall.
    report = [f"# Code Review\n\n_Generated {datetime.now():%Y-%m-%d %H:%M}_\n"]
    titles = {
        "correctness": "Correctness (bugs & edge cases)",
        "style": "Style & readability",
        "tests": "Test coverage",
    }
    for n in names:
        report.append(f"\n## {titles[n]}\n\n{findings[n]}\n")

    Path("REVIEW.md").write_text("\n".join(report), encoding="utf-8")
    print("Wrote REVIEW.md")
    print(f"Trace: {TRACE.resolve()}")


asyncio.run(main())