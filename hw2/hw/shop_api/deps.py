from typing import Annotated

from fastapi import Depends
from starlette.requests import Request

from shop_api.service import ItemService, CartService
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
