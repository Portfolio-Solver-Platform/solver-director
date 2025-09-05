FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1


RUN useradd -u 10001 -m appuser

WORKDIR /src
COPY requirements.txt .

USER 10001
RUN pip install --no-cache-dir --user -r requirements.txt

COPY src/ .

EXPOSE 8080
CMD ["python", "app.py"]


