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
COPY pyproject.toml ./
RUN pip install --upgrade pip \
 && pip install \
      "deepagents==0.7.5" \
      "langchain==1.3.14" \
      "langgraph==1.2.10" \
      "langchain-google-genai==4.3.2" \
      "langchain-openai==1.4.2" \
      "mcp==2.0.0" \
      "fastapi==0.141.1" \
      "uvicorn==0.52.1" \
      "pydantic>=2.9"

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
