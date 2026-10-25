from fastapi import FastAPI

from shop_api.api.routers import main_router
from shop_api.core.config import settings
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(
    title=settings.app_title,
    description=settings.app_description,
)
Instrumentator().instrument(app).expose(app)
app.include_router(main_router)