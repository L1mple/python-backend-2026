from random import choices
from string import ascii_lowercase

from fastapi import WebSocket

from shop_api.exceptions import NotFoundError
from shop_api.models import Item, Cart, FullCart, CartItem
from shop_api.schema import (
    ItemFiltersSchema, CartFiltersSchema,
    ItemSchema, ItemCreateSchema, ItemPatchSchema,
    CartSchema, CartItemSchema,
)
from shop_api.storage import Store


class ItemService:
    def __init__(self, store: Store):
        self._store = store

    @staticmethod
    def _to_schema(item: Item) -> ItemSchema:
        return ItemSchema(
            id=item.id,
            name=item.name,
            price=item.price,
            deleted=item.deleted,
        )

    def _get_item_or_not_found(self, item_id: int) -> Item:
        item = self._store.items.get(item_id)
        if not item or item.deleted:
            raise NotFoundError
        return item

    def get_all(self, filters: ItemFiltersSchema) -> list[ItemSchema]:
        filtered = sorted(self._store.items.get_all(), key=lambda item: item.id)

        if not filters.show_deleted:
            filtered = (item for item in filtered if item.deleted == filters.show_deleted)

        if filters.min_price is not None:
            filtered = [item for item in filtered if item.price >= filters.min_price]
        if filters.max_price is not None:
            filtered = [item for item in filtered if item.price <= filters.max_price]

        page = list(filtered)[filters.offset:filters.offset + filters.limit]
        return [self._to_schema(item) for item in page]

    def get_item(self, item_id: int) -> ItemSchema:
        item = self._get_item_or_not_found(item_id)
        return self._to_schema(item)

    def create_item(self, item: ItemCreateSchema) -> ItemSchema:
        item = Item(id=0, name=item.name, price=item.price)
        item = self._store.items.add(item)
        return self._to_schema(item)

    def update_item(self, item_id: int, new_item: ItemCreateSchema | ItemPatchSchema) -> ItemSchema:
        old_item = self._get_item_or_not_found(item_id)
        if new_item.name:
            old_item.name = new_item.name
        if new_item.price:
            old_item.price = new_item.price
        item = self._store.items.set(old_item)
        return self._to_schema(item)

    def delete_item(self, item_id: int) -> None:
        self._store.items.remove(item_id)


class CartService:
    def __init__(self, store: Store):
        self._store = store

    def _to_full(self, cart: Cart) -> FullCart:
        cart_items = []
        total_price = 0.0
        total_quantity = 0
        for item_id, amount in cart.items.items():
            item = self._store.items.get(item_id)
            if not item:
                continue
            cart_items.append(CartItem(
                id=item.id,
                name=item.name,
                available=not item.deleted,
                quantity=amount,
            ))
            total_price += item.price * amount
            total_quantity += amount
        return FullCart(
            id=cart.id,
            items=cart_items,
            price=total_price,
            quantity=total_quantity,
        )

    @staticmethod
    def _to_schema(cart: FullCart) -> CartSchema:
        return CartSchema(
            id=cart.id,
            items=[CartItemSchema(
                id=item.id,
                name=item.name,
                quantity=item.quantity,
                available=item.available,
            ) for item in cart.items],
            price=cart.price,
        )

    def _get_cart_or_not_found(self, cart_id: int) -> Cart:
        cart = self._store.carts.get(cart_id)
        if not cart:
            raise NotFoundError
        return cart

    def _get_item_or_not_found(self, item_id: int) -> Item:
        item = self._store.items.get(item_id)
        if not item or item.deleted:
            raise NotFoundError
        return item

    def get_all(self, filters: CartFiltersSchema) -> list[CartSchema]:
        filtered = sorted(
            map(self._to_full, self._store.carts.get_all()),
            key=lambda cart: cart.id
        )

        if filters.min_price is not None:
            filtered = [cart for cart in filtered if cart.price >= filters.min_price]
        if filters.max_price is not None:
            filtered = [cart for cart in filtered if cart.price <= filters.max_price]

        if filters.min_quantity is not None:
            filtered = [cart for cart in filtered if cart.quantity >= filters.min_quantity]
        if filters.max_quantity is not None:
            filtered = [cart for cart in filtered if cart.quantity <= filters.max_quantity]

        page = list(filtered)[filters.offset:filters.offset + filters.limit]
        return [self._to_schema(cart) for cart in page]

    def get_cart(self, cart_id: int) -> CartSchema:
        cart = self._get_cart_or_not_found(cart_id)
        full_cart = self._to_full(cart)
        return self._to_schema(full_cart)

    def create_cart(self) -> CartSchema:
        cart = Cart(0, {})
        cart = self._store.carts.add(cart)
        full_cart = self._to_full(cart)
        return self._to_schema(full_cart)

    def add_item(self, cart_id: int, item_id: int) -> CartSchema:
        cart = self._get_cart_or_not_found(cart_id)
        self._get_item_or_not_found(item_id)
        cart.items[item_id] = cart.items.get(item_id, 0) + 1
        full_cart = self._to_full(cart)
        return self._to_schema(full_cart)


class ChatService:
    _chats: dict[str, list[WebSocket]]

    def __init__(self):
        self._chats = {}

    @staticmethod
    def generate_username() -> str:
        return ''.join(choices(ascii_lowercase, k=10))


    async def subscribe(self, chat_name: str, ws: WebSocket):
        await ws.accept()
        if chat_name not in self._chats:
            self._chats[chat_name] = []
        self._chats[chat_name].append(ws)

    def unsubscribe(self, chat_name: str, ws: WebSocket):
        if chat_name in self._chats:
            self._chats[chat_name].remove(ws)

    async def publish(self, chat_name, username, message):
        if chat_name not in self._chats:
            return
        for ws in self._chats[chat_name]:
            await ws.send_text(f'{username} :: {message}')




