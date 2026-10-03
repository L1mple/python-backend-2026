from fastapi import (
    FastAPI,
    Depends,
    status,
    Response,
    HTTPException,
    Query,
)
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Item, Cart, CartItem
from .schemas import (
    ItemCreate,
    ItemResponse,
    ItemPatch,
    CartResponse,
    CartItemResponse,
)


app = FastAPI(title="Shop API")


def get_db():
    db: Session = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# ============================================================
# ITEM
# ============================================================


@app.post(
    "/item",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    item: ItemCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    new_item = Item(
        name=item.name,
        price=item.price,
    )

    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    response.headers["Location"] = f"/item/{new_item.id}"

    return new_item


@app.get(
    "/item/{item_id}",
    response_model=ItemResponse,
)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)

    if item is None or item.deleted:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    return item


@app.get(
    "/item",
    response_model=list[ItemResponse],
)
def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Item)

    if not show_deleted:
        query = query.filter(Item.deleted == False)

    if min_price is not None:
        query = query.filter(Item.price >= min_price)

    if max_price is not None:
        query = query.filter(Item.price <= max_price)

    items = (
        query
        .offset(offset)
        .limit(limit)
        .all()
    )

    return items


@app.put(
    "/item/{item_id}",
    response_model=ItemResponse,
)
def update_item(
    item_id: int,
    item_data: ItemCreate,
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    item.name = item_data.name
    item.price = item_data.price

    db.commit()
    db.refresh(item)

    return item


@app.patch(
    "/item/{item_id}",
    response_model=ItemResponse,
)
def patch_item(
    item_id: int,
    item_data: ItemPatch,
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    if item.deleted:
        return Response(status_code=304)

    if item_data.name is not None:
        item.name = item_data.name

    if item_data.price is not None:
        item.price = item_data.price

    db.commit()
    db.refresh(item)

    return item


@app.delete("/item/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    item.deleted = True

    db.commit()

    return {"id": item.id}


# ============================================================
# CART
# ============================================================


@app.post(
    "/cart",
    status_code=status.HTTP_201_CREATED,
)
def create_cart(
    response: Response,
    db: Session = Depends(get_db),
):
    cart = Cart()

    db.add(cart)
    db.commit()
    db.refresh(cart)

    response.headers["Location"] = f"/cart/{cart.id}"

    return {"id": cart.id}


@app.get(
    "/cart/{cart_id}",
    response_model=CartResponse,
)
def get_cart(
    cart_id: int,
    db: Session = Depends(get_db),
):
    cart = db.get(Cart, cart_id)

    if cart is None:
        raise HTTPException(
            status_code=404,
            detail="Cart not found",
        )

    cart_items = (
        db.query(CartItem, Item)
        .join(Item, CartItem.item_id == Item.id)
        .filter(CartItem.cart_id == cart_id)
        .all()
    )

    items = []
    total_price = 0.0

    for cart_item, item in cart_items:
        available = not item.deleted

        if available:
            total_price += float(item.price) * cart_item.quantity

        items.append(
            CartItemResponse(
                id=item.id,
                name=item.name,
                quantity=cart_item.quantity,
                available=available,
            )
        )

    return CartResponse(
        id=cart.id,
        items=items,
        price=total_price,
    )


@app.get(
    "/cart",
    response_model=list[CartResponse],
)
def get_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
):
    carts = (
        db.query(Cart)
        .offset(offset)
        .limit(limit)
        .all()
    )

    result = []

    for cart in carts:
        cart_items = (
            db.query(CartItem, Item)
            .join(Item, CartItem.item_id == Item.id)
            .filter(CartItem.cart_id == cart.id)
            .all()
        )

        items = []
        total_price = 0.0
        total_quantity = 0

        for cart_item, item in cart_items:
            available = not item.deleted

            total_quantity += cart_item.quantity

            if available:
                total_price += (
                    float(item.price) * cart_item.quantity
                )

            items.append(
                CartItemResponse(
                    id=item.id,
                    name=item.name,
                    quantity=cart_item.quantity,
                    available=available,
                )
            )

        if min_price is not None and total_price < min_price:
            continue

        if max_price is not None and total_price > max_price:
            continue

        if (
            min_quantity is not None
            and total_quantity < min_quantity
        ):
            continue

        if (
            max_quantity is not None
            and total_quantity > max_quantity
        ):
            continue

        result.append(
            CartResponse(
                id=cart.id,
                items=items,
                price=total_price,
            )
        )

    return result


@app.post(
    "/cart/{cart_id}/add/{item_id}",
    response_model=CartResponse,
)
def add_item_to_cart(
    cart_id: int,
    item_id: int,
    db: Session = Depends(get_db),
):
    cart = db.get(Cart, cart_id)

    if cart is None:
        raise HTTPException(
            status_code=404,
            detail="Cart not found",
        )

    item = db.get(Item, item_id)

    if item is None or item.deleted:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    cart_item = (
        db.query(CartItem)
        .filter(
            CartItem.cart_id == cart_id,
            CartItem.item_id == item_id,
        )
        .first()
    )

    if cart_item is None:
        cart_item = CartItem(
            cart_id=cart_id,
            item_id=item_id,
            quantity=1,
        )
        db.add(cart_item)
    else:
        cart_item.quantity += 1

    db.commit()

    cart_items = (
        db.query(CartItem, Item)
        .join(Item, CartItem.item_id == Item.id)
        .filter(CartItem.cart_id == cart_id)
        .all()
    )

    items = []
    total_price = 0.0

    for cart_item, item in cart_items:
        available = not item.deleted

        if available:
            total_price += float(item.price) * cart_item.quantity

        items.append(
            CartItemResponse(
                id=item.id,
                name=item.name,
                quantity=cart_item.quantity,
                available=available,
            )
        )

    return CartResponse(
        id=cart.id,
        items=items,
        price=total_price,
    )