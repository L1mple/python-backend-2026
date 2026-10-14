from itertools import count
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response, status

from .chat import router as chat_router
from .models import Cart, CartFilters, CartItem, Item, ItemData, ItemFilters, ItemPatch

app = FastAPI(title="Shop API")
app.include_router(chat_router)

items: dict[int, Item] = {}
carts: dict[int, dict[int, int]] = {}
item_ids = count(1)
cart_ids = count(1)


def find_item(item_id: int) -> Item:
    item = items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return item


def build_cart(cart_id: int) -> Cart:
    if cart_id not in carts:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found")
    cart_items = []
    price = 0.0
    for item_id, quantity in carts[cart_id].items():
        item = items[item_id]
        cart_items.append(
            CartItem(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )
        # Deleted items stay visible in the cart but do not contribute to its price.
        if not item.deleted:
            price += item.price * quantity
    return Cart(id=cart_id, items=cart_items, price=price)


@app.post("/item", status_code=status.HTTP_201_CREATED)
async def create_item(data: ItemData, response: Response) -> Item:
    item = Item(id=next(item_ids), **data.model_dump())
    items[item.id] = item
    response.headers["Location"] = f"/item/{item.id}"
    return item


@app.get("/item")
async def list_items(filters: Annotated[ItemFilters, Query()]) -> list[Item]:
    filtered = [
        item
        for item in items.values()
        if (filters.show_deleted or not item.deleted)
        and (filters.min_price is None or item.price >= filters.min_price)
        and (filters.max_price is None or item.price <= filters.max_price)
    ]
    return filtered[filters.offset : filters.offset + filters.limit]


@app.get("/item/{item_id}")
async def get_item(item_id: int) -> Item:
    return find_item(item_id)


@app.put("/item/{item_id}")
async def replace_item(item_id: int, data: ItemData) -> Item:
    find_item(item_id)
    item = Item(id=item_id, **data.model_dump())
    items[item_id] = item
    return item


@app.patch("/item/{item_id}", response_model=Item)
async def patch_item(item_id: int, data: ItemPatch) -> Item | Response:
    item = items.get(item_id)
    if item is None or item.deleted:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)
    item = item.model_copy(update=data.model_dump(exclude_unset=True))
    items[item_id] = item
    return item


@app.delete("/item/{item_id}")
async def delete_item(item_id: int) -> Response:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    item.deleted = True
    return Response(status_code=status.HTTP_200_OK)


@app.post("/cart", status_code=status.HTTP_201_CREATED)
async def create_cart(response: Response) -> dict[str, int]:
    cart_id = next(cart_ids)
    carts[cart_id] = {}
    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart")
async def list_carts(filters: Annotated[CartFilters, Query()]) -> list[Cart]:
    filtered = []
    for cart_id in carts:
        cart = build_cart(cart_id)
        quantity = sum(item.quantity for item in cart.items)
        if (
            (filters.min_price is None or cart.price >= filters.min_price)
            and (filters.max_price is None or cart.price <= filters.max_price)
            and (filters.min_quantity is None or quantity >= filters.min_quantity)
            and (filters.max_quantity is None or quantity <= filters.max_quantity)
        ):
            filtered.append(cart)
    return filtered[filters.offset : filters.offset + filters.limit]


@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int) -> Cart:
    return build_cart(cart_id)


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_to_cart(cart_id: int, item_id: int) -> Cart:
    if cart_id not in carts:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found")
    find_item(item_id)
    cart = carts[cart_id]
    cart[item_id] = cart.get(item_id, 0) + 1
    return build_cart(cart_id)
