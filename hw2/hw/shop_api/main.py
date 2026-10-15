import os
import random
import string
from http import HTTPStatus
from typing import AsyncGenerator, Optional
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, Response, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload
from sqlalchemy.pool import NullPool
from prometheus_fastapi_instrumentator import Instrumentator


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/shop_db",
)

engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session



class ItemORM(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    price: Mapped[float]
    deleted: Mapped[bool] = mapped_column(default=False)


class CartORM(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    items: Mapped[list["CartItemORM"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CartItemORM(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    quantity: Mapped[int] = mapped_column(default=1)

    cart: Mapped[CartORM] = relationship(back_populates="items")
    item: Mapped[ItemORM] = relationship(lazy="selectin")


app = FastAPI(title="Shop API")

Instrumentator().instrument(app).expose(app)


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    price: float = Field(ge = 0)

class Item(ItemCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    deleted: bool = False

class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    price: float = Field(ge = 0)

class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    price: Optional[float] = Field(default = None, ge = 0)


class CartItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    quantity: int
    available: bool

class Cart(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    items: list[CartItem]
    price: float


async def build_cart(cart_id: int, session: AsyncSession) -> Cart:
    result = await session.execute(
        select(CartORM)
        .where(CartORM.id == cart_id)
        .options(selectinload(CartORM.items).selectinload(CartItemORM.item))
    )
    cart_orm = result.scalar_one_or_none()
    if cart_orm is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    cart_items = []
    total_price = 0.0
    for ci in cart_orm.items:
        cart_items.append(CartItem(id=ci.item.id,name=ci.item.name, quantity=ci.quantity,available=not ci.item.deleted,))
        total_price += ci.item.price * ci.quantity

    return Cart(id=cart_orm.id, items=cart_items, price=total_price)


# Item(REST)

@app.post("/item", status_code=HTTPStatus.CREATED, response_model=Item)
async def create_item(item: ItemCreate, session: AsyncSession = Depends(get_session)) -> Item:
    orm_item = ItemORM(name=item.name, price=item.price, deleted=False)
    session.add(orm_item)
    await session.commit()
    await session.refresh(orm_item)
    return Item.model_validate(orm_item)

@app.get("/item/{item_id}", response_model=Item)
async def get_item(item_id: int, session: AsyncSession = Depends(get_session)) -> Item:
    orm_item = await session.get(ItemORM, item_id)
    if orm_item is None or orm_item.deleted:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    return Item.model_validate(orm_item)


@app.get("/item", response_model=list[Item])
async def get_items(offset: int = Query(0, ge=0), limit: int = Query(10, gt=0), min_price: Optional[float] = Query(None, ge=0), max_price: Optional[float] = Query(None, ge=0), show_deleted: bool = Query(False), session: AsyncSession = Depends(get_session),) -> list[Item]:
    stmt = select(ItemORM)
    if not show_deleted:
        stmt = stmt.where(ItemORM.deleted.is_(False))
    if min_price is not None:
        stmt = stmt.where(ItemORM.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(ItemORM.price <= max_price)
    stmt = stmt.order_by(ItemORM.id).offset(offset).limit(limit)

    result = await session.execute(stmt)
    return [Item.model_validate(row) for row in result.scalars().all()]

@app.put("/item/{item_id}", response_model=Item)
async def put_item(item_id: int, item: ItemUpdate, session: AsyncSession = Depends(get_session)) -> Item:
    orm_item = await session.get(ItemORM, item_id)
    if orm_item is None or orm_item.deleted:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    orm_item.name = item.name
    orm_item.price = item.price
    await session.commit()
    await session.refresh(orm_item)
    return Item.model_validate(orm_item)


@app.patch("/item/{item_id}", response_model=Item)
async def patch_item(item_id: int, patch: ItemPatch, session: AsyncSession = Depends(get_session)) -> Item:
    orm_item = await session.get(ItemORM, item_id)
    if orm_item is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    if orm_item.deleted:
        raise HTTPException(status_code=HTTPStatus.NOT_MODIFIED)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(orm_item, field, value)
    await session.commit()
    await session.refresh(orm_item)
    return Item.model_validate(orm_item)


@app.delete("/item/{item_id}", response_model=Item)
async def delete_item(item_id: int, session: AsyncSession = Depends(get_session)) -> Item:
    orm_item = await session.get(ItemORM, item_id)
    if orm_item is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    orm_item.deleted = True
    await session.commit()
    await session.refresh(orm_item)
    return Item.model_validate(orm_item)


# Cart(REST)

@app.post("/cart", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response, session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    orm_cart = CartORM()
    session.add(orm_cart)
    await session.commit()
    await session.refresh(orm_cart)
    response.headers['location'] = f"/cart/{orm_cart.id}"
    return {'id': orm_cart.id}

@app.get("/cart/{cart_id}", response_model=Cart)
async def get_cart(cart_id: int, session: AsyncSession = Depends(get_session)) -> Cart:
    return await build_cart(cart_id, session)

@app.get("/cart", response_model=list[Cart])
async def get_carts(offset: int = Query(0, ge=0), limit: int = Query(10, gt=0), min_price: Optional[float] = Query(None, ge=0), max_price: Optional[float] = Query(None, ge=0), min_quantity: Optional[int] = Query(None, ge=0), max_quantity: Optional[int] = Query(None, ge=0), session: AsyncSession = Depends(get_session),) -> list[Cart]:
    result = await session.execute(select(CartORM.id).order_by(CartORM.id))
    cart_ids = list(result.scalars().all())
    carts = []
    for cart_id in cart_ids:
        cart = await build_cart(cart_id, session)
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        total_quantity = sum(c.quantity for c in cart.items)
        if min_quantity is not None and total_quantity < min_quantity:
            continue
        if max_quantity is not None and total_quantity > max_quantity:
            continue
        carts.append(cart)

    return carts[offset : offset + limit]

@app.post("/cart/{cart_id}/add/{item_id}", response_model=Cart)
async def add_item_to_cart(cart_id: int, item_id: int, session: AsyncSession = Depends(get_session)) -> Cart:
    cart_orm = await session.get(CartORM, cart_id)
    if cart_orm is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    item_orm = await session.get(ItemORM, item_id)
    if item_orm is None or item_orm.deleted:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    result = await session.execute(
        select(CartItemORM).where(CartItemORM.cart_id == cart_id, CartItemORM.item_id == item_id,))
    cart_item = result.scalar_one_or_none()
    if cart_item is None:
        session.add(CartItemORM(cart_id=cart_id, item_id=item_id, quantity=1))
    else:
        cart_item.quantity += 1

    await session.commit()
    return await build_cart(cart_id, session)

# Web Sockets Chat

class ChatManager:
    def __init__(self) -> None:
        self.chats = dict()
    async def connect(self, chat_name: str, websocket: WebSocket) -> str:
        await websocket.accept()
        username = "".join(random.choices(string.ascii_letters+string.digits, k=10))
        self.chats.setdefault(chat_name, []).append((websocket, username))
        return username
    def disconnect(self, chat_name: str, websocket: WebSocket) -> None:
        chat = self.chats.get(chat_name, [])
        self.chats[chat_name] = [(ws, name) for ws, name in chat if ws is not websocket]
        if not self.chats[chat_name]:
            del self.chats[chat_name]

    async def broadcast(self, chat_name: str, sender: WebSocket, message: str, username: str) -> None:
        for ws, _ in self.chats.get(chat_name, []):
            if ws is not sender:
                await ws.send_text(f'{username} :: {message}')


chat_manager = ChatManager()

@app.websocket("/chat/{chat_name}")
async def chat_endpoint(websocket: WebSocket, chat_name: str) -> None:
    username = await chat_manager.connect(chat_name, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await chat_manager.broadcast(chat_name, websocket, message, username)
    except WebSocketDisconnect:
        chat_manager.disconnect(chat_name, websocket)


def _init_db_sync() -> None:
    """Создаёт таблицы синхронно при импорте модуля.

    Нужно для тестов и CI, которые импортируют main.py,
    но не запускают lifespan/startup event.
    """
    sync_url = DATABASE_URL.replace("+asyncpg", "+psycopg2")
    sync_engine = create_engine(sync_url)
    try:
        Base.metadata.create_all(sync_engine)
    finally:
        sync_engine.dispose()


_init_db_sync()