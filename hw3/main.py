from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from shop_api.main import DB, app


@app.get("/health", include_in_schema=False)
def health(db: DB) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


Instrumentator(
    should_group_status_codes=False,
    should_instrument_requests_inprogress=True,
    excluded_handlers=[r"^/(metrics|health|docs|openapi\.json)$"],
).instrument(app, metric_namespace="shop").expose(app, include_in_schema=False)
