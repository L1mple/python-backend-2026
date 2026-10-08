from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from http import HTTPStatus
from typing import Annotated, Protocol

from fastapi import FastAPI, HTTPException, Query, Response
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, ConfigDict, Field


@dataclass(slots=True)
class Item:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass(slots=True)
class CartItem:
    id: int
    name: str
    quantity: int
    available: bool = True


@dataclass(slots=True)
class Cart:
    id: int
    items: dict[int, CartItem]
    price: float

    @property
    def quantity(self) -> int:
        return sum(item.quantity for item in self.items.values())


class ItemClient(BaseModel):
    name: str
    price: float


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = None


@dataclass(slots=True)
class CartResponse:
    id: int
    items: list[CartItem]
    price: float

    @classmethod
    def from_cart(cls, cart: Cart) -> "CartResponse":
        return cls(id=cart.id, items=list(cart.items.values()), price=cart.price)


class ListParams(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(10, gt=0)
    min_price: float | None = Field(None, ge=0)
    max_price: float | None = Field(None, ge=0)


class CartListParams(ListParams):
    min_quantity: int | None = Field(None, ge=0)
    max_quantity: int | None = Field(None, ge=0)


class ItemListParams(ListParams):
    show_deleted: bool = False


class HasPrice(Protocol):
    price: float


def apply_list_params[T: HasPrice](objs: Iterable[T], params: ListParams) -> list[T]:
    filtered = [
        o
        for o in objs
        if (params.min_price is None or o.price >= params.min_price)
        and (params.max_price is None or o.price <= params.max_price)
    ]
    return filtered[params.offset : params.offset + params.limit]


def int_id_generator() -> Iterator[int]:
    i = 0
    while True:
        yield i
        i += 1


_id_generator = int_id_generator()

carts: dict[int, Cart] = {}
items: dict[int, Item] = {}

app = FastAPI(title="Shop API")
Instrumentator().instrument(app).expose(app)


@app.post("/cart", status_code=HTTPStatus.CREATED)
async def post_cart(response: Response):
    _id = next(_id_generator)
    carts[_id] = Cart(_id, {}, 0.0)
    response.headers["Location"] = f"/cart/{_id}"
    return carts[_id]


@app.get("/cart/{id}", status_code=HTTPStatus.OK)
async def get_cart(id: int):
    return CartResponse.from_cart(carts[id])


@app.get("/cart")
async def get_cart_list(
    params: Annotated[CartListParams, Query()],
) -> list[CartResponse]:
    result = [
        c
        for c in carts.values()
        if (params.min_quantity is None or c.quantity >= params.min_quantity)
        and (params.max_quantity is None or c.quantity <= params.max_quantity)
    ]
    return [CartResponse.from_cart(c) for c in apply_list_params(result, params)]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int):
    cart = carts[cart_id]
    item = items[item_id]
    if item_id not in cart.items:
        cart.items[item_id] = CartItem(id=item_id, name=item.name, quantity=0)
    cart.items[item_id].quantity += 1
    cart.price += item.price


@app.post("/item", status_code=HTTPStatus.CREATED)
async def post_item(item: ItemClient):
    _id = next(_id_generator)
    items[_id] = Item(_id, item.name, item.price)
    return items[_id]


@app.get("/item/{id}", status_code=HTTPStatus.OK)
async def get_item(id: int):
    item = items.get(id)
    if item is None or item.deleted:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    return item


@app.get("/item")
async def get_item_list(params: Annotated[ItemListParams, Query()]) -> list[Item]:
    result = [i for i in items.values() if params.show_deleted or not i.deleted]
    return apply_list_params(result, params)


@app.put("/item/{id}", status_code=HTTPStatus.OK)
async def put_item(id: int, item: ItemClient):
    if id in items:
        return Item(id, name=item.name, price=item.price, deleted=items[id].deleted)
    raise HTTPException(status_code=HTTPStatus.NOT_FOUND)


@app.patch("/item/{id}", status_code=HTTPStatus.OK)
async def patch_item(id: int, body: ItemPatch):
    item = items.get(id)
    if item is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price
    return item


@app.delete("/item/{id}", status_code=HTTPStatus.OK)
async def delete_item(id: int):
    if id in items:
        items[id].deleted = True
        return
    raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
