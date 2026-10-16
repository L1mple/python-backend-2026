from fastapi import FastAPI

from shop_api.api import cart, item

app = FastAPI(title="Shop API")

app.include_router(item.router)
app.include_router(cart.router)
