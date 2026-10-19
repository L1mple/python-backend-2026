from prometheus_fastapi_instrumentator import Instrumentator, metrics
from shop_api.main import app

Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/metrics", "/docs", "/openapi.json"],
).add(
    metrics.default(
        latency_lowr_buckets=(
            0.001,
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1,
            2.5,
            5,
        ),
    )
).instrument(app).expose(app, include_in_schema=False)
