from fastapi import FastAPI

from app.routers.health import router as health_router

app = FastAPI(
    title="VetGlobal API",
    version="1.0.0",
    description="VetGlobal Asynchronous Document Processing API",
)

app.include_router(health_router)
