from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from typing import Optional, List


app = FastAPI(title="Shop API")

class ItemBase(BaseModel):
    name: str
    price: float

class ItemCreate(ItemBase):
    pass

class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    name: Optional[str] = None
    price: Optional[float] = None
    deleted: Optional[bool] = None

class Item(ItemBase):
    id: int
    deleted: bool = False

class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool

class Cart(BaseModel):
    id: int
    items: List[CartItem]
    price: float

class CartIdResponse(BaseModel):
    id: int

items_db: dict[int, Item] = {}
carts_db: dict[int, Cart] = {}

item_id_cnt = 0
cart_id_cnt = 0

ITEM_NOT_FOUND = "Item not found"
CART_NOT_FOUND = "Cart not found"


def calculate_cart(cart: Cart) -> Cart:
    total_price = 0.0
    updated_items = []
    for cart_item in cart.items:
        db_item = items_db.get(cart_item.id)
        if db_item:
            is_available = not db_item.deleted
            total_price += db_item.price * cart_item.quantity
            updated_items.append(CartItem(
                id=cart_item.id,
                name=db_item.name,
                quantity=cart_item.quantity,
                available=is_available
            ))
    return Cart(
        id=cart.id,
        items=updated_items,
        price=total_price
    )


@app.post("/item", response_model=Item, status_code=201)
def create_item(item: ItemCreate):
    global item_id_cnt
    new_item = Item(id=item_id_cnt, name=item.name, price=item.price, deleted=False)
    items_db[item_id_cnt] = new_item
    item_id_cnt += 1
    return new_item


@app.get("/item/{item_id}", response_model=Item)
def get_item(item_id: int):
    if item_id not in items_db or items_db[item_id].deleted:
        raise HTTPException(status_code=404, detail=ITEM_NOT_FOUND)
    return items_db[item_id]


@app.get("/item", response_model=List[Item])
def list_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    show_deleted: bool = False
):
    result = []
    for item in items_db.values():
        if not show_deleted and item.deleted:
            continue
        if min_price is not None and item.price < min_price:
            continue
        if max_price is not None and item.price > max_price:
            continue
        result.append(item)
    result.sort(key=lambda x: x.id)
    return result[offset:offset + limit]


@app.put("/item/{item_id}", response_model=Item)
def update_item(item_id: int, item: ItemCreate):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail=ITEM_NOT_FOUND)
    items_db[item_id].name = item.name
    items_db[item_id].price = item.price
    items_db[item_id].deleted = False
    return items_db[item_id]


@app.patch("/item/{item_id}", response_model=Item)
def patch_item(item_id: int, item: ItemUpdate):
    if item_id not in items_db or items_db[item_id].deleted:
        raise HTTPException(status_code=304, detail="Not modified")
    if item.deleted is not None:
        raise HTTPException(status_code=422, detail="Cannot update 'deleted' field via PATCH")
    if item.name is not None:
        items_db[item_id].name = item.name
    if item.price is not None:
        items_db[item_id].price = item.price    
    return items_db[item_id]


@app.delete("/item/{item_id}", response_model=Item)
def delete_item(item_id: int):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail=ITEM_NOT_FOUND)
    items_db[item_id].deleted = True
    return items_db[item_id]


@app.post("/cart", response_model=CartIdResponse, status_code=201)
def create_cart(response: Response):
    global cart_id_cnt
    new_id = cart_id_cnt
    carts_db[new_id] = Cart(id=new_id, items=[], price=0.0)
    cart_id_cnt += 1
    response.headers["Location"] = f"/cart/{new_id}"
    return {"id": new_id}


@app.get("/cart/{cart_id}", response_model=Cart)
def get_cart(cart_id: int):
    if cart_id not in carts_db:
        raise HTTPException(status_code=404, detail=CART_NOT_FOUND)
    return calculate_cart(carts_db[cart_id])


@app.get("/cart", response_model=List[Cart])
def list_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_quantity: Optional[int] = Query(None, ge=0),
    max_quantity: Optional[int] = Query(None, ge=0)
):
    result = []
    for cart in carts_db.values():
        calc_cart = calculate_cart(cart)
        if min_price is not None and calc_cart.price < min_price:
            continue
        if max_price is not None and calc_cart.price > max_price:
            continue
        total_qty = sum(ci.quantity for ci in calc_cart.items)
        if min_quantity is not None and total_qty < min_quantity:
            continue
        if max_quantity is not None and total_qty > max_quantity:
            continue
        result.append(calc_cart)
    result.sort(key=lambda x: x.id)
    return result[offset:offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}", response_model=Cart)
def add_to_cart(cart_id: int, item_id: int):
    if cart_id not in carts_db:
        raise HTTPException(status_code=404, detail=CART_NOT_FOUND)
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail=ITEM_NOT_FOUND)
    cart = carts_db[cart_id]
    db_item = items_db[item_id]
    for cart_item in cart.items:
        if cart_item.id == item_id:
            cart_item.quantity += 1
            return calculate_cart(cart)
    new_cart_item = CartItem(
        id=db_item.id,
        name=db_item.name,
        quantity=1,
        available=not db_item.deleted
    )
    cart.items.append(new_cart_item)
    return calculate_cart(cart)
