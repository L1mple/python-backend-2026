from prometheus_fastapi_instrumentator import Instrumentator

from shop_api.main import app


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


Instrumentator(
    should_group_status_codes=False,
    should_instrument_requests_inprogress=True,
    excluded_handlers=[r"^/(metrics|health|docs|openapi\.json)$"],
).instrument(app, metric_namespace="shop").expose(app, include_in_schema=False)
