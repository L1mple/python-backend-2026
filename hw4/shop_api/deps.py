from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from shop_api.config import STORAGE_BACKEND
from shop_api.database import session_factory
from shop_api.service import ItemService, CartService, ChatService
from shop_api.storage import (
    ItemRepository, CartRepository, Store,
    InMemoryItemRepository, InMemoryCartRepository,
    SqlItemRepository, SqlCartRepository,
)


def get_store(request: Request) -> Store:
    if not hasattr(request.app.state, 'store'):
        request.app.state.store = Store()
    return request.app.state.store


async def get_session() -> AsyncIterator[AsyncSession | None]:
    if STORAGE_BACKEND == 'memory':
        yield None
        return
    async with session_factory() as session:
        yield session


type SessionDep = Annotated[AsyncSession | None, Depends(get_session)]


def get_item_repository(request: Request, session: SessionDep) -> ItemRepository:
    if session is None:
        return InMemoryItemRepository(get_store(request))
    return SqlItemRepository(session)


type ItemRepositoryDep = Annotated[ItemRepository, Depends(get_item_repository)]


def get_cart_repository(request: Request, session: SessionDep) -> CartRepository:
    if session is None:
        return InMemoryCartRepository(get_store(request))
    return SqlCartRepository(session)


type CartRepositoryDep = Annotated[CartRepository, Depends(get_cart_repository)]


def get_item_service(items: ItemRepositoryDep) -> ItemService:
    return ItemService(items)


type ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]


def get_cart_service(carts: CartRepositoryDep, items: ItemRepositoryDep) -> CartService:
    return CartService(carts, items)


type CartServiceDep = Annotated[CartService, Depends(get_cart_service)]


def get_chat_service(websocket: WebSocket) -> ChatService:
    if not hasattr(websocket.app.state, 'chat_service'):
        websocket.app.state.chat_service = ChatService()
    return websocket.app.state.chat_service


type ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
