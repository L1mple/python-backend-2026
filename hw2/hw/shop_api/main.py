from fastapi import FastAPI
from prometheus_client import make_asgi_app

from shop_api.routes import router_cart, router_item

app = FastAPI(title="Shop API")

app.include_router(router_cart)
app.include_router(router_item)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
