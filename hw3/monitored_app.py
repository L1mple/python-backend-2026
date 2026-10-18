from prometheus_fastapi_instrumentator import Instrumentator

from shop_api.main import app


Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    excluded_handlers=[r"^/metrics$", r"^/docs$", r"^/redoc$", r"^/openapi\.json$"],
).instrument(
    app,
    latency_lowr_buckets=(
        0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05,
        0.1, 0.25, 0.5, 1, 2.5, 5,
    ),
).expose(app, include_in_schema=False)
