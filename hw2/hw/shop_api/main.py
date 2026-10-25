from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from shop_api.database import get_session, init_db
from shop_api.models import Cart, CartItem, Item
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)


class ItemCreate(BaseModel):
    name: str
    price: float


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None

    model_config = {"extra": "forbid"}


@app.post("/cart", status_code=201)
async def create_cart(response: Response, session: AsyncSession = Depends(get_session)):
    cart = Cart()
    session.add(cart)
    await session.commit()
    await session.refresh(cart)
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


async def _build_cart_response(session: AsyncSession, cart: Cart) -> dict:
    result = await session.execute(
        select(CartItem, Item)
        .join(Item, CartItem.item_id == Item.id)
        .where(CartItem.cart_id == cart.id, Item.deleted == False)
    )

    items = []
    total_price = 0.0

    for cart_item, item in result.all():
        items.append(
            {
                "id": item.id,
                "name": item.name,
                "quantity": cart_item.quantity,
                "available": True,
            }
        )
        total_price += item.price * cart_item.quantity

    return {"id": cart.id, "items": items, "price": total_price}


@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int, session: AsyncSession = Depends(get_session)):
    cart = await session.get(Cart, cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    return await _build_cart_response(session, cart)


@app.get("/cart")
async def get_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_quantity: Optional[int] = Query(None, ge=0),
    max_quantity: Optional[int] = Query(None, ge=0),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Cart))
    carts = result.scalars().all()

    filtered = []
    for cart in carts:
        cart_data = await _build_cart_response(session, cart)
        total_quantity = sum(i["quantity"] for i in cart_data["items"])
        total_price = cart_data["price"]

        if min_price is not None and total_price < min_price:
            continue
        if max_price is not None and total_price > max_price:
            continue
        if min_quantity is not None and total_quantity < min_quantity:
            continue
        if max_quantity is not None and total_quantity > max_quantity:
            continue

        filtered.append(cart_data)

    return filtered[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_to_cart(
    cart_id: int,
    item_id: int,
    session: AsyncSession = Depends(get_session),
):
    cart = await session.get(Cart, cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    result = await session.execute(
        select(CartItem).where(
            CartItem.cart_id == cart_id, CartItem.item_id == item_id
        )
    )
    cart_item = result.scalar_one_or_none()

    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(cart_id=cart_id, item_id=item_id, quantity=1)
        session.add(cart_item)

    await session.commit()
    return {"status": "ok"}


@app.post("/item", status_code=201)
async def create_item(item: ItemCreate, session: AsyncSession = Depends(get_session)):
    new_item = Item(name=item.name, price=item.price)
    session.add(new_item)
    await session.commit()
    await session.refresh(new_item)
    return new_item


@app.get("/item/{item_id}")
async def get_item(item_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Item).where(Item.id == item_id, Item.deleted == False)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.get("/item")
async def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    show_deleted: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Item)

    if not show_deleted:
        stmt = stmt.where(Item.deleted == False)
    if min_price is not None:
        stmt = stmt.where(Item.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Item.price <= max_price)

    result = await session.execute(stmt)
    items = result.scalars().all()

    return items[offset : offset + limit]


@app.put("/item/{item_id}")
async def update_item(
    item_id: int,
    item: ItemCreate,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Item).where(Item.id == item_id, Item.deleted == False)
    )
    db_item = result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    db_item.name = item.name
    db_item.price = item.price
    await session.commit()
    await session.refresh(db_item)
    return db_item


@app.patch("/item/{item_id}")
async def patch_item(
    item_id: int,
    item: ItemUpdate,
    session: AsyncSession = Depends(get_session),
):
    db_item = await session.get(Item, item_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    if db_item.deleted:
        return Response(status_code=304)

    if item.name is not None:
        db_item.name = item.name
    if item.price is not None:
        db_item.price = item.price

    await session.commit()
    await session.refresh(db_item)
    return db_item


@app.delete("/item/{item_id}")
async def delete_item(item_id: int, session: AsyncSession = Depends(get_session)):
    db_item = await session.get(Item, item_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    db_item.deleted = True
    await session.commit()
    return {"status": "ok"}