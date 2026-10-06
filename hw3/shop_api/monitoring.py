"""Prometheus metrics for successful shop operations and current store state."""

from prometheus_client import Counter, Gauge


items_created = Counter("shop_items_created", "Successfully created items")
carts_created = Counter("shop_carts_created", "Successfully created carts")
cart_additions = Counter(
    "shop_cart_additions",
    "Successful item additions to carts",
)
available_items = Gauge("shop_available_items", "Currently available items")
stored_carts = Gauge("shop_stored_carts", "Currently stored carts")

