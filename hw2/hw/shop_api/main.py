from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select
from sqlalchemy.orm import Session

from shop_api.database import Cart, CartItem, Item, SessionLocal
from shop_api.schemas import ItemData, ItemPatch


app = FastAPI(title="Shop API")
# Как в примере к лекции 3: собираем метрики и отдаём их на /metrics.
Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(app)


def item_to_dict(item: Item) -> dict:
    """Берём поля объекта БД и собираем обычный словарь для JSON-ответа."""
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "deleted": item.deleted,
    }


def find_item(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def find_cart(db: Session, cart_id: int) -> Cart:
    cart = db.get(Cart, cart_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


def cart_to_dict(db: Session, cart: Cart) -> dict:
    """
    В cart_items лежат id товаров и их количество, а в items — название и цена.
    Через join соединяем эти данные и затем собираем ответ обычным циклом.
    """
    result = {"id": cart.id, "items": [], "price": 0.0}
    query = select(CartItem, Item)
    query = query.join(Item, CartItem.item_id == Item.id)
    query = query.where(CartItem.cart_id == cart.id)
    query = query.order_by(Item.id)
    for line, item in db.execute(query):
        result["items"].append({
            "id": item.id,
            "name": item.name,
            "quantity": line.quantity,
            "available": not item.deleted,
        })
        # Удалённый товар виден в корзине, но в сумму заказа не входит.
        if not item.deleted:
            result["price"] += item.price * line.quantity
    return result


@app.post("/item", status_code=201)
def create_item(data: ItemData) -> dict:
    """
    Открываем сессию БД, добавляем товар и сохраняем изменение через commit().
    При выходе из with сессия закроется, в том числе если возникла ошибка.
    """
    with SessionLocal() as db:
        item = Item(name=data.name, price=data.price)
        db.add(item)
        db.commit()
        return item_to_dict(item)


@app.get("/item")
def get_items(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    max_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    show_deleted: bool = False,
) -> list[dict]:
    with SessionLocal() as db:
        query = select(Item).order_by(Item.id)
        if not show_deleted:
            query = query.where(Item.deleted.is_(False))
        if min_price is not None:
            query = query.where(Item.price >= min_price)
        if max_price is not None:
            query = query.where(Item.price <= max_price)
        query = query.offset(offset).limit(limit)

        result = []
        for item in db.scalars(query):
            result.append(item_to_dict(item))
        return result


@app.get("/item/{item_id}")
def get_item(item_id: int) -> dict:
    with SessionLocal() as db:
        item = find_item(db, item_id)
        if item.deleted:
            raise HTTPException(status_code=404, detail="Item not found")
        return item_to_dict(item)


@app.put("/item/{item_id}")
def replace_item(item_id: int, data: ItemData):
    with SessionLocal() as db:
        item = find_item(db, item_id)
        if item.deleted:
            return Response(status_code=304)
        item.name = data.name
        item.price = data.price
        db.commit()
        return item_to_dict(item)


@app.patch("/item/{item_id}")
def update_item(item_id: int, data: ItemPatch):
    """
    exclude_unset=True оставляет только поля, которые клиент передал явно.
    Например, из {"price": 15} получим только новую цену и сохраним старое имя.
    Отдельно проверяем null: пропустить поле можно, записать null нельзя.
    """
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and data.name is None:
        raise HTTPException(status_code=422, detail="Name cannot be null")
    if "price" in changes and data.price is None:
        raise HTTPException(status_code=422, detail="Price cannot be null")

    with SessionLocal() as db:
        item = find_item(db, item_id)
        if item.deleted:
            return Response(status_code=304)
        if "name" in changes:
            item.name = data.name
        if "price" in changes:
            item.price = data.price
        db.commit()
        return item_to_dict(item)


@app.delete("/item/{item_id}")
def delete_item(item_id: int) -> dict:
    with SessionLocal() as db:
        item = find_item(db, item_id)
        item.deleted = True
        db.commit()
        return item_to_dict(item)


@app.post("/cart", status_code=201)
def create_cart(response: Response) -> dict:
    with SessionLocal() as db:
        cart = Cart()
        db.add(cart)
        db.commit()
        response.headers["Location"] = f"/cart/{cart.id}"
        return {"id": cart.id}


@app.get("/cart")
def get_carts(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    max_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[dict]:
    with SessionLocal() as db:
        result = []
        for cart in db.scalars(select(Cart).order_by(Cart.id)):
            data = cart_to_dict(db, cart)
            quantity = 0
            for item in data["items"]:
                quantity += item["quantity"]

            if min_price is not None and data["price"] < min_price:
                continue
            if max_price is not None and data["price"] > max_price:
                continue
            if min_quantity is not None and quantity < min_quantity:
                continue
            if max_quantity is not None and quantity > max_quantity:
                continue
            result.append(data)
        # Сначала фильтруем, затем берём нужную страницу.
        return result[offset:offset + limit]


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int) -> dict:
    with SessionLocal() as db:
        cart = find_cart(db, cart_id)
        return cart_to_dict(db, cart)


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item(cart_id: int, item_id: int) -> dict:
    with SessionLocal() as db:
        cart = find_cart(db, cart_id)
        item = find_item(db, item_id)
        if item.deleted:
            raise HTTPException(status_code=404, detail="Item not found")

        # До commit другой запрос в PostgreSQL подождёт изменения этой корзины.
        # Так два добавления не запишут одно и то же старое количество.
        query = select(Cart)
        query = query.where(Cart.id == cart_id)
        query = query.with_for_update()
        db.execute(query).scalar_one()
        line = db.get(CartItem, (cart_id, item_id))
        if line is None:
            db.add(CartItem(cart_id=cart_id, item_id=item_id, quantity=1))
        else:
            line.quantity += 1
        db.commit()
        return cart_to_dict(db, cart)
