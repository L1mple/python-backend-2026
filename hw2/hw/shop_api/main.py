from fastapi import FastAPI, HTTPException, Query, Response, Depends
from sqlalchemy.orm import Session
from prometheus_fastapi_instrumentator import Instrumentator
from http import HTTPStatus
from typing import Annotated
from pydantic import NonNegativeInt, PositiveInt

from . import models
from shop_api.schemas import (
    CartCreatedResponse,
    CartItemResponse,
    CartResponse,
    ItemCreate,
    ItemPatch,
    ItemPut,
    ItemResponse
)
from .database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Shop API")
Instrumentator().instrument(app).expose(app)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _build_cart_response(cart_db: models.DBCart) -> CartResponse:
    items: list[CartItemResponse] = []
    total = 0.0

    for cart_item in cart_db.items:
        item_db = cart_item.item
        if item_db is None:
            continue
        available = not item_db.deleted
        items.append(
            CartItemResponse(
                id=item_db.id,
                name=item_db.name,
                quantity=cart_item.quantity,
                available=available,
            )
        )
        if available:
            total += item_db.price * cart_item.quantity
    return CartResponse(id=cart_db.id, items=items, price=total)

@app.post("/cart", status_code=HTTPStatus.CREATED, response_model=CartCreatedResponse)
async def create_cart(response: Response, db: Session = Depends(get_db)) -> CartCreatedResponse:
    db_cart = models.DBCart()
    db.add(db_cart)
    db.commit()
    db.refresh(db_cart)
    
    response.headers["location"] = f"/cart/{db_cart.id}"
    return CartCreatedResponse(id=db_cart.id)

@app.get("/cart/{cart_id}", response_model=CartResponse)
async def get_cart(cart_id: int, db: Session = Depends(get_db)) -> CartResponse:
    db_cart = db.query(models.DBCart).filter(models.DBCart.id == cart_id).first()
    if not db_cart:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    return _build_cart_response(db_cart)

@app.get("/cart", response_model=list[CartResponse])
async def get_carts(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    db: Session = Depends(get_db)
) -> list[CartResponse]:
    db_carts = db.query(models.DBCart).all()
    carts = [_build_cart_response(c) for c in db_carts]

    if min_price is not None:
        carts = [c for c in carts if c.price >= min_price]
    if max_price is not None:
        carts = [c for c in carts if c.price <= max_price]
    if min_quantity is not None:
        carts = [c for c in carts if sum(i.quantity for i in c.items) >= min_quantity]
    if max_quantity is not None:
        carts = [c for c in carts if sum(i.quantity for i in c.items) <= max_quantity]
    return carts[offset : offset + limit]

@app.post("/cart/{cart_id}/add/{item_id}", response_model=CartResponse)
async def add_item_to_cart(cart_id: int, item_id: int, db: Session = Depends(get_db)) -> CartResponse:
    db_cart = db.query(models.DBCart).filter(models.DBCart.id == cart_id).first()
    if not db_cart:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
        
    db_item = db.query(models.DBItem).filter(models.DBItem.id == item_id, models.DBItem.deleted == False).first()
    if not db_item:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")

    cart_item = db.query(models.DBCartItem).filter(
        models.DBCartItem.cart_id == cart_id,
        models.DBCartItem.item_id == item_id
    ).first()
    
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = models.DBCartItem(cart_id=cart_id, item_id=item_id, quantity=1)
        db.add(cart_item)
        
    db.commit()
    db.refresh(db_cart)
    return _build_cart_response(db_cart)

@app.post("/item", status_code=HTTPStatus.CREATED, response_model=ItemResponse)
async def create_item(body: ItemCreate, response: Response, db: Session = Depends(get_db)) -> ItemResponse:
    db_item = models.DBItem(name=body.name, price=body.price, deleted=False)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    response.headers["location"] = f"/item/{db_item.id}"
    return db_item

@app.get("/item/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int, db: Session = Depends(get_db)) -> ItemResponse:
    db_item = db.query(models.DBItem).filter(models.DBItem.id == item_id, models.DBItem.deleted == False).first()
    if not db_item:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return db_item

@app.get("/item", response_model=list[ItemResponse])
async def get_items(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
    db: Session = Depends(get_db)
) -> list[ItemResponse]:
    query = db.query(models.DBItem)
    
    if not show_deleted:
        query = query.filter(models.DBItem.deleted == False)
    if min_price is not None:
        query = query.filter(models.DBItem.price >= min_price)
    if max_price is not None:
        query = query.filter(models.DBItem.price <= max_price)
        
    return query.offset(offset).limit(limit).all()

@app.put("/item/{item_id}", response_model=ItemResponse)
async def put_item(item_id: int, body: ItemPut, db: Session = Depends(get_db)) -> ItemResponse:
    db_item = db.query(models.DBItem).filter(models.DBItem.id == item_id, models.DBItem.deleted == False).first()
    if not db_item:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
        
    db_item.name = body.name
    db_item.price = body.price
    db.commit()
    db.refresh(db_item)
    return db_item

@app.patch("/item/{item_id}", response_model=ItemResponse)
async def patch_item(item_id: int, body: ItemPatch, db: Session = Depends(get_db)) -> ItemResponse:
    db_item = db.query(models.DBItem).filter(models.DBItem.id == item_id, models.DBItem.deleted == False).first()
    if not db_item:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, "Item not found")

    if body.name is not None:
        db_item.name = body.name
    if body.price is not None:
        db_item.price = body.price
        
    db.commit()
    db.refresh(db_item)
    return db_item

@app.delete("/item/{item_id}")
async def delete_item(item_id: int, db: Session = Depends(get_db)) -> dict:
    db_item = db.query(models.DBItem).filter(models.DBItem.id == item_id).first()
    if db_item is not None:
        db_item.deleted = True
        db.commit()
    return {}