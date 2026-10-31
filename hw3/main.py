from prometheus_fastapi_instrumentator import Instrumentator

from hw2.hw.shop_api.main import app

Instrumentator().instrument(app).expose(app)
