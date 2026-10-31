import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from shop_api.database import engine, init_db
from shop_api.api.item.routes import router as item_router
from shop_api.api.cart.routes import router as cart_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.db_initialized = True

    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="Shop API", lifespan=lifespan)

app.state.db_initialized = False
app.state.db_init_lock = asyncio.Lock()


@app.middleware("http")
async def initialize_database(request, call_next):
    if not app.state.db_initialized:
        async with app.state.db_init_lock:
            if not app.state.db_initialized:
                await init_db()
                app.state.db_initialized = True

    return await call_next(request)


app.include_router(item_router)
app.include_router(cart_router)

Instrumentator(
    should_instrument_requests_inprogress=True
).instrument(app).expose(app)