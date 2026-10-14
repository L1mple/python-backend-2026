from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from shop_api.database import DatabaseSession, engine
from shop_api.monitoring import setup_monitoring
from shop_api.storage import ItemDeletedError, NotFoundError
from shop_api.routers.carts import router as carts_router
from shop_api.routers.items import router as items_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(title="Shop API", lifespan=lifespan)
app.include_router(items_router)
app.include_router(carts_router)
setup_monitoring(app)


@app.get("/health", include_in_schema=False)
def health(session: DatabaseSession):
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "database unavailable"})
    return {"status": "ok"}


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ItemDeletedError)
async def deleted_item_handler(request: Request, exc: ItemDeletedError):
    return Response(status_code=304)
