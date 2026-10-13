from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(health_router, prefix="/api/v1")


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "ok"}
