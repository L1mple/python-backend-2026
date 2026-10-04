from dataclasses import dataclass, field


@dataclass
class ItemInfo:
    name: str
    price: float
    deleted: bool = False


@dataclass
class ItemEntity:
    id: int
    info: ItemInfo


@dataclass
class PatchItemInfo:
    name: str | None = None
    price: float | None = None


@dataclass
class CartItemEntity:
    id: int
    name: str
    price: float
    quantity: int
    available: bool


@dataclass
class CartEntity:
    id: int
    items: list[CartItemEntity] = field(default_factory=list)
