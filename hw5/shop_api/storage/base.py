from abc import ABC, abstractmethod

from shop_api.models import Item, Cart
from shop_api.schema import ItemFiltersSchema, CartFiltersSchema


class ItemRepository(ABC):
    @abstractmethod
    async def get(self, item_id: int) -> Item | None:
        ...

    @abstractmethod
    async def get_all(self, filters: ItemFiltersSchema) -> list[Item]:
        ...

    @abstractmethod
    async def add(self, item: Item) -> Item:
        """Сохраняет новый товар и проставляет ему id."""

    @abstractmethod
    async def save(self, item: Item) -> Item:
        ...

    @abstractmethod
    async def mark_deleted(self, item_id: int) -> None:
        ...


class CartRepository(ABC):
    @abstractmethod
    async def get(self, cart_id: int) -> Cart | None:
        ...

    @abstractmethod
    async def get_all(self, filters: CartFiltersSchema) -> list[Cart]:
        ...

    @abstractmethod
    async def add(self) -> Cart:
        """Создает пустую корзину."""

    @abstractmethod
    async def add_item(self, cart_id: int, item_id: int) -> None:
        """Добавляет товар в корзину, если он уже есть — увеличивает количество."""
