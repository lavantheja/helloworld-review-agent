from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from arq import create_pool
from arq.connections import RedisSettings
from arq.jobs import Job, JobStatus

REDIS = RedisSettings(host=os.environ.get("REDIS_HOST", "localhost"), port=6379)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = await create_pool(REDIS)   # connection pool to Redis
    yield
    await app.state.redis.close()


app = FastAPI(title="Code Review Service", lifespan=lifespan)


class ReviewRequest(BaseModel):
    path: str = "."

from pathlib import Path

BASE = Path(os.environ.get("REPOS_BASE", "/workspace/repos")).resolve()

@app.post("/reviews")
async def create_review(req: ReviewRequest):
    target = (BASE / req.path).resolve()       # path is relative to BASE
    # Must be a real dir AND must not have escaped BASE via ".."
    if not target.is_dir() or not target.is_relative_to(BASE):
        raise HTTPException(400, "Invalid path")

    job = await app.state.redis.enqueue_job("review_task", str(target))
    return {"job_id": job.job_id, "status": "queued"}

@app.get("/reviews/{job_id}")
async def get_review(job_id: str):
    job = Job(job_id, redis=app.state.redis)
    status = await job.status()
    if status == JobStatus.not_found:
        raise HTTPException(404, "No such job")

    resp = {"job_id": job_id, "status": status.value}
    if status == JobStatus.complete:
        try:
            resp["report"] = await job.result()      # the task's return value
        except Exception as e:
            resp["status"] = "error"                 # the task raised
            resp["error"] = str(e)
    return resp