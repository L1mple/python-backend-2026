from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from shop_api.routes import router_cart, router_item
from shop_api.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)

app.include_router(router_cart)
app.include_router(router_item)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
