from http import HTTPStatus
from typing import Annotated
from uuid import UUID, uuid4

from psycopg import Connection
from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, field_validator

from .database import initialize, session

app = FastAPI(title="Shop API")
initialize()


class ItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float = Field(ge=0, allow_inf_nan=False)


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, WithJsonSchema({"type": "string"})] = None
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


Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(gt=0)]
PriceFilter = Annotated[float | None, Query(ge=0, allow_inf_nan=False)]
QuantityFilter = Annotated[int | None, Query(ge=0)]


def find_item(db: Connection, item_id: UUID, *, include_deleted: bool = False) -> dict:
    row = db.execute("SELECT * FROM items WHERE id = %s", (item_id,)).fetchone()
    if row is None or (row["deleted"] and not include_deleted):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Item not found")
    return row


def find_cart(db: Connection, cart_id: UUID) -> None:
    if db.execute("SELECT 1 FROM carts WHERE id = %s", (cart_id,)).fetchone() is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Cart not found")


def render_cart(db: Connection, cart_id: UUID) -> Cart:
    find_cart(db, cart_id)
    rows = db.execute("""
        SELECT i.id, i.name, i.price, i.deleted, ci.quantity
        FROM cart_items AS ci JOIN items AS i ON i.id = ci.item_id
        WHERE ci.cart_id = %s ORDER BY ci.sequence
    """, (cart_id,)).fetchall()
    return Cart(
        id=cart_id,
        items=[
            CartItem(
                id=row["id"],
                name=row["name"],
                quantity=row["quantity"],
                available=not row["deleted"]
            ) for row in rows],
        price=sum(row["price"] * row["quantity"] for row in rows if not row["deleted"]),
    )


@app.post("/item", status_code=HTTPStatus.CREATED, response_model=Item)
async def create_item(body: ItemInput, response: Response) -> Item:
    item = Item(id=uuid4(), **body.model_dump())
    with session() as db:
        db.execute(
            "INSERT INTO items (id, name, price) VALUES (%s, %s, %s)",
            (item.id, item.name, item.price)
        )
    response.headers["Location"] = f"/item/{item.id}"
    return item


@app.get("/item", response_model=list[Item])
def list_items(
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: PriceFilter = None,
    max_price: PriceFilter = None,
    show_deleted: bool = False,
) -> list[Item]:
    filters = {
        "deleted = %s": False if not show_deleted else None,
        "price >= %s": min_price,
        "price <= %s": max_price,
    }
    filters = {
        condition: value
        for condition, value in filters.items()
        if value is not None
    }

    where = "WHERE " + " AND ".join(filters) if filters else ""
    query = f"""
        SELECT *
        FROM items
        {where}
        ORDER BY sequence
        LIMIT %s OFFSET %s
    """

    with session() as db:
        rows = db.execute(
            query,
            (*filters.values(), limit, offset),
        ).fetchall()

    return [
        Item(
            id=row["id"],
            name=row["name"],
            price=row["price"],
            deleted=bool(row["deleted"])
        ) for row in rows
    ]


@app.get("/item/{item_id}", response_model=Item)
async def get_item(item_id: UUID) -> Item:
    with session() as db:
        result = find_item(db, item_id)
        return Item(
            id=result["id"],
            name=result["name"],
            price=result["price"],
            deleted=bool(result["deleted"])
        )


@app.put("/item/{item_id}", response_model=Item)
async def replace_item(item_id: UUID, body: ItemInput) -> Item:
    with session() as db:
        find_item(db, item_id)
        db.execute(
            "UPDATE items SET name = %s, price = %s, deleted = FALSE WHERE id = %s",
            (body.name, body.price, item_id)
        )
        result = find_item(db, item_id)
        return Item(
            id=result["id"],
            name=result["name"],
            price=result["price"],
            deleted=bool(result["deleted"])
        )


@app.patch("/item/{item_id}", response_model=Item)
async def patch_item(item_id: UUID, body: ItemPatch) -> Item | Response:
    with session() as db:
        item = find_item(db, item_id, include_deleted=True)
        if item["deleted"]:
            return Response(status_code=HTTPStatus.NOT_MODIFIED)
        changes = body.model_dump(exclude_unset=True)
        if changes:
            columns = ", ".join(f"{column} = %s" for column in changes)
            db.execute(
                f"UPDATE items SET {columns} WHERE id = %s",
                (*changes.values(), item_id)
            )
        result = find_item(db, item_id)
        return Item(
            id=result["id"],
            name=result["name"],
            price=result["price"],
            deleted=bool(result["deleted"])
        )


@app.delete("/item/{item_id}")
async def delete_item(item_id: UUID) -> Response:
    with session() as db:
        find_item(db, item_id, include_deleted=True)
        db.execute("UPDATE items SET deleted = TRUE WHERE id = %s", (item_id,))
    return Response(status_code=HTTPStatus.OK)


@app.post("/cart", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response) -> dict[str, UUID]:
    cart_id = uuid4()
    with session() as db:
        db.execute("INSERT INTO carts (id) VALUES (%s)", (cart_id,))
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
    with session() as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        ids = [row["id"] for row in db.execute("SELECT id FROM carts ORDER BY sequence")]
        matches = []
        for cart_id in ids:
            cart = render_cart(db, cart_id)
            quantity = sum(item.quantity for item in cart.items)
            if ((min_price is None or cart.price >= min_price)
                    and (max_price is None or cart.price <= max_price)
                    and (min_quantity is None or quantity >= min_quantity)
                    and (max_quantity is None or quantity <= max_quantity)):
                matches.append(cart)
        return matches[offset:offset + limit]


@app.get("/cart/{cart_id}", response_model=Cart)
async def get_cart(cart_id: UUID) -> Cart:
    with session() as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return render_cart(db, cart_id)


@app.post("/cart/{cart_id}/add/{item_id}", response_model=Cart)
async def add_item(cart_id: UUID, item_id: UUID) -> Cart:
    with session() as db:
        find_cart(db, cart_id)
        find_item(db, item_id)
        db.execute("""
            INSERT INTO cart_items (cart_id, item_id, quantity) VALUES (%s, %s, 1)
            ON CONFLICT(cart_id, item_id) DO UPDATE SET quantity = cart_items.quantity + 1
            """, (cart_id, item_id)
        )
        return render_cart(db, cart_id)
