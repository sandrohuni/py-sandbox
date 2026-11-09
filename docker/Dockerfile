FROM python:3.13-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uvx /usr/local/bin/
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates bash \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*
RUN npm install -g @anthropic-ai/claude-code @openai/codex
ARG AGENT_UID=1000
ARG AGENT_GID=1000
RUN if ! getent group ${AGENT_GID}; then groupadd -g ${AGENT_GID} agent; fi \
 && useradd -m -u ${AGENT_UID} -g ${AGENT_GID} -s /bin/bash agent \
 && mkdir -p /home/agent/.claude /home/agent/.codex \
 && chown -R agent:agent /home/agent
ENV HOME=/home/agent CLAUDE_CONFIG_DIR=/home/agent/.claude
USER agent
