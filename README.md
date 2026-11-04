# Code Review Service

An asynchronous HTTP service that runs AI-powered code reviews against a local repository. A client POSTs a path, the API enqueues a job, and an arq worker picks it up and spawns three specialised Claude sub-agents in parallel — one for correctness, one for style, and one for test coverage. Each agent reads the Python files in the target directory using read-only tools, then hands its findings back to the orchestration layer, which assembles them into a single Markdown report stored on the job. The client polls a second endpoint to retrieve the report when it is ready.

---

## Architecture

The service runs as three processes coordinated through Redis:

```
Client
  │
  │  POST /reviews          GET /reviews/{job_id}
  ▼
┌─────────────────┐
│   api  (FastAPI) │  ──enqueue──▶  Redis (arq queue)
└─────────────────┘                        │
                                           │  dequeue
                                           ▼
                                 ┌──────────────────┐
                                 │  worker  (arq)    │
                                 │                   │
                                 │  ┌─────────────┐  │
                                 │  │ correctness │  │  claude-agent-sdk
                                 │  │  reviewer   │  │  query() ──▶ Claude API
                                 │  └─────────────┘  │
                                 │  ┌─────────────┐  │
                                 │  │   style     │  │  (three agents run
                                 │  │  reviewer   │  │   concurrently via
                                 │  └─────────────┘  │   asyncio.gather)
                                 │  ┌─────────────┐  │
                                 │  │    tests    │  │
                                 │  │  reviewer   │  │
                                 │  └─────────────┘  │
                                 └──────────────────┘
```

- **api** — FastAPI app that accepts review requests, enqueues them as arq jobs in Redis, and serves job-status/result lookups.
- **worker** — arq worker process that dequeues jobs and runs the three-reviewer orchestration. Capped at 5 concurrent jobs.
- **redis** — arq's job queue and result store. The API and worker never share a process; Redis is the only communication channel between them.

---

## File-by-file breakdown

| File | Role |
|---|---|
| `api.py` | **API process entry-point.** FastAPI application with `POST /reviews` and `GET /reviews/{job_id}`. Opens an arq Redis connection pool on startup (via `lifespan`), enqueues `review_task` jobs, and reads back job status and results. Path validation ensures requests cannot escape the `REPOS_BASE` directory. |
| `worker.py` | **Worker process entry-point.** Declares the `review_task` arq function and the `WorkerSettings` class (functions list, Redis connection, `max_jobs = 5`). Each invocation calls `run_review()` from `review_core.py` and returns the assembled Markdown report as the job result. |
| `review_core.py` | **Review orchestration and sub-agent logic.** Defines the three reviewer personas (`correctness`, `style`, `tests`) and their system prompts. `run_reviewer()` creates a `ClaudeAgentOptions` object (read-only tools: `Read`, `Glob`, `Grep`; `max_turns = 8`; pre/post tool hooks for tracing) and streams a `query()` call, collecting assistant text. `run_review()` runs all three reviewers in parallel with `asyncio.gather` and assembles their outputs into a single Markdown string. Tool events are appended to a per-job JSONL trace file. |
| `service.py` | **Single-process prototype** (earlier iteration, not used by Docker Compose). Identical reviewer logic, but uses an in-memory `JOBS` dict instead of Redis/arq and runs the background task as an `asyncio.create_task`. Useful for local development without Redis. |
| `orchestrator.py` | **Standalone CLI script** for ad-hoc reviews. Runs the same three reviewers against the current working directory, writes the report to `REVIEW.md`, and writes a trace to `agent_trace.jsonl`. Not part of the HTTP service. |
| `agent.py` | **SDK session-resume demo.** Illustrates how to capture a `session_id` from a `ResultMessage` and resume the same conversation in a later call using `ClaudeAgentOptions(resume=...)`. Not part of the production service. |
| `utils.py` | **Sample code under review.** Two utility functions — `calculate_average()` and `get_user_name()` — that serve as the demo target for the review service. |
| `test_utils.py` | **Unit tests for `utils.py`.** Full `unittest` suite covering normal cases, edge cases, and wrong-type inputs for both utility functions. |
| `requirements.txt` | Python dependencies: `claude-agent-sdk`, `fastapi`, `uvicorn[standard]`, `arq`. |
| `Dockerfile` | Builds from `python:3.12-slim`. Installs Node.js and npm (required by the Claude Code binary that backs the agent SDK), then installs Python dependencies and copies the source. |
| `docker-compose.yml` | Defines the three services (`redis`, `api`, `worker`). Both `api` and `worker` mount `./repos` at `/workspace/repos` — the only directory the service can read. |

---

## Prerequisites

- **Docker** and **Docker Compose** (v2)
- An **Anthropic API key** with access to Claude

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | — | Passed to both `api` and `worker` containers; used by the Claude agent SDK to call the Anthropic API. |
| `REDIS_HOST` | No | `localhost` | Redis hostname. Set automatically to `redis` inside Docker Compose. |
| `REPOS_BASE` | No | `/workspace/repos` | Root directory that the API validates paths against. Any `POST /reviews` path is resolved relative to this directory; requests that would escape it are rejected. |

Create a `.env` file in the project root before running:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

Docker Compose reads `.env` automatically and injects `ANTHROPIC_API_KEY` into both containers.

---

## Running with Docker Compose

```bash
# 1. Put your API key in .env
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 2. Place code you want reviewed under ./repos/
#    (the volume mount maps ./repos → /workspace/repos inside the containers)
mkdir -p repos/myproject
cp -r /path/to/myproject/* repos/myproject/

# 3. Build and start all three services
docker compose up --build

# 4. The API is now listening on http://localhost:8000
```

To run only the worker or API in the foreground for debugging:

```bash
docker compose up redis
docker compose run --rm api uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

---

## API endpoints

### `POST /reviews`

Enqueues a code-review job for the given directory. The path is relative to `REPOS_BASE` (`/workspace/repos` by default).

**Request body**

```json
{
  "path": "myproject"
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `path` | string | `"."` | Directory to review, relative to `REPOS_BASE`. |

**Response — 200 OK**

```json
{
  "job_id": "3f8a1c92b74e11efaa560242ac120002",
  "status": "queued"
}
```

Returns `400` if the path does not exist or resolves outside `REPOS_BASE`.

**Example**

```bash
curl -s -X POST http://localhost:8000/reviews \
  -H "Content-Type: application/json" \
  -d '{"path": "myproject"}' | jq .
```

```json
{
  "job_id": "3f8a1c92b74e11efaa560242ac120002",
  "status": "queued"
}
```

---

### `GET /reviews/{job_id}`

Polls the status of a review job. When complete, includes the full Markdown report.

**Path parameter** — `job_id`: the value returned by `POST /reviews`.

**Response — 200 OK (job in progress)**

```json
{
  "job_id": "3f8a1c92b74e11efaa560242ac120002",
  "status": "in_progress"
}
```

**Response — 200 OK (job complete)**

```json
{
  "job_id": "3f8a1c92b74e11efaa560242ac120002",
  "status": "complete",
  "report": "# Code Review\n\n_Generated 2024-11-04 14:32_\n\n## Correctness (bugs & edge cases)\n\n...\n\n## Style & readability\n\n...\n\n## Test coverage\n\n..."
}
```

**Response — 200 OK (job failed)**

```json
{
  "job_id": "3f8a1c92b74e11efaa560242ac120002",
  "status": "error",
  "error": "..."
}
```

Returns `404` if the job ID is not found.

**Possible `status` values** (from arq `JobStatus`): `queued`, `in_progress`, `complete`, `not_found`, `deferred`, `expired`.

**Example — poll until done**

```bash
JOB_ID="3f8a1c92b74e11efaa560242ac120002"

while true; do
  RESP=$(curl -s "http://localhost:8000/reviews/$JOB_ID")
  STATUS=$(echo "$RESP" | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "complete" ] || [ "$STATUS" = "error" ]; then
    echo "$RESP" | jq -r '.report // .error'
    break
  fi
  sleep 3
done
```

---

## Running the standalone orchestrator (no HTTP, no Redis)

For quick local reviews without Docker, run `orchestrator.py` directly against any directory:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

# Review the current directory
python orchestrator.py
# → writes REVIEW.md and agent_trace.jsonl
```

The output is identical in structure to the report returned by the HTTP service.
