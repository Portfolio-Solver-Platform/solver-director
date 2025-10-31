
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install skopeo for pushing Docker images to Harbor
RUN apt-get update && apt-get install -y \
    skopeo \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -u 10001 -m appuser

RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


WORKDIR /home/appuser/app

COPY requirements.txt .
COPY requirements-dev.txt .

USER 10001
ENV PATH="/home/appuser/.local/bin:${PATH}"


FROM base AS dev
RUN pip install --no-cache-dir --user -r requirements-dev.txt
RUN pip install git+https://github.com/Portfolio-Solver-Platform/python-auth-lib@791ce2d

COPY pyproject.toml .
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY src/ ./src/
COPY tests/ ./tests/
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "-k", "uvicorn.workers.UvicornWorker", "src.main:app"]


FROM base AS runtime
RUN pip install --no-cache-dir --user -r requirements.txt
RUN pip install git+https://github.com/Portfolio-Solver-Platform/python-auth-lib@791ce2d

COPY pyproject.toml .
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY src/ ./src/
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "-k", "uvicorn.workers.UvicornWorker", "src.main:app"]


