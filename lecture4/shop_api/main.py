from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from prometheus_fastapi_instrumentator import Instrumentator

from .database import Base, engine, get_db
from .models import CartDB, CartItemDB, ItemDB
from .schemas import Cart, CartItem, Item, ItemCreate, ItemPatch, ItemUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):

    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)


def item_out(item: ItemDB) -> Item:
    return Item(id=item.id, name=item.name, price=item.price, deleted=item.deleted)


def cart_out(cart: CartDB) -> Cart:
    return Cart(
        id=cart.id,
        items=[
            CartItem(
                id=ci.item_id,
                name=ci.name,
                quantity=ci.quantity,
                available=ci.available,
            )
            for ci in cart.items
        ],
        price=cart.price,
    )


@app.post("/cart", status_code=status.HTTP_201_CREATED)
def create_cart(response: Response, db: Session = Depends(get_db)):
    cart = CartDB(price=0.0)
    db.add(cart)
    db.commit()
    db.refresh(cart)
    response.headers["Location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{id}", response_model=Cart)
def get_cart(id: int, db: Session = Depends(get_db)):
    cart = db.scalar(
        select(CartDB)
        .options(selectinload(CartDB.items))
        .where(CartDB.id == id)
    )
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart_out(cart)


@app.get("/cart", response_model=list[Cart])
def get_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(CartDB).options(selectinload(CartDB.items))
    if min_price is not None:
        stmt = stmt.where(CartDB.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(CartDB.price <= max_price)
    if min_quantity is not None or max_quantity is not None:
        quantity_sum = (
            select(func.coalesce(func.sum(CartItemDB.quantity), 0))
            .where(CartItemDB.cart_id == CartDB.id)
            .correlate(CartDB)
            .scalar_subquery()
        )
        if min_quantity is not None:
            stmt = stmt.where(quantity_sum >= min_quantity)
        if max_quantity is not None:
            stmt = stmt.where(quantity_sum <= max_quantity)
    stmt = stmt.order_by(CartDB.id).offset(offset).limit(limit)
    return [cart_out(cart) for cart in db.scalars(stmt).all()]


@app.post("/cart/{cart_id}/add/{item_id}", response_model=Cart)
def add_item(cart_id: int, item_id: int, db: Session = Depends(get_db)):
    cart = db.scalar(
        select(CartDB)
        .options(selectinload(CartDB.items))
        .where(CartDB.id == cart_id)
        .with_for_update()
    )
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")

    item = db.get(ItemDB, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.deleted:
        raise HTTPException(status_code=400, detail="Item is deleted")

    cart_item = next((ci for ci in cart.items if ci.item_id == item_id), None)
    if cart_item is None:
        cart.items.append(
            CartItemDB(
                item_id=item.id,
                name=item.name,
                quantity=1,
                available=True,
            )
        )
    else:
        cart_item.quantity += 1

    cart.price += item.price
    db.commit()
    db.refresh(cart)
    return cart_out(cart)


@app.post("/item", status_code=status.HTTP_201_CREATED, response_model=Item)
def create_item(new_item: ItemCreate, db: Session = Depends(get_db)):
    item = ItemDB(name=new_item.name, price=new_item.price, deleted=False)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item_out(item)


@app.get("/item/{id}", response_model=Item)
def get_item(id: int, db: Session = Depends(get_db)):
    item = db.get(ItemDB, id)
    if item is None or item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return item_out(item)


@app.get("/item", response_model=list[Item])
def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = False,
    db: Session = Depends(get_db),
):
    stmt = select(ItemDB)
    if not show_deleted:
        stmt = stmt.where(ItemDB.deleted.is_(False))
    if min_price is not None:
        stmt = stmt.where(ItemDB.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(ItemDB.price <= max_price)
    stmt = stmt.order_by(ItemDB.id).offset(offset).limit(limit)
    return [item_out(item) for item in db.scalars(stmt).all()]


@app.put("/item/{id}", response_model=Item)
def update_item(id: int, new_item: ItemUpdate, db: Session = Depends(get_db)):
    item = db.get(ItemDB, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    item.name = new_item.name
    item.price = new_item.price
    for cart_item in db.scalars(
        select(CartItemDB).where(CartItemDB.item_id == id)
    ).all():
        cart_item.name = item.name

    db.commit()
    db.refresh(item)
    return item_out(item)


@app.patch("/item/{id}", response_model=Item)
def patch_item(id: int, new_item: ItemPatch, db: Session = Depends(get_db)):
    item = db.get(ItemDB, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.deleted:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    if new_item.name is not None:
        item.name = new_item.name
        for cart_item in db.scalars(
            select(CartItemDB).where(CartItemDB.item_id == id)
        ).all():
            cart_item.name = item.name
    if new_item.price is not None:
        item.price = new_item.price

    db.commit()
    db.refresh(item)
    return item_out(item)


@app.delete("/item/{id}", response_model=Item)
def delete_item(id: int, db: Session = Depends(get_db)):
    item = db.get(ItemDB, id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    item.deleted = True
    db.commit()
    db.refresh(item)
    return item_out(item)
