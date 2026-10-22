from http import HTTPStatus
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Response
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    WithJsonSchema,
    field_validator
)

app = FastAPI(title="Shop API")


class ItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float = Field(ge=0, allow_inf_nan=False)


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[
        str | None, WithJsonSchema({"type": "string"})
    ] = None
    price: Annotated[
        float | None, WithJsonSchema({"type": "number", "minimum": 0})
    ] = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("name", "price", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field may be omitted, but must not be null")
        return value


class Item(ItemInput):
    id: UUID
    deleted: bool = False


class CartItem(BaseModel):
    id: UUID
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: UUID
    items: list[CartItem]
    price: float


items: dict[UUID, Item] = {}
carts: dict[UUID, dict[UUID, int]] = {}

Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(gt=0)]
PriceFilter = Annotated[float | None, Query(ge=0, allow_inf_nan=False)]
QuantityFilter = Annotated[int | None, Query(ge=0)]


def find_item(item_id: UUID, *, include_deleted: bool = False) -> Item:
    item = items.get(item_id)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Item not found")
    return item


def find_cart(cart_id: UUID) -> dict[UUID, int]:
    if cart_id not in carts:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Cart not found")
    return carts[cart_id]

def render_cart(cart_id: UUID) -> Cart:
    contents = find_cart(cart_id)
    return Cart(
        id=cart_id,
        items=[
            CartItem(
                id=item_id,
                name=items[item_id].name,
                quantity=quantity,
                available=not items[item_id].deleted
            )
            for item_id, quantity in contents.items()
        ],
        price=sum(
            items[item_id].price * quantity
            for item_id, quantity in contents.items()
            if not items[item_id].deleted
        ),
    )


@app.post("/item", status_code=HTTPStatus.CREATED, response_model=Item)
async def create_item(body: ItemInput, response: Response) -> Item:
    item = Item(id=uuid4(), **body.model_dump())
    items[item.id] = item
    response.headers["Location"] = f"/item/{item.id}"
    return item


@app.get("/item", response_model=list[Item])
async def list_items(
        offset: Offset = 0,
        limit: Limit = 10,
        min_price: PriceFilter = None,
        max_price: PriceFilter = None,
        show_deleted: bool = False
) -> list[Item]:
    matches = [
        item for item in items.values()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return matches[offset:offset + limit]


@app.get("/item/{item_id}", response_model=Item)
async def get_item(item_id: UUID) -> Item:
    return find_item(item_id)


@app.put("/item/{item_id}", response_model=Item)
async def replace_item(item_id: UUID, body: ItemInput) -> Item:
    find_item(item_id)
    items[item_id] = Item(id=item_id, **body.model_dump())
    return items[item_id]


@app.patch("/item/{item_id}", response_model=Item)
async def patch_item(item_id: UUID, body: ItemPatch) -> Item | Response:
    item = find_item(item_id, include_deleted=True)
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    items[item_id] = item.model_copy(update=body.model_dump(exclude_unset=True))
    return items[item_id]


@app.delete("/item/{item_id}")
async def delete_item(item_id: UUID) -> Response:
    find_item(item_id, include_deleted=True).deleted = True
    return Response(status_code=HTTPStatus.OK)


@app.post("/cart", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response) -> dict[str, UUID]:
    cart_id = uuid4()
    carts[cart_id] = {}
    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart", response_model=list[Cart])
async def list_carts(
        offset: Offset = 0,
        limit: Limit = 10,
        min_price: PriceFilter = None,
        max_price: PriceFilter = None,
        min_quantity: QuantityFilter = None,
        max_quantity: QuantityFilter = None
) -> list[Cart]:
    matches = []
    for cart_id in carts:
        cart = render_cart(cart_id)
        quantity = sum(item.quantity for item in cart.items)
        if ((min_price is None or cart.price >= min_price)
                and (max_price is None or cart.price <= max_price)
                and (min_quantity is None or quantity >= min_quantity)
                and (max_quantity is None or quantity <= max_quantity)):
            matches.append(cart)
    return matches[offset:offset + limit]


@app.get("/cart/{cart_id}", response_model=Cart)
async def get_cart(cart_id: UUID) -> Cart:
    return render_cart(cart_id)


@app.post("/cart/{cart_id}/add/{item_id}", response_model=Cart)
async def add_item(cart_id: UUID, item_id: UUID) -> Cart:
    contents = find_cart(cart_id)
    find_item(item_id)
    contents[item_id] = contents.get(item_id, 0) + 1
    return render_cart(cart_id)
