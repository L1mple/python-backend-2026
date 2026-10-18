from dataclasses import dataclass, field


@dataclass(slots=True)
class ItemInfo:
    """Информация о товаре без id (то, что задаёт пользователь)."""

    name: str
    price: float


@dataclass(slots=True)
class ItemEntity:
    """Товар как он хранится в нашей 'базе'."""

    id: int
    info: ItemInfo
    deleted: bool = False


@dataclass(slots=True)
class PatchItemInfo:
    """Данные для частичного обновления товара — все поля опциональны."""

    name: str | None = None
    price: float | None = None


@dataclass(slots=True)
class CartItemInfo:
    """Позиция в корзине: id товара + количество."""

    item_id: int
    quantity: int


@dataclass(slots=True)
class CartEntity:
    """Корзина как она хранится в нашей 'базе'."""

    id: int
    items: list[CartItemInfo] = field(default_factory=list)
