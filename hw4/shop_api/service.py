from random import choices
from string import ascii_lowercase

from fastapi import WebSocket

from shop_api.exceptions import NotFoundError
from shop_api.models import Item, Cart
from shop_api.schema import (
    ItemFiltersSchema, CartFiltersSchema,
    ItemSchema, ItemCreateSchema, ItemPatchSchema,
    CartSchema, CartItemSchema,
)
from shop_api.storage import ItemRepository, CartRepository


class ItemService:
    def __init__(self, items: ItemRepository):
        self._items = items

    @staticmethod
    def _to_schema(item: Item) -> ItemSchema:
        return ItemSchema(
            id=item.id,
            name=item.name,
            price=item.price,
            deleted=item.deleted,
        )

    async def _get_item_or_not_found(self, item_id: int) -> Item:
        item = await self._items.get(item_id)
        if not item or item.deleted:
            raise NotFoundError
        return item

    async def get_all(self, filters: ItemFiltersSchema) -> list[ItemSchema]:
        items = await self._items.get_all(filters)
        return [self._to_schema(item) for item in items]

    async def get_item(self, item_id: int) -> ItemSchema:
        item = await self._get_item_or_not_found(item_id)
        return self._to_schema(item)

    async def create_item(self, item: ItemCreateSchema) -> ItemSchema:
        created = await self._items.add(Item(id=0, name=item.name, price=item.price))
        return self._to_schema(created)

    async def update_item(self, item_id: int, new_item: ItemCreateSchema | ItemPatchSchema) -> ItemSchema:
        item = await self._get_item_or_not_found(item_id)
        if new_item.name is not None:
            item.name = new_item.name
        if new_item.price is not None:
            item.price = new_item.price
        item = await self._items.save(item)
        return self._to_schema(item)

    async def delete_item(self, item_id: int) -> None:
        await self._items.mark_deleted(item_id)


class CartService:
    def __init__(self, carts: CartRepository, items: ItemRepository):
        self._carts = carts
        self._items = items

    @staticmethod
    def _to_schema(cart: Cart) -> CartSchema:
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

    async def _get_cart_or_not_found(self, cart_id: int) -> Cart:
        cart = await self._carts.get(cart_id)
        if not cart:
            raise NotFoundError
        return cart

    async def _get_item_or_not_found(self, item_id: int) -> Item:
        item = await self._items.get(item_id)
        if not item or item.deleted:
            raise NotFoundError
        return item

    async def get_all(self, filters: CartFiltersSchema) -> list[CartSchema]:
        carts = await self._carts.get_all(filters)
        return [self._to_schema(cart) for cart in carts]

    async def get_cart(self, cart_id: int) -> CartSchema:
        cart = await self._get_cart_or_not_found(cart_id)
        return self._to_schema(cart)

    async def create_cart(self) -> CartSchema:
        cart = await self._carts.add()
        return self._to_schema(cart)

    async def add_item(self, cart_id: int, item_id: int) -> CartSchema:
        await self._get_cart_or_not_found(cart_id)
        await self._get_item_or_not_found(item_id)
        await self._carts.add_item(cart_id, item_id)
        return await self.get_cart(cart_id)


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
