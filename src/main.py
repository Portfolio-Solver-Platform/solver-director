from contextlib import asynccontextmanager
from fastapi import FastAPI
from .config import Config
from .routers import health, version, api
from .database import engine
from . import models  # Import models to register them with Base
import prometheus_fastapi_instrumentator
import time
import logging
from alembic.config import Config as AlembicConfig
from alembic import command



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown"""
    if Config.App.DEBUG:
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                alembic_cfg = AlembicConfig("alembic.ini")
                command.upgrade(alembic_cfg, "head")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise  # Re-raise in DEBUG mode so we know something is wrong

    yield 
    
app = FastAPI(
    debug=Config.App.DEBUG,
    root_path=Config.Api.ROOT_PATH,
    title=Config.Api.TITLE,
    description=Config.Api.DESCRIPTION,
    version=Config.App.VERSION,
    lifespan=lifespan,
)


app.include_router(health.router, tags=["Health"])
app.include_router(version.router, tags=["Info"])
app.include_router(api.router, tags=["Api"], prefix=f"/{Config.Api.VERSION}")

# Monitoring
prometheus_fastapi_instrumentator.Instrumentator().instrument(app).expose(app)

# Exclude /metrics from schema
for route in app.routes:
    if route.path == "/metrics":
        route.include_in_schema = False
        break
