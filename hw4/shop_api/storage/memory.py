from dataclasses import replace

from shop_api.exceptions import NotFoundError
from shop_api.models import Item, Cart, CartItem
from shop_api.schema import ItemFiltersSchema, CartFiltersSchema
from shop_api.storage.base import ItemRepository, CartRepository


class BaseStore[T]:
    _data: dict[int, T]
    _last_id: int

    def __init__(self, data: dict[int, T] | None = None):
        self._data = data or {}
        self._last_id = max(map(int, self._data.keys()), default=0)

    def _get_next_id(self) -> int:
        self._last_id += 1
        return self._last_id

    def get_all(self) -> list[T]:
        return list(self._data.values())

    def get_all_with_ids(self) -> list[tuple[int, T]]:
        return list(self._data.items())

    def get(self, obj_id: int) -> T | None:
        return self._data.get(obj_id)

    def add(self, obj: T) -> int:
        obj_id = self._get_next_id()
        self.set(obj_id, obj)
        return obj_id

    def set(self, obj_id: int, obj: T) -> None:
        self._data[obj_id] = obj


class Store:
    """Общие данные для in-memory репозиториев: товары и содержимое корзин {item_id: quantity}."""

    def __init__(self):
        self.items = BaseStore[Item]()
        self.carts = BaseStore[dict[int, int]]()


class InMemoryItemRepository(ItemRepository):
    def __init__(self, store: Store):
        self._store = store

    async def get(self, item_id: int) -> Item | None:
        item = self._store.items.get(item_id)
        return replace(item) if item else None

    async def get_all(self, filters: ItemFiltersSchema) -> list[Item]:
        filtered = sorted(self._store.items.get_all(), key=lambda item: item.id)

        if not filters.show_deleted:
            filtered = [item for item in filtered if not item.deleted]
        if filters.min_price is not None:
            filtered = [item for item in filtered if item.price >= filters.min_price]
        if filters.max_price is not None:
            filtered = [item for item in filtered if item.price <= filters.max_price]

        page = filtered[filters.offset:filters.offset + filters.limit]
        return [replace(item) for item in page]

    async def add(self, item: Item) -> Item:
        stored = replace(item)
        item.id = stored.id = self._store.items.add(stored)
        return item

    async def save(self, item: Item) -> Item:
        self._store.items.set(item.id, replace(item))
        return item

    async def mark_deleted(self, item_id: int) -> None:
        item = self._store.items.get(item_id)
        if item:
            item.deleted = True


class InMemoryCartRepository(CartRepository):
    def __init__(self, store: Store):
        self._store = store

    def _to_model(self, cart_id: int, content: dict[int, int]) -> Cart:
        cart = Cart(id=cart_id)
        for item_id, quantity in sorted(content.items()):
            item = self._store.items.get(item_id)
            if not item:
                continue
            cart.items.append(CartItem(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            ))
            cart.price += item.price * quantity
            cart.quantity += quantity
        return cart

    async def get(self, cart_id: int) -> Cart | None:
        content = self._store.carts.get(cart_id)
        return self._to_model(cart_id, content) if content is not None else None

    async def get_all(self, filters: CartFiltersSchema) -> list[Cart]:
        filtered = sorted(
            (self._to_model(cart_id, content) for cart_id, content in self._store.carts.get_all_with_ids()),
            key=lambda cart: cart.id,
        )

        if filters.min_price is not None:
            filtered = [cart for cart in filtered if cart.price >= filters.min_price]
        if filters.max_price is not None:
            filtered = [cart for cart in filtered if cart.price <= filters.max_price]
        if filters.min_quantity is not None:
            filtered = [cart for cart in filtered if cart.quantity >= filters.min_quantity]
        if filters.max_quantity is not None:
            filtered = [cart for cart in filtered if cart.quantity <= filters.max_quantity]

        return filtered[filters.offset:filters.offset + filters.limit]

    async def add(self) -> Cart:
        cart_id = self._store.carts.add({})
        return Cart(id=cart_id)

    async def add_item(self, cart_id: int, item_id: int) -> None:
        content = self._store.carts.get(cart_id)
        if content is None:
            raise NotFoundError
        content[item_id] = content.get(item_id, 0) + 1
