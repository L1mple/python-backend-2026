from dataclasses import dataclass, field


@dataclass(slots=True)
class ItemInfo:
    name: str
    price: float
    deleted: bool = False


@dataclass(slots=True)
class ItemEntity:
    id: int
    info: ItemInfo


@dataclass(slots=True)
class PatchItemInfo:
    name: str | None = None
    price: float | None = None


@dataclass(slots=True)
class CartInfo:
    items: dict[int, int] = field(default_factory=dict)


@dataclass(slots=True)
class CartEntity:
    id: int
    info: CartInfo