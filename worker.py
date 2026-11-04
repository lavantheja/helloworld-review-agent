from pathlib import Path
from arq.connections import RedisSettings
from review_core import run_review
import os

# An Arq task: first arg is the context, the rest are what you enqueue.
async def review_task(ctx, target_dir: str) -> str:
    job_id = ctx["job_id"]
    trace_path = Path(f"trace_{job_id}.jsonl")
    return await run_review(target_dir, trace_path)


class WorkerSettings:
    functions = [review_task]
    redis_settings = RedisSettings(host=os.environ.get("REDIS_HOST", "localhost"), port=6379)
    max_jobs = 5          # <- concurrency cap, enforced by the worker itself