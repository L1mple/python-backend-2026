

from prometheus_fastapi_instrumentator import Instrumentator
from shop_api.main import app


Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(app)
