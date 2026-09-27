from typing import Annotated

from fastapi import Depends, Request, WebSocket

from shop_api.service import ItemService, CartService, ChatService
from shop_api.storage import Store


def get_storage(request: Request) -> Store:
    return request.app.state.store


type StoreDep = Annotated[Store, Depends(get_storage)]


def get_item_service(store: StoreDep) -> ItemService:
    return ItemService(store)


type ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]


def get_cart_service(store: StoreDep) -> CartService:
    return CartService(store)


type CartServiceDep = Annotated[CartService, Depends(get_cart_service)]


def get_chat_service(websocket: WebSocket) -> ChatService:
    if not hasattr(websocket.app.state, 'chat_service'):
        websocket.app.state.chat_service = ChatService()
    return websocket.app.state.chat_service


type ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
