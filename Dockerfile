FROM python:3.12-slim

# Node is present so the SDK's Claude Code binary and any npx-based MCP
# servers work. If you ever see "binary not found", uncomment the npm line.
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
 && rm -rf /var/lib/apt/lists/*
# RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .