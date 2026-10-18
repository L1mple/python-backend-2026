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
    """Хранимое состояние корзины: сколько единиц каждого товара в ней лежит."""

    items: dict[int, int] = field(default_factory=dict)


@dataclass(slots=True)
class CartItem:
    """Позиция корзины, собранная из CartInfo и актуальных данных товара."""

    id: int
    name: str
    quantity: int
    available: bool


@dataclass(slots=True)
class CartEntity:
    id: int
    items: list[CartItem]
    price: float

    @property
    def quantity(self) -> int:
        return sum(item.quantity for item in self.items)
