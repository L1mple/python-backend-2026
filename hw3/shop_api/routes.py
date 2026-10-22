from fastapi import APIRouter, HTTPException, Query, status

from .contracts import (
    CartCreateOut,
    CartListOut,
    CartOut,
    ItemCreateIn,
    ItemListOut,
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


@router2.get("/item", response_model=ItemListOut)
def list_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = Query(False),
) -> ItemListOut:
    all_items = list(memory.items.values())

    if not show_deleted:
        all_items = [i for i in all_items if not i.deleted]
    if min_price is not None:
        all_items = [i for i in all_items if i.price >= min_price]
    if max_price is not None:
        all_items = [i for i in all_items if i.price <= max_price]

    total = len(all_items)
    page = all_items[offset : offset + limit]

    return ItemListOut(
        items=[ItemOut.from_domain(i) for i in page],
        total=total,
    )


@router2.put("/item/{item_id}", response_model=ItemOut)
def replace_item(item_id: int, payload: ItemPutIn) -> ItemOut:
    existing = memory.items.get(item_id)
    if existing is None or existing.deleted:
        raise HTTPException(404, "item not found")

    existing.name = payload.name
    existing.price = payload.price
    return ItemOut.from_domain(existing)


@router2.patch("/item/{item_id}", response_model=ItemOut)
def patch_item(item_id: int, payload: ItemPatchIn) -> ItemOut:
    item = memory.items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(404, "item not found")

    if "name" in payload.model_fields_set:
        item.name = payload.name or ""
    if "price" in payload.model_fields_set:
        item.price = payload.price or 0.0

    return ItemOut.from_domain(item)


@router2.delete("/item/{item_id}", status_code=status.HTTP_200_OK)
def delete_item(item_id: int) -> None:
    item = memory.items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(404, "item not found")
    item.deleted = True

@router2.post("/cart", response_model=CartCreateOut, status_code=status.HTTP_201_CREATED)
def create_cart() -> CartCreateOut:
    cart = Cart(id=next(memory.cart_id_generator))
    memory.carts[cart.id] = cart
    return CartCreateOut(id=cart.id)


@router2.get("/cart/{cart_id}", response_model=CartOut)
def get_cart(cart_id: int) -> CartOut:
    cart = memory.carts.get(cart_id)
    if cart is None:
        raise HTTPException(404, "cart not found")
    return CartOut.from_domain(cart)


@router2.get("/cart", response_model=CartListOut)
def list_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
) -> CartListOut:
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

    total = len(all_carts)
    page = all_carts[offset : offset + limit]

    return CartListOut(
        items=[CartOut.from_domain(c) for c in page],
        total=total,
    )


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