# Minimal image with Python and Codex CLI for codex-cli-linker
FROM python:3.11-slim

ENV CODEX_HOME=/data/.codex \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Node.js + npm to get Codex CLI
RUN apt-get update \
 && apt-get install -y --no-install-recommends nodejs npm ca-certificates curl git \
 && npm install -g @openai/codex-cli \
 && apt-get purge -y --auto-remove \
 && rm -rf /var/lib/apt/lists/*

# Add the single-file tool
COPY codex-cli-linker.py ./

# Prepare data directory for configs
RUN mkdir -p /data/.codex
VOLUME ["/data"]

# Default command: interactive run; override with args in docker run/compose
ENTRYPOINT ["python", "./codex-cli-linker.py"]
CMD ["--help"]

