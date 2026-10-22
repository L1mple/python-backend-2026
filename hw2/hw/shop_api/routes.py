from fastapi import APIRouter, HTTPException, Query, Response, status

from .contracts import (
    CartCreateOut,
    CartOut,
    ItemCreateIn,
    ItemOut,
    ItemPatchIn,
    ItemPutIn,
)
from .store.models import Cart, CartItem
from .store import memory

router2 = APIRouter()


@router2.post("/item", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreateIn) -> ItemOut:
    item = payload.to_domain()
    item.id = next(memory.item_id_generator)
    memory.items[item.id] = item
    return ItemOut.from_domain(item)


@router2.get("/item/{item_id}", response_model=ItemOut)
def get_item(item_id: int) -> ItemOut:
    item = memory.items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(404, "item not found")
    return ItemOut.from_domain(item)


@router2.get("/item", response_model=list[ItemOut])
def list_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = Query(False),
) -> list[ItemOut]:
    all_items = list(memory.items.values())

    if not show_deleted:
        all_items = [i for i in all_items if not i.deleted]
    if min_price is not None:
        all_items = [i for i in all_items if i.price >= min_price]
    if max_price is not None:
        all_items = [i for i in all_items if i.price <= max_price]

    page = all_items[offset : offset + limit]

    return [ItemOut.from_domain(i) for i in page]


@router2.put("/item/{item_id}", response_model=ItemOut)
def replace_item(item_id: int, payload: ItemPutIn) -> ItemOut:
    existing = memory.items.get(item_id)
    if existing is None or existing.deleted:
        raise HTTPException(404, "item not found")

    existing.name = payload.name
    existing.price = payload.price
    return ItemOut.from_domain(existing)


@router2.patch("/item/{item_id}", response_model=ItemOut)
def patch_item(item_id: int, payload: ItemPatchIn) -> ItemOut | Response:
    item = memory.items.get(item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    if item.deleted:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    if "name" in payload.model_fields_set and payload.name is not None:
        item.name = payload.name
    if "price" in payload.model_fields_set and payload.price is not None:
        item.price = payload.price

    return ItemOut.from_domain(item)


@router2.delete("/item/{item_id}")
def delete_item(item_id: int) -> None:
    item = memory.items.get(item_id)
    if item is None:
        raise HTTPException(404, "item not found")
    item.deleted = True

@router2.post("/cart", response_model=CartCreateOut, status_code=status.HTTP_201_CREATED)
def create_cart(response: Response) -> CartCreateOut:
    cart = Cart(id=next(memory.cart_id_generator))
    memory.carts[cart.id] = cart
    response.headers["location"] = f"/cart/{cart.id}"
    return CartCreateOut(id=cart.id)


@router2.get("/cart/{cart_id}", response_model=CartOut)
def get_cart(cart_id: int) -> CartOut:
    cart = memory.carts.get(cart_id)
    if cart is None:
        raise HTTPException(404, "cart not found")
    return CartOut.from_domain(cart)


@router2.get("/cart", response_model=list[CartOut])
def list_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
) -> list[CartOut]:
    all_carts = list(memory.carts.values())

    if min_price is not None:
        all_carts = [c for c in all_carts if c.price >= min_price]
    if max_price is not None:
        all_carts = [c for c in all_carts if c.price <= max_price]

    if min_quantity is not None:
        all_carts = [
            c for c in all_carts if sum(i.quantity for i in c.items) >= min_quantity
        ]
    if max_quantity is not None:
        all_carts = [
            c for c in all_carts if sum(i.quantity for i in c.items) <= max_quantity
        ]

    page = all_carts[offset : offset + limit]

    return [CartOut.from_domain(c) for c in page]


@router2.post("/cart/{cart_id}/add/{item_id}", response_model=CartOut)
def add_item_to_cart(cart_id: int, item_id: int) -> CartOut:
    cart = memory.carts.get(cart_id)
    if cart is None:
        raise HTTPException(404, "cart not found")

    item = memory.items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(404, "item not found")
    for ci in cart.items:
        if ci.item_id == item_id:
            ci.quantity += 1
            ci.available = not item.deleted
            break
    else:
        cart.items.append(
            CartItem(
                item_id=item.id,
                name=item.name,
                quantity=1,
                available=not item.deleted,
            )
        )
    cart.price = sum(
        ci.quantity * memory.items[ci.item_id].price
        for ci in cart.items
        if ci.item_id in memory.items
    )

    return CartOut.from_domain(cart)