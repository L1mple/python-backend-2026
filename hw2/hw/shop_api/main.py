from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from .api.carts.routes import router as carts_router
from .api.items.routes import router as items_router

app = FastAPI(title="Shop API")
app.include_router(carts_router)
app.include_router(items_router)

Instrumentator(
    should_group_status_codes=False,
    should_instrument_requests_inprogress=True,
    inprogress_labels=True,
    excluded_handlers=["/metrics"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
