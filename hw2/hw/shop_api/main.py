from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from shop_api.database import Base, engine, get_db
from shop_api.models import CartItemModel, CartModel, ItemModel

# Создаём таблицы при старте
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Shop API")


class ItemCreate(BaseModel):
    name: str
    price: float


class ItemReplace(BaseModel):
    name: str
    price: float


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    price: Optional[float] = None


def item_to_dict(item: ItemModel) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "deleted": item.deleted,
    }


def cart_to_dict(cart: CartModel) -> dict:
    items_out = []
    total = 0.0
    for link in cart.items:
        item = link.item
        items_out.append(
            {
                "id": item.id,
                "name": item.name,
                "quantity": link.quantity,
                "available": not item.deleted,
            }
        )
        total += item.price * link.quantity
    return {"id": cart.id, "items": items_out, "price": total}


@app.post("/cart", status_code=201)
def create_cart(response: Response, db: Session = Depends(get_db)):
    cart = CartModel()
    db.add(cart)
    db.commit()
    db.refresh(cart)
    response.headers["Location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int, db: Session = Depends(get_db)):
    cart = db.get(CartModel, cart_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart_to_dict(cart)


@app.get("/cart")
def get_carts(
        offset: int = Query(0, ge=0),
        limit: int = Query(10, gt=0),
        min_price: Optional[float] = Query(None, ge=0),
        max_price: Optional[float] = Query(None, ge=0),
        min_quantity: Optional[int] = Query(None, ge=0),
        max_quantity: Optional[int] = Query(None, ge=0),
        db: Session = Depends(get_db),
):
    result = []
    for cart in db.query(CartModel).all():
        data = cart_to_dict(cart)

        if min_price is not None and data["price"] < min_price:
            continue
        if max_price is not None and data["price"] > max_price:
            continue

        qty = sum(i["quantity"] for i in data["items"])

        if min_quantity is not None and qty < min_quantity:
            continue
        if max_quantity is not None and qty > max_quantity:
            continue

        result.append(data)

    return result[offset: offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int, db: Session = Depends(get_db)):
    cart = db.get(CartModel, cart_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")

    item = db.get(ItemModel, item_id)
    if item is None or item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")

    link = (
        db.query(CartItemModel)
        .filter_by(cart_id=cart_id, item_id=item_id)
        .first()
    )
    if link is None:
        link = CartItemModel(cart_id=cart_id, item_id=item_id, quantity=1)
        db.add(link)
    else:
        link.quantity += 1

    db.commit()
    db.refresh(cart)
    return cart_to_dict(cart)


@app.post("/item", status_code=201)
def create_item(payload: ItemCreate, db: Session = Depends(get_db)):
    item = ItemModel(name=payload.name, price=payload.price, deleted=False)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item_to_dict(item)


@app.get("/item/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ItemModel, item_id)
    if item is None or item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return item_to_dict(item)


@app.get("/item")
def get_items(
        offset: int = Query(0, ge=0),
        limit: int = Query(10, gt=0),
        min_price: Optional[float] = Query(None, ge=0),
        max_price: Optional[float] = Query(None, ge=0),
        show_deleted: bool = False,
        db: Session = Depends(get_db),
):
    query = db.query(ItemModel)
    if not show_deleted:
        query = query.filter(ItemModel.deleted.is_(False))
    if min_price is not None:
        query = query.filter(ItemModel.price >= min_price)
    if max_price is not None:
        query = query.filter(ItemModel.price <= max_price)

    items = query.offset(offset).limit(limit).all()
    return [item_to_dict(i) for i in items]


@app.put("/item/{item_id}")
def replace_item(item_id: int, payload: ItemReplace, db: Session = Depends(get_db)):
    item = db.get(ItemModel, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    item.name = payload.name
    item.price = payload.price
    db.commit()
    db.refresh(item)
    return item_to_dict(item)


@app.patch("/item/{item_id}")
def patch_item(item_id: int, payload: ItemPatch, db: Session = Depends(get_db)):
    item = db.get(ItemModel, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    if item.deleted:
        return Response(status_code=304)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item_to_dict(item)


@app.delete("/item/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ItemModel, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    item.deleted = True
    db.commit()
    db.refresh(item)
    return item_to_dict(item)
