from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query, Body, Response, status, Depends
from pydantic import BaseModel, ConfigDict
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import engine, Base, get_db
from models import Item, Cart, CartItem


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    price: Optional[float] = None


async def get_item_raw(db: AsyncSession, item_id: int) -> Item:
    item = await db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


async def get_item_or_404(db: AsyncSession, item_id: int) -> Item:
    item = await db.get(Item, item_id)
    if not item or item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


async def dict_of_cart(db: AsyncSession, cart: Cart) -> dict:
    stmt = select(Cart).where(Cart.id == cart.id).options(
        selectinload(Cart.items).selectinload(CartItem.item)
    )
    cart = (await db.execute(stmt)).scalar_one()

    out_items = []
    total_price = 0.0
    for ci in cart.items:
        item = ci.item
        available = not item.deleted
        out_items.append({
            "id": item.id,
            "name": item.name,
            "quantity": ci.quantity,
            "available": available,
        })
        if available:
            total_price += item.price * ci.quantity

    return {
        "id": cart.id,
        "items": out_items,
        "price": total_price,
    }


@app.post("/cart", status_code=status.HTTP_201_CREATED)
async def create_cart(response: Response, db: AsyncSession = Depends(get_db)):
    cart = Cart()
    db.add(cart)
    await db.commit()
    await db.refresh(cart)

    response.headers["Location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}")
async def get_cart_e(cart_id: int, db: AsyncSession = Depends(get_db)):
    cart = await db.get(Cart, cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    return await dict_of_cart(db, cart)


@app.get("/cart")
async def list_carts(
        offset: int = Query(0, ge=0),
        limit: int = Query(10, gt=0),
        min_price: Optional[float] = Query(None, ge=0),
        max_price: Optional[float] = Query(None, ge=0),
        min_quantity: Optional[int] = Query(None, ge=0),
        max_quantity: Optional[int] = Query(None, ge=0),
        db: AsyncSession = Depends(get_db)
):
    stmt = select(Cart).options(selectinload(Cart.items).selectinload(CartItem.item))
    carts = (await db.execute(stmt)).scalars().all()

    result = []
    for cart in carts:
        cart_dict = await dict_of_cart(db, cart)
        price = cart_dict["price"]
        quantity = sum(ci["quantity"] for ci in cart_dict["items"])

        if min_price is not None and price < min_price: continue
        if max_price is not None and price > max_price: continue
        if min_quantity is not None and quantity < min_quantity: continue
        if max_quantity is not None and quantity > max_quantity: continue

        result.append(cart_dict)

    return result[offset: offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int, db: AsyncSession = Depends(get_db)):
    cart = await db.get(Cart, cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    await get_item_or_404(db, item_id)

    stmt = select(CartItem).where(CartItem.cart_id == cart_id, CartItem.item_id == item_id)
    cart_item = (await db.execute(stmt)).scalar_one_or_none()

    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(cart_id=cart_id, item_id=item_id, quantity=1)
        db.add(cart_item)

    await db.commit()
    return await dict_of_cart(db, cart)


@app.post("/item", status_code=status.HTTP_201_CREATED)
async def create_item(body: Dict[str, Any] = Body(...), db: AsyncSession = Depends(get_db)):
    item = Item(name=body["name"], price=float(body["price"]), deleted=False)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": item.id, "name": item.name, "price": item.price, "deleted": item.deleted}


@app.get("/item/{item_id}")
async def get_item_e(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await get_item_or_404(db, item_id)
    return {"id": item.id, "name": item.name, "price": item.price, "deleted": item.deleted}


@app.get("/item")
async def list_items(
        offset: int = Query(0, ge=0),
        limit: int = Query(10, gt=0),
        min_price: Optional[float] = Query(None, ge=0),
        max_price: Optional[float] = Query(None, ge=0),
        show_deleted: bool = Query(False),
        db: AsyncSession = Depends(get_db)
):
    stmt = select(Item)
    if not show_deleted:
        stmt = stmt.where(Item.deleted == False)
    if min_price is not None:
        stmt = stmt.where(Item.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Item.price <= max_price)

    stmt = stmt.offset(offset).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    return [{"id": i.id, "name": i.name, "price": i.price, "deleted": i.deleted} for i in items]


@app.put("/item/{item_id}")
async def replace_item(item_id: int, body: Dict[str, Any] = Body(...), db: AsyncSession = Depends(get_db)):
    item = await get_item_or_404(db, item_id)
    if "name" not in body or "price" not in body:
        raise HTTPException(status_code=422, detail="name and price are required")

    item.name = body["name"]
    item.price = float(body["price"])
    item.deleted = False
    await db.commit()
    await db.refresh(item)

    return {"id": item.id, "name": item.name, "price": item.price, "deleted": item.deleted}


@app.patch("/item/{item_id}")
async def patch_item(item_id: int, body: ItemPatch = Body(...), db: AsyncSession = Depends(get_db)):
    item = await get_item_raw(db, item_id)
    if item.deleted:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        item.name = data["name"]
    if "price" in data:
        item.price = float(data["price"])

    await db.commit()
    await db.refresh(item)
    return {"id": item.id, "name": item.name, "price": item.price, "deleted": item.deleted}


@app.delete("/item/{item_id}")
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await get_item_raw(db, item_id)
    item.deleted = True
    await db.commit()
    await db.refresh(item)
    return {"id": item.id, "name": item.name, "price": item.price, "deleted": item.deleted}