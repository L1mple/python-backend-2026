"""In-memory REST API for the homework shop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field


app = FastAPI(title="Shop API")


class ItemCreate(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(gt=0)


class ItemUpdate(ItemCreate):
    """A complete replacement has the same required fields as creation."""


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1)
    price: Optional[float] = Field(default=None, gt=0)


class ItemResponse(ItemCreate):
    id: int
    deleted: bool = False


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float


@dataclass
class StoredItem:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass
class StoredCart:
    id: int
    quantities: dict[int, int] = field(default_factory=dict)


items: dict[int, StoredItem] = {}
carts: dict[int, StoredCart] = {}
next_item_id = 1
next_cart_id = 1


def get_item_or_404(item_id: int, *, include_deleted: bool = False) -> StoredItem:
    item = items.get(item_id)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


def get_cart_or_404(cart_id: int) -> StoredCart:
    cart = carts.get(cart_id)
    if cart is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    return cart


def item_response(item: StoredItem) -> ItemResponse:
    return ItemResponse(id=item.id, name=item.name, price=item.price, deleted=item.deleted)


def cart_response(cart: StoredCart) -> CartResponse:
    cart_items: list[CartItemResponse] = []
    total_price = 0.0
    for item_id, quantity in cart.quantities.items():
        item = items[item_id]
        cart_items.append(CartItemResponse(id=item.id, name=item.name, quantity=quantity, available=not item.deleted))
        total_price += item.price * quantity
    return CartResponse(id=cart.id, items=cart_items, price=total_price)


@app.post("/cart", status_code=status.HTTP_201_CREATED)
def create_cart(response: Response) -> dict[str, int]:
    global next_cart_id
    cart = StoredCart(id=next_cart_id)
    carts[cart.id] = cart
    next_cart_id += 1
    response.headers["Location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}", response_model=CartResponse)
def get_cart(cart_id: int) -> CartResponse:
    return cart_response(get_cart_or_404(cart_id))


@app.get("/cart", response_model=list[CartResponse])
def list_carts(
    offset: int = Query(default=0, ge=0), limit: int = Query(default=10, gt=0),
    min_price: Optional[float] = Query(default=None, ge=0), max_price: Optional[float] = Query(default=None, ge=0),
    min_quantity: Optional[int] = Query(default=None, ge=0), max_quantity: Optional[int] = Query(default=None, ge=0),
) -> list[CartResponse]:
    result = [cart_response(cart) for cart in carts.values()]
    if min_price is not None:
        result = [cart for cart in result if cart.price >= min_price]
    if max_price is not None:
        result = [cart for cart in result if cart.price <= max_price]
    if min_quantity is not None:
        result = [cart for cart in result if sum(item.quantity for item in cart.items) >= min_quantity]
    if max_quantity is not None:
        result = [cart for cart in result if sum(item.quantity for item in cart.items) <= max_quantity]
    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}", response_model=CartResponse)
def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    cart = get_cart_or_404(cart_id)
    get_item_or_404(item_id)
    cart.quantities[item_id] = cart.quantities.get(item_id, 0) + 1
    return cart_response(cart)


@app.post("/item", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, response: Response) -> ItemResponse:
    global next_item_id
    item = StoredItem(id=next_item_id, name=payload.name, price=payload.price)
    items[item.id] = item
    next_item_id += 1
    response.headers["Location"] = f"/item/{item.id}"
    return item_response(item)


@app.get("/item/{item_id}", response_model=ItemResponse)
def get_item(item_id: int) -> ItemResponse:
    return item_response(get_item_or_404(item_id))


@app.get("/item", response_model=list[ItemResponse])
def list_items(
    offset: int = Query(default=0, ge=0), limit: int = Query(default=10, gt=0),
    min_price: Optional[float] = Query(default=None, ge=0), max_price: Optional[float] = Query(default=None, ge=0),
    show_deleted: bool = False,
) -> list[ItemResponse]:
    result = list(items.values())
    if not show_deleted:
        result = [item for item in result if not item.deleted]
    if min_price is not None:
        result = [item for item in result if item.price >= min_price]
    if max_price is not None:
        result = [item for item in result if item.price <= max_price]
    return [item_response(item) for item in result[offset : offset + limit]]


@app.put("/item/{item_id}", response_model=ItemResponse)
def replace_item(item_id: int, payload: ItemUpdate) -> ItemResponse:
    item = get_item_or_404(item_id)
    item.name, item.price = payload.name, payload.price
    return item_response(item)


@app.patch("/item/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, payload: ItemPatch) -> ItemResponse:
    item = get_item_or_404(item_id, include_deleted=True)
    if item.deleted:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        item.name = changes["name"]
    if "price" in changes:
        item.price = changes["price"]
    return item_response(item)


@app.delete("/item/{item_id}", status_code=status.HTTP_200_OK)
def delete_item(item_id: int) -> dict[str, int]:
    item = get_item_or_404(item_id, include_deleted=True)
    item.deleted = True
    return {"id": item.id}
