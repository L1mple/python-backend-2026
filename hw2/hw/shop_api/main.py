from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from shop_api.exceptions import NotFoundError
from shop_api.routers.items_router import router as item_router
from shop_api.routers.carts_router import router as cart_router
from shop_api.routers.chat_router import router as chat_router
from shop_api.storage import Store


@asynccontextmanager
async def lifespan(app: FastAPI):
    with Store() as store:
        app.state.store = store
        yield


app = FastAPI(title="Shop API", lifespan=lifespan)


@app.exception_handler(NotFoundError)
async def unicorn_exception_handler(request: Request, exc: NotFoundError):
    return PlainTextResponse(exc.detail, status_code=exc.status_code)


app.include_router(cart_router)
app.include_router(item_router)
app.include_router(chat_router)
