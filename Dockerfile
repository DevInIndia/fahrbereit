# One Python image, three roles. The backend and both MCP App servers share the same
# dependencies and the same source, so building them separately would triple the build
# time to no purpose. Which role a container plays is decided by its command in
# docker-compose.yml.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# Dependencies first, so editing source does not invalidate the dependency layer.
# pyproject.toml is the single source of truth: duplicating the list here would let
# the container and a local checkout drift apart silently.
COPY pyproject.toml ./
RUN mkdir -p agent && touch agent/__init__.py \
 && pip install --upgrade pip \
 && pip install . \
 && rm -rf agent

COPY agent/ ./agent/
COPY mcpapps/ ./mcpapps/
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY run_backend.py ./

# The response cache and any future session database live here. Mounted as a volume in
# compose so they survive a container restart.
RUN mkdir -p /app/state

EXPOSE 8000
CMD ["python", "run_backend.py"]
