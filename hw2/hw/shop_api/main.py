from fastapi import FastAPI, Query, HTTPException, Response, status
from pydantic import BaseModel


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: dict[int, CartItem] = {}
    price: float


class Item(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool


class ItemCreate(BaseModel):
    name: str
    price: float


class ItemUpdate(BaseModel):
    name: str
    price: float


class ItemPatch(BaseModel):
    name: str | None = None
    price: float | None = None

    model_config = {
        "extra": "forbid"
    }

carts: dict[int, Cart] = {}
items: dict[int, Item] = {}

next_cart_id = 1
next_item_id = 1

app = FastAPI(title="Shop API")

@app.post("/cart", status_code=status.HTTP_201_CREATED)
def create_cart(response: Response):
    global next_cart_id

    cart_id = next_cart_id
    next_cart_id += 1

    carts[cart_id] = Cart(
        id=cart_id,
        items={},
        price=0.0,
    )

    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{id}")
def get_cart(id: int):
    cart = carts.get(id)

    if cart is None:
        raise HTTPException(
            status_code=404,
            detail="Cart not found"
        )

    return {
        "id": cart.id,
        "items": list(cart.items.values()),
        "price": cart.price,
    }


@app.get("/cart")
def get_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
):
    result = list(carts.values())

    if min_price is not None:
        result = [
            cart
            for cart in result
            if cart.price >= min_price
        ]

    if max_price is not None:
        result = [
            cart
            for cart in result
            if cart.price <= max_price
        ]

    if min_quantity is not None:
        result = [
            cart
            for cart in result
            if sum(
                item.quantity
                for item in cart.items.values()
            ) >= min_quantity
        ]

    if max_quantity is not None:
        result = [
            cart
            for cart in result
            if sum(
                item.quantity
                for item in cart.items.values()
            ) <= max_quantity
        ]

    return [
        {
            "id": cart.id,
            "items": list(cart.items.values()),
            "price": cart.price,
        }
        for cart in result[offset:offset + limit]
    ]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item(cart_id: int, item_id: int):
    cart = carts.get(cart_id)
    item = items.get(item_id)

    if cart is None:
        raise HTTPException(
            status_code=404,
            detail="Cart not found"
        )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    if item.deleted:
        raise HTTPException(
            status_code=400,
            detail="Item is deleted"
        )

    if item_id not in cart.items:
        cart.items[item_id] = CartItem(
            id=item_id,
            name=item.name,
            quantity=1,
            available=True,
        )
    else:
        cart.items[item_id].quantity += 1

    cart.price += item.price
    return cart


@app.post("/item", status_code=status.HTTP_201_CREATED)
def create_item(new_item: ItemCreate):
    global next_item_id

    item_id = next_item_id
    next_item_id += 1

    item = Item(
        id=item_id,
        name=new_item.name,
        price=new_item.price,
        deleted=False,
    )

    items[item_id] = item
    return item


@app.get("/item/{id}")
def get_item(id: int):
    item = items.get(id)

    if item is None or item.deleted:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    return item


@app.get("/item")
def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = False,
):
    result = list(items.values())

    if not show_deleted:
        result = [
            item
            for item in result
            if not item.deleted
        ]

    if min_price is not None:
        result = [
            item
            for item in result
            if item.price >= min_price
        ]

    if max_price is not None:
        result = [
            item
            for item in result
            if item.price <= max_price
        ]

    return result[offset:offset + limit]


@app.put("/item/{id}")
def update_item(id: int, new_item: ItemUpdate):
    item = items.get(id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    item.name = new_item.name
    item.price = new_item.price

    for cart in carts.values():
        cart_item = cart.items.get(id)

        if cart_item is not None:
            cart_item.name = item.name

    return item


@app.patch("/item/{id}")
def patch_item(id: int, new_item: ItemPatch):
    item = items.get(id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    if item.deleted:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED
        )

    if new_item.name is not None:
        item.name = new_item.name

    if new_item.price is not None:
        item.price = new_item.price

    for cart in carts.values():
        cart_item = cart.items.get(id)

        if cart_item is not None:
            if new_item.name is not None:
                cart_item.name = item.name

    return item


@app.delete("/item/{id}")
def delete_item(id: int):
    item = items.get(id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    item.deleted = True
    return item