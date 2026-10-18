from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from shop_api import models  # noqa: F401  — регистрирует модели в Base.metadata
from shop_api.api import cart, item
from shop_api.database import Base, engine

# Создаём таблицы при импорте модуля — чтобы они были готовы
# до первого запроса, в том числе при запуске через TestClient.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Shop API")

Instrumentator(
    should_instrument_requests_inprogress=True,
    inprogress_labels=True,
).instrument(app).expose(app)

app.include_router(item.router)
app.include_router(cart.router)
