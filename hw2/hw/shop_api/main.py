from fastapi import FastAPI

from shop_api.api.routers import main_router
from shop_api.core.config import settings

app = FastAPI(
    title=settings.app_title,
    description=settings.app_description,
)
app.include_router(main_router)