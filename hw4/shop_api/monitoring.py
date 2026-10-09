"""HTTP metrics and successful shop operations, without per-item labels."""

from fastapi import FastAPI
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func, select

from shop_api.database import SessionLocal
from shop_api.models import Cart, Item


items_created = Counter("shop_items_created", "Successfully created items")
carts_created = Counter("shop_carts_created", "Successfully created carts")
cart_additions = Counter("shop_cart_additions", "Successful item additions to carts")
available_items = Gauge("shop_available_items", "Currently available items")
carts = Gauge("shop_carts", "Currently stored carts")


def count_available_items() -> int:
    with SessionLocal() as session:
        return session.scalar(select(func.count()).select_from(Item).where(Item.deleted.is_(False)))


def count_carts() -> int:
    with SessionLocal() as session:
        return session.scalar(select(func.count()).select_from(Cart))


available_items.set_function(count_available_items)
carts.set_function(count_carts)


def setup_monitoring(app: FastAPI) -> None:
    Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=["/metrics", "/health", "/docs", "/openapi.json", "/redoc"],
    ).instrument(
        app,
        latency_lowr_buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
    ).expose(app, include_in_schema=False)
