from dataclasses import dataclass, field


@dataclass
class Item:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass
class CartItem:
    id: int
    name: str
    quantity: int
    available: bool


@dataclass
class Cart:
    id: int
    items: list[CartItem] = field(default_factory=list)
    price: float = 0.0
    quantity: int = 0
