from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from shop_api.api.item.routes import router as item_router
from shop_api.api.cart.routes import router as cart_router


app = FastAPI(title="Shop API")

app.include_router(item_router)
app.include_router(cart_router)


Instrumentator(
    should_instrument_requests_inprogress=True
).instrument(app).expose(app)

