from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Shop API")
Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(
    app, include_in_schema=False
)


class ItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float = Field(ge=0, allow_inf_nan=False)


class Item(ItemData):
    id: int
    deleted: bool = False


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("name", "price")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


items: dict[int, Item] = {}
carts: dict[int, dict[int, int]] = {}


def find_item(item_id: int, include_deleted: bool = False) -> Item:
    item = items.get(item_id)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def find_cart(cart_id: int) -> dict[int, int]:
    if cart_id not in carts:
        raise HTTPException(status_code=404, detail="Cart not found")
    return carts[cart_id]


def cart_response(cart_id: int) -> Cart:
    cart_items = []
    price = 0.0
    for item_id, quantity in find_cart(cart_id).items():
        item = items[item_id]
        cart_items.append(CartItem(
            id=item.id,
            name=item.name,
            quantity=quantity,
            available=not item.deleted,
        ))
        if not item.deleted:
            price += item.price * quantity
    return Cart(id=cart_id, items=cart_items, price=price)


@app.post("/item", status_code=201)
async def create_item(body: ItemData, response: Response) -> Item:
    item_id = len(items) + 1
    item = Item(id=item_id, **body.model_dump())
    items[item_id] = item
    response.headers["Location"] = f"/item/{item_id}"
    return item


@app.get("/item")
async def list_items(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    max_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    show_deleted: bool = False,
) -> list[Item]:
    result = [
        item for item in items.values()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return result[offset:offset + limit]


@app.get("/item/{item_id}")
async def get_item(item_id: int) -> Item:
    return find_item(item_id)


@app.put("/item/{item_id}")
async def replace_item(item_id: int, body: ItemData) -> Item:
    find_item(item_id)
    item = Item(id=item_id, **body.model_dump())
    items[item_id] = item
    return item


@app.patch("/item/{item_id}", response_model=Item)
async def patch_item(item_id: int, body: ItemPatch):
    item = find_item(item_id, include_deleted=True)
    if item.deleted:
        return Response(status_code=304)
    updated = item.model_copy(update=body.model_dump(exclude_unset=True))
    items[item_id] = updated
    return updated


@app.delete("/item/{item_id}")
async def delete_item(item_id: int) -> Item:
    item = find_item(item_id, include_deleted=True)
    item.deleted = True
    return item


@app.post("/cart", status_code=201)
async def create_cart(response: Response) -> dict[str, int]:
    cart_id = len(carts) + 1
    carts[cart_id] = {}
    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart")
async def list_carts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    max_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    min_quantity: int | None = Query(default=None, ge=0),
    max_quantity: int | None = Query(default=None, ge=0),
) -> list[Cart]:
    result = []
    for cart_id in carts:
        cart = cart_response(cart_id)
        quantity = sum(item.quantity for item in cart.items)
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(cart)
    return result[offset:offset + limit]


@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int) -> Cart:
    return cart_response(cart_id)


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_item(cart_id: int, item_id: int) -> Cart:
    cart = find_cart(cart_id)
    find_item(item_id)
    cart[item_id] = cart.get(item_id, 0) + 1
    return cart_response(cart_id)
