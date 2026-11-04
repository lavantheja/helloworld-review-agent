import json
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import (
    query, ClaudeAgentOptions, HookMatcher, AssistantMessage, ResultMessage,
)

REVIEWERS = {
    "correctness": (
        "You review ONLY for correctness: bugs, crashes, unhandled inputs, and "
        "logic errors. Report concrete issues with file names. Ignore style."
    ),
    "style": (
        "You review ONLY for style/readability: naming, docstrings, PEP 8. "
        "List concrete suggestions with file names. Ignore bugs/tests."
    ),
    "tests": (
        "You review ONLY test coverage. Report which functions lack tests and "
        "which edge cases are untested. Be specific."
    ),
}


def make_hooks(reviewer, trace_path: Path):
    def _log(event, i, t):
        with trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "time": datetime.now().isoformat(timespec="seconds"),
                "reviewer": reviewer, "event": event,
                "tool": i.get("tool_name"), "tool_use_id": t,
            }, default=str) + "\n")

    async def pre(i, t, c): _log("pre", i, t); return {}
    async def post(i, t, c): _log("post", i, t); return {}
    return {"PreToolUse": [HookMatcher(hooks=[pre])],
            "PostToolUse": [HookMatcher(hooks=[post])]}


async def run_reviewer(name, instructions, target_dir, trace_path) -> str:
    options = ClaudeAgentOptions(
        system_prompt=instructions,
        allowed_tools=["Read", "Glob", "Grep"],
        max_turns=8,
        hooks=make_hooks(name, trace_path),
        cwd=target_dir,
    )
    findings = ""
    try:
        async for m in query(prompt="Review all Python files here as instructed.",
                             options=options):
            if isinstance(m, AssistantMessage):
                for b in m.content:
                    if hasattr(b, "text"):
                        findings += b.text + "\n"
            elif isinstance(m, ResultMessage):
                if getattr(m, "result", None):
                    findings = m.result
        return findings.strip() or "(no findings)"
    except Exception as e:
        return f"(reviewer '{name}' failed: {e})"


async def run_review(target_dir: str, trace_path: Path) -> str:
    import asyncio
    names = list(REVIEWERS.keys())
    results = await asyncio.gather(
        *(run_reviewer(n, REVIEWERS[n], target_dir, trace_path) for n in names)
    )
    findings = dict(zip(names, results))
    titles = {"correctness": "Correctness", "style": "Style & readability",
              "tests": "Test coverage"}
    out = [f"# Code Review\n\n_Generated {datetime.now():%Y-%m-%d %H:%M}_\n"]
    for n in names:
        out.append(f"\n## {titles[n]}\n\n{findings[n]}\n")
    return "\n".join(out)