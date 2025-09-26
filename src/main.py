from fastapi import FastAPI
from .config import Config
from .routers import health, version, api
import prometheus_fastapi_instrumentator

app = FastAPI(
    debug=Config.App.DEBUG,
    root_path=Config.Api.ROOT_PATH,
    title=Config.Api.TITLE,
    description=Config.Api.DESCRIPTION,
    version=Config.App.VERSION,
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
