from fastapi import FastAPI

from app.routers.health import router as health_router
from app.routers.pets import router as pets_router
from app.routers.documents import router as documents_router

app = FastAPI(
    title="VetGlobal API",
    version="1.0.0",
    description="VetGlobal Asynchronous Document Processing API",
)

app.include_router(health_router)
app.include_router(pets_router)
app.include_router(documents_router)
