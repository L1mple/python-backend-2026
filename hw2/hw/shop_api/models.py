from dataclasses import dataclass, field


@dataclass(slots=True)
class ItemEntity:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass(slots=True)
class CartLine:
    id: int
    name: str
    quantity: int
    available: bool


@dataclass(slots=True)
class CartEntity:
    id: int
    lines: dict[int, int] = field(default_factory=dict)


@dataclass(slots=True)
class CartView:
    id: int
    items: list[CartLine]
    price: float
