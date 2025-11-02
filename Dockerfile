FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-cache

# Runtime stage for running the FastAPI application
FROM python:3.14-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY ./ /app

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port your FastAPI application listens on
EXPOSE 8000

# Command to run the FastAPI application with Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
