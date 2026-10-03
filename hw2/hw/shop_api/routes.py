from typing import Optional

from shop_api.contracts import Cart, Item, ItemCreate, ItemPatch
from fastapi import status, Response, Query, APIRouter, HTTPException
from shop_api.queries import (
    build_cart,
    carts,
    create_cart_id,
    create_item_id,
    get_cart_or_404,
    get_item_or_404,
    items,
)

router_cart = APIRouter(prefix="/cart")

@router_cart.post("/", status_code=status.HTTP_201_CREATED)
def create_cart(response: Response) -> dict[str, int]:
    cart_id = create_cart_id()
    carts[cart_id] = {}
    response.headers["Location"] = f"/cart/{cart_id}"

    return {"id": cart_id}

@router_cart.get("/{cart_id}", response_model=Cart)
def get_cart(cart_id: int) -> Cart:
    cart = get_cart_or_404(cart_id)
    return build_cart(cart_id, cart)


@router_cart.get("/", response_model=list[Cart])
def get_carts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
    min_quantity: Optional[int] = Query(default=None, ge=0),
    max_quantity: Optional[int] = Query(default=None, ge=0),
) -> list[Cart]:
    result: list[Cart] = []

    for cart_id, cart_data in carts.items():
        cart = build_cart(cart_id, cart_data)
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue

        total_quantity = sum(item.quantity for item in cart.items)

        if min_quantity is not None and total_quantity < min_quantity:
            continue
        if max_quantity is not None and total_quantity > max_quantity:
            continue
        result.append(cart)

    return result[offset : offset + limit]


@router_cart.post("/{cart_id}/add/{item_id}", response_model=Cart)
def add_item_to_cart(cart_id: int, item_id: int) -> Cart:
    cart = get_cart_or_404(cart_id)
    item = get_item_or_404(item_id)
    cart[item.id] = cart.get(item.id, 0) + 1

    return build_cart(cart_id, cart)

router_item = APIRouter(prefix="/item")

@router_item.post("/", response_model=Item, status_code=status.HTTP_201_CREATED)
def create_item(
    item_data: ItemCreate,
    response: Response,
) -> Item:
    item_id = create_item_id()

    item = Item(
        id=item_id,
        name=item_data.name,
        price=item_data.price,
        deleted=False,
    )
    items[item.id] = item
    response.headers["Location"] = f"/item/{item.id}"

    return item


@router_item.get("/{item_id}", response_model=Item)
def get_item(item_id: int) -> Item:
    return get_item_or_404(item_id)


@router_item.get("/", response_model=list[Item])
def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = False,
) -> list[Item]:
    result: list[Item] = []

    for item in items.values():
        if item.deleted and not show_deleted:
            continue
        if min_price is not None and item.price < min_price:
            continue
        if max_price is not None and item.price > max_price:
            continue
        result.append(item)

    return result[offset : offset + limit]


@router_item.put("/{item_id}", response_model=Item)
def replace_item(
    item_id: int,
    item_data: ItemCreate,
) -> Item:
    item = get_item_or_404(item_id)
    updated_item = Item(
        id=item.id,
        name=item_data.name,
        price=item_data.price,
        deleted=item.deleted,
    )
    items[item_id] = updated_item

    return updated_item


@router_item.patch("/{item_id}", response_model=Item)
def patch_item(
    item_id: int,
    item_data: ItemPatch,
) -> Response | Item:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    if item.deleted:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)
    update_data = item_data.model_dump(exclude_unset=True)
    updated_item = item.model_copy(update=update_data)
    items[item_id] = updated_item

    return updated_item


@router_item.delete("/{item_id}")
def delete_item(item_id: int) -> dict[str, bool]:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
    if not item.deleted:
        items[item_id] = item.model_copy(update={"deleted": True})

    return {"deleted": True}

