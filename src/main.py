import asyncio
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from .config import Config
from .routers import health, version, api
import prometheus_fastapi_instrumentator
from .auth import auth
import asyncpg
from .spawner.result_collector import result_collector


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create asyncpg connection pool
    app.state.pool = await asyncpg.create_pool(
        host=Config.Database.HOST,
        port=Config.Database.PORT,
        user=Config.Database.USER,
        password=Config.Database.PASSWORD,
        database=Config.Database.NAME,
        min_size=1,
        max_size=10
    )

    # Start result collector background task
    asyncio.create_task(result_collector())

    yield

    # Close connection pool on shutdown
    await app.state.pool.close()


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
app.include_router(api.router, prefix=f"/{Config.Api.VERSION}")

auth.add_docs(app)

# Monitoring
prometheus_fastapi_instrumentator.Instrumentator().instrument(app).expose(app)

# Exclude /metrics from schema
for route in app.routes:
    if route.path == "/metrics":
        route.include_in_schema = False
        break
