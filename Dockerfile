# FROM python:3.13-slim AS base

# ENV PYTHONDONTWRITEBYTECODE=1 \
#     PYTHONUNBUFFERED=1


# RUN useradd -u 10001 -m appuser

# WORKDIR /src
# COPY requirements.txt .
# COPY requirements-dev.txt . 

# USER 10001
# ENV PATH="/home/appuser/.local/bin:${PATH}"

# FROM base AS dev
# RUN pip install --no-cache-dir --user -r requirements-dev.txt
# # COPY src/ .
# COPY --chown=10001:0 src/ .
# EXPOSE 8080
# CMD ["python", "app.py"]






# FROM base AS runtime
# RUN pip install --no-cache-dir --user -r requirements.txt

# COPY src/ .

# EXPOSE 8080
# CMD ["python", "app.py"]


FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd -u 10001 -m appuser

# Create and own /src BEFORE switching user
RUN mkdir -p /src && chown 10001:0 /src
WORKDIR /src

# Copy manifests first
COPY requirements.txt .
COPY requirements-dev.txt .

# Switch to non-root and expose user-site bin
USER 10001
ENV PATH="/home/appuser/.local/bin:${PATH}"

# -------- dev (CI) --------
FROM base AS dev
RUN pip install --no-cache-dir --user -r requirements-dev.txt
COPY --chown=10001:0 src/ .
EXPOSE 8080
CMD ["python", "app.py"]

# -------- runtime (prod) --------
FROM base AS runtime
RUN pip install --no-cache-dir --user -r requirements.txt
COPY --chown=10001:0 src/ .
EXPOSE 8080
CMD ["python", "app.py"]


