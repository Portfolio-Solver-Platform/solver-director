FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1


RUN useradd -u 10001 -m appuser

WORKDIR /src
COPY requirements.txt .
COPY requirements-dev.txt . 

USER 10001
ENV PATH="/home/appuser/.local/bin:${PATH}"

FROM base AS dev
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY src/ .

EXPOSE 8080
CMD ["python", "app.py"]






FROM base AS runtime
RUN pip install --no-cache-dir --user -r requirements.txt

COPY src/ .

EXPOSE 8080
CMD ["python", "app.py"]




