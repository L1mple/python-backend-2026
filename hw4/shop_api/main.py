from decimal import Decimal
from http import HTTPStatus
from typing import Annotated
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
    field_validator,
)
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from shop_api.database import get_db, init_db
from shop_api.models import Cart, CartItem, Item

app = FastAPI(title="Shop API with PostgreSQL")
init_db()


class ItemRequest(BaseModel):
    name: str
    price: NonNegativeFloat

    model_config = ConfigDict(extra="forbid")


class ItemPatchRequest(BaseModel):
    name: str | None = None
    price: NonNegativeFloat | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "price")
    @classmethod
    def reject_null(cls, value: str | float | None) -> str | float:
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class ItemResponse(ItemRequest):
    id: int
    deleted: bool


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float


DatabaseSession = Annotated[Session, Depends(get_db)]


def item_response(item: Item) -> ItemResponse:
    return ItemResponse(
        id=item.id,
        name=item.name,
        price=float(item.price),
        deleted=item.deleted,
    )


def find_active_item(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return item


def find_cart(db: Session, cart_id: int) -> Cart:
    cart = db.scalar(
        select(Cart)
        .where(Cart.id == cart_id)
        .options(selectinload(Cart.items).selectinload(CartItem.item))
    )
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    return cart


def find_cart_for_update(db: Session, cart_id: int) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.id == cart_id).with_for_update())
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    return cart


def cart_response(cart: Cart) -> CartResponse:
    cart_items = [
        CartItemResponse(
            id=entry.item.id,
            name=entry.item.name,
            quantity=entry.quantity,
            available=not entry.item.deleted,
        )
        for entry in cart.items
    ]
    total = sum(
        (entry.item.price * entry.quantity for entry in cart.items),
        start=Decimal(0),
    )
    return CartResponse(id=cart.id, items=cart_items, price=float(total))


@app.get("/health", include_in_schema=False)
def health(db: DatabaseSession) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response, db: DatabaseSession) -> dict[str, int]:
    cart = Cart()
    db.add(cart)
    db.commit()
    db.refresh(cart)
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int, db: DatabaseSession) -> CartResponse:
    return cart_response(find_cart(db, cart_id))


@app.get("/cart")
def get_carts(
    db: DatabaseSession,
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    carts = db.scalars(
        select(Cart)
        .order_by(Cart.id)
        .options(selectinload(Cart.items).selectinload(CartItem.item))
    ).all()

    result: list[CartResponse] = []
    for cart in carts:
        response = cart_response(cart)
        quantity = sum(entry.quantity for entry in cart.items)

        if min_price is not None and response.price < min_price:
            continue
        if max_price is not None and response.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(response)

    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int, db: DatabaseSession) -> CartResponse:
    # The row lock serializes changes to one cart, so concurrent requests do not
    # overwrite each other's quantity updates.
    cart = find_cart_for_update(db, cart_id)
    find_active_item(db, item_id)
    entry = db.get(CartItem, (cart_id, item_id))

    if entry is None:
        db.add(CartItem(cart_id=cart_id, item_id=item_id, quantity=1))
    else:
        entry.quantity += 1

    db.commit()
    db.expire(cart)
    return cart_response(find_cart(db, cart_id))


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(
    info: ItemRequest,
    response: Response,
    db: DatabaseSession,
) -> ItemResponse:
    item = Item(name=info.name, price=Decimal(str(info.price)))
    db.add(item)
    db.commit()
    db.refresh(item)
    response.headers["location"] = f"/item/{item.id}"
    return item_response(item)


@app.get("/item/{item_id}")
def get_item(item_id: int, db: DatabaseSession) -> ItemResponse:
    return item_response(find_active_item(db, item_id))


@app.get("/item")
def get_items(
    db: DatabaseSession,
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    query = select(Item).order_by(Item.id)

    if not show_deleted:
        query = query.where(Item.deleted.is_(False))
    if min_price is not None:
        query = query.where(Item.price >= min_price)
    if max_price is not None:
        query = query.where(Item.price <= max_price)

    items = db.scalars(query.offset(offset).limit(limit)).all()
    return [item_response(item) for item in items]


@app.put("/item/{item_id}", response_model=ItemResponse)
def replace_item(
    item_id: int,
    info: ItemRequest,
    db: DatabaseSession,
) -> ItemResponse | Response:
    item = db.get(Item, item_id)
    if item is None or item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    item.name = info.name
    item.price = Decimal(str(info.price))
    db.commit()
    db.refresh(item)
    return item_response(item)


@app.patch("/item/{item_id}", response_model=ItemResponse)
def update_item(
    item_id: int,
    info: ItemPatchRequest,
    db: DatabaseSession,
) -> ItemResponse | Response:
    item = db.get(Item, item_id)
    if item is None or item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    if info.name is not None:
        item.name = info.name
    if info.price is not None:
        item.price = Decimal(str(info.price))

    db.commit()
    db.refresh(item)
    return item_response(item)


@app.delete("/item/{item_id}")
def delete_item(item_id: int, db: DatabaseSession) -> Response:
    item = db.get(Item, item_id)
    if item is not None:
        item.deleted = True
        db.commit()
    return Response(status_code=HTTPStatus.OK)


class ChatRooms:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = {}

    async def connect(self, chat_name: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.setdefault(chat_name, set()).add(websocket)

    def disconnect(self, chat_name: str, websocket: WebSocket) -> None:
        room = self.connections.get(chat_name)
        if room is None:
            return

        room.discard(websocket)
        if not room:
            del self.connections[chat_name]

    async def broadcast(self, chat_name: str, sender: WebSocket, message: str) -> None:
        for websocket in self.connections.get(chat_name, set()).copy():
            if websocket is not sender:
                await websocket.send_text(message)


chat_rooms = ChatRooms()


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    username = uuid4().hex[:8]
    await chat_rooms.connect(chat_name, websocket)

    try:
        while True:
            message = await websocket.receive_text()
            await chat_rooms.broadcast(chat_name, websocket, f"{username} :: {message}")
    except WebSocketDisconnect:
        chat_rooms.disconnect(chat_name, websocket)
