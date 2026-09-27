from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from shop_api.exceptions import NotFoundError
from shop_api.routers.items_router import router as item_router
from shop_api.routers.carts_router import router as cart_router
from shop_api.routers.chat_router import router as chat_router

app = FastAPI(title="Shop API")


@app.exception_handler(NotFoundError)
async def unicorn_exception_handler(request: Request, exc: NotFoundError):
    return PlainTextResponse(exc.detail, status_code=exc.status_code)


app.include_router(cart_router)
app.include_router(item_router)
app.include_router(chat_router)
