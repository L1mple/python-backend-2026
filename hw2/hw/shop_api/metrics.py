from contextlib import contextmanager
from time import perf_counter

from fastapi import HTTPException
from prometheus_client import Counter, Histogram


class ShopMetrics:
    """Bounded operation metrics and observed cart distributions."""

    def __init__(self):
        self.created = Counter(
            "shop_created", "Successfully created resources", ["resource"]
        )
        self.deletions = Counter(
            "shop_item_deletions", "Successful item deletion operations"
        )
        self.additions = Counter(
            "shop_cart_additions", "Cart addition outcomes", ["result"]
        )
        self.duration = Histogram(
            "shop_stage_duration_seconds",
            "Shop operation duration including failures",
            ["stage", "result"],
            buckets=(
                0.0001,
                0.0005,
                0.001,
                0.0025,
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
        self.value = Histogram(
            "shop_cart_value",
            "Observed cart value, not revenue",
            buckets=(0, 10, 50, 100, 500, 1000, 5000, 10000, 100000, 1000000, 10000000),
        )
        self.quantity = Histogram(
            "shop_cart_quantity",
            "Observed cart quantity including unavailable items",
            buckets=(0, 1, 5, 10, 25, 50, 100, 500, 1000, 10000, 100000, 1000000),
        )
        self.unavailable = Histogram(
            "shop_cart_unavailable_quantity",
            "Observed unavailable item quantity",
            buckets=(0, 1, 5, 10, 25, 50, 100, 500, 1000, 10000, 100000, 1000000),
        )

    @contextmanager
    def stage(self, name):
        start = perf_counter()
        result = "success"
        try:
            yield
        except HTTPException as error:
            result = {404: "not_found", 422: "rejected"}.get(error.status_code, "error")
            raise
        except Exception:
            result = "error"
            raise
        finally:
            self.duration.labels(stage=name, result=result).observe(
                perf_counter() - start
            )
            if name == "cart_mutation":
                self.additions.labels(result=result).inc()

    def observe_cart(self, cart):
        self.value.observe(cart.price)
        self.quantity.observe(sum(item.quantity for item in cart.items))
        self.unavailable.observe(
            sum(item.quantity for item in cart.items if not item.available)
        )


metrics = ShopMetrics()
