from dataclasses import dataclass, field
from shop_api.store.item import ItemEntity

@dataclass(slots=True)
class CartItem:
    info: ItemEntity
    quantity: int = 0


@dataclass(slots=True)
class CartInfo:
    items: list[CartItem] = field(default_factory=list)
    price: float = 0


@dataclass(slots=True)
class CartEntity:
    id: int
    info: CartInfo