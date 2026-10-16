from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from shop_api.storage import ItemDeletedError, NotFoundError
from shop_api.routers.carts import router as carts_router
from shop_api.routers.items import router as items_router


app = FastAPI(title="Shop API")
app.include_router(items_router)
app.include_router(carts_router)


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ItemDeletedError)
async def deleted_item_handler(request: Request, exc: ItemDeletedError):
    return Response(status_code=304)
