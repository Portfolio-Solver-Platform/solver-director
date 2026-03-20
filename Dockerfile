
FROM python:3.13-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:72ab0aeb448090480ccabb99fb5f52b0dc3c71923bffb5e2e26517a1c27b7fec /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN useradd -u 10001 -m appuser

WORKDIR /home/appuser/app

ENV PATH="/home/appuser/app/.venv/bin:${PATH}"

COPY pyproject.toml .
COPY uv.lock .


FROM base AS dev
RUN uv sync --frozen --no-install-project
COPY src/ ./src/
COPY tests/ ./tests/
COPY alembic.ini .
COPY alembic/ ./alembic/
RUN uv sync --frozen
USER 10001
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "-k", "uvicorn.workers.UvicornWorker", "src.main:app"]

FROM base AS runtime
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ ./src/
COPY alembic.ini .
COPY alembic/ ./alembic/
RUN uv sync --frozen --no-dev
USER 10001
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "-k", "uvicorn.workers.UvicornWorker", "src.main:app"]

