import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    HookMatcher,
    AssistantMessage,
    ResultMessage,
)

app = FastAPI(title="Code Review Service")

# In-memory job store. Per-process and lost on restart —
# in production this becomes Redis or a database (see notes below).
JOBS: Dict[str, dict] = {}

REVIEWERS = {
    "correctness": (
        "You review ONLY for correctness: bugs, crashes, unhandled inputs "
        "(None, empty, wrong type), and logic errors. Read the Python files and "
        "report concrete issues with file names. Ignore style."
    ),
    "style": (
        "You review ONLY for style and readability: naming, docstrings, PEP 8, "
        "structure. List concrete suggestions with file names. Ignore bugs/tests."
    ),
    "tests": (
        "You review ONLY test coverage. Report which functions lack tests and "
        "which edge cases are untested. Be specific about file and function names."
    ),
}


# --- per-reviewer tracing, written to a per-job file ---
def make_hooks(reviewer: str, trace_path: Path):
    def _log(event, input_data, tool_use_id):
        with trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "time": datetime.now().isoformat(timespec="seconds"),
                "reviewer": reviewer,
                "event": event,
                "tool": input_data.get("tool_name"),
                "tool_use_id": tool_use_id,
            }, default=str) + "\n")

    async def pre_tool(i, t, c):
        _log("pre", i, t); return {}

    async def post_tool(i, t, c):
        _log("post", i, t); return {}

    return {
        "PreToolUse": [HookMatcher(hooks=[pre_tool])],
        "PostToolUse": [HookMatcher(hooks=[post_tool])],
    }


# --- one reviewer = one query(), reading the requested folder ---
async def run_reviewer(name, instructions, target_dir, trace_path) -> str:
    options = ClaudeAgentOptions(
        system_prompt=instructions,
        allowed_tools=["Read", "Glob", "Grep"],
        max_turns=8,
        hooks=make_hooks(name, trace_path),
        cwd=target_dir,                      # read the folder the request named
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
                if getattr(message, "result", None):
                    findings = message.result
        return findings.strip() or "(no findings)"
    except Exception as e:
        return f"(reviewer '{name}' failed: {e})"


# --- the orchestration, returning the assembled markdown ---
async def run_review(target_dir: str, trace_path: Path) -> str:
    names = list(REVIEWERS.keys())
    results = await asyncio.gather(
        *(run_reviewer(n, REVIEWERS[n], target_dir, trace_path) for n in names)
    )
    findings = dict(zip(names, results))

    titles = {
        "correctness": "Correctness (bugs & edge cases)",
        "style": "Style & readability",
        "tests": "Test coverage",
    }
    out = [f"# Code Review\n\n_Generated {datetime.now():%Y-%m-%d %H:%M}_\n"]
    for n in names:
        out.append(f"\n## {titles[n]}\n\n{findings[n]}\n")
    return "\n".join(out)


# --- the background worker: runs the job, updates its status ---
async def run_job(job_id: str, target_dir: str):
    JOBS[job_id]["status"] = "running"
    trace_path = Path(f"trace_{job_id}.jsonl")
    try:
        report = await run_review(target_dir, trace_path)
        JOBS[job_id].update(status="done", report=report)
    except Exception as e:
        JOBS[job_id].update(status="error", error=str(e))


# --- the API ---
class ReviewRequest(BaseModel):
    path: str = "."


@app.post("/reviews")
async def create_review(req: ReviewRequest):
    target = Path(req.path).expanduser().resolve()
    if not target.is_dir():
        raise HTTPException(400, f"Not a directory: {target}")

    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {"status": "queued", "path": str(target)}
    # Launch in the background; return immediately.
    asyncio.create_task(run_job(job_id, str(target)))
    return {"job_id": job_id, "status": "queued"}


@app.get("/reviews/{job_id}")
async def get_review(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "No such job")
    return job


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)