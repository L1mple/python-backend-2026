from fastapi import FastAPI, HTTPException
from collections import defaultdict
from itertools import count
from pydantic import BaseModel #TODO
from pydantic import ConfigDict

app = FastAPI(title="Shop API")

cart_id_counter = count(1)

class Item:
    def __init__(self, item_id: int, name: str, price: float):
        self.item_id = item_id
        self.name = name
        self.price = price
        self.is_actual = True  

    def to_dict(self):
        return {
            "id": self.item_id,
            "name": self.name,
            "price": self.price,
            "deleted": not self.is_actual
        }

    def mark_as_deleted(self):
        self.is_actual = False

    def mark_as_actual(self):
        self.is_actual = True


class Cart:
    def __init__(self, cart_id: int):
        self.cart_id = cart_id
        self.items = defaultdict(int)

    def add_item(self, item_id: int, quantity: int):
        self.items[item_id] += quantity
        return None

    def get_item_quantity(self, item_id: int) -> int:
        return self.items.get(item_id, 0)
    
    def remove_item(self, item_id: int, quantity: int) -> None:
        self.items[item_id] -= quantity
        if self.items[item_id] <= 0:
            del self.items[item_id]

    def get_items(self) -> defaultdict:
        return self.items

    def get_total_price(self) -> float:
        return sum(items[item_id].price * quantity for item_id, quantity in self.items.items() if item_id in items and items[item_id].is_actual)
    
    def get_items_quantity(self, cart_id: int) -> int:
        return sum(self.items.values())
    
    def to_dict(self):
        return {
            "id": self.cart_id,
            "items": [
                {"id": item_id, "name": items[item_id].name, "quantity": quantity, "available": items[item_id].is_actual if item_id in items else False}
                for item_id, quantity in self.items.items()
            ],
            "price": self.get_total_price()
        }

items: dict[int, Item] = {}
carts: dict[int, Cart] = {}

class ItemCreateRequest(BaseModel):
    # item_id: int
    name: str
    price: float

class ItemUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    price: float
    deleted: bool | None = None

class ItemPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    price: float | None = None

def get_cart(cart_id: int) -> Cart:
    cart = carts.get(cart_id)
    if not cart:
        raise HTTPException(
                    status_code=404, 
                    detail="Cart not found"
                )
    return cart

@app.get("/cart/{cart_id}")
def read_cart(cart_id: int):
    cart = get_cart(cart_id)
    return cart.to_dict()

from fastapi import Response

@app.post("/cart", status_code=201)
def create_cart(response: Response):
    cart_id = next(cart_id_counter)
    carts[cart_id] = Cart(cart_id)
    response.headers["location"] = f"/cart/{cart_id}"
    return {"id": cart_id}

@app.get("/cart")
def get_carts(
               offset: int = 0,
               limit: int = 10, 
               min_price: float = 0.0, 
               max_price: float = float(10 ** 9),
               min_quantity: int = 0,
               max_quantity: int = 10 ** 9
            ):
    if offset < 0 or limit <= 0 or min_price < 0 or max_price < 0 or min_price > max_price or min_quantity < 0 or max_quantity < 0 or min_quantity > max_quantity:
        raise HTTPException(
                    status_code=422, 
                    detail="Offset must be non-negative and limit must be positive"
                )
    
    filtered_carts = [
        x for x in carts.values() if min_quantity <= x.get_items_quantity(x.cart_id) <= max_quantity and min_price <= x.get_total_price() <= max_price
    ]
    cart_list = filtered_carts[offset:offset + limit]
    return [cart.to_dict() for cart in cart_list]

@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int):
    cart = get_cart(cart_id)
    item = items.get(item_id)
    if not item or not item.is_actual:
        raise HTTPException(
                    status_code=404, 
                    detail="Item not found or marked as deleted"
                )
    cart.add_item(item_id, 1)
    return {"id": cart_id, "item_id": item_id, "quantity": 1}

@app.post("/item", status_code=201)
def create_item(item: ItemCreateRequest):
    item_id = len(items) + 1
    items[item_id] = Item(item_id, item.name, item.price)
    return {"id": item_id, "name": item.name, "price": item.price, "deleted": False}

@app.get("/item")
def get_items(offset: int = 0, limit: int = 10, min_price: float = 0.0, max_price: float = float(10 ** 9), show_deleted: bool = False):
    if offset < 0 or limit <= 0 or min_price < 0 or max_price < 0 or min_price > max_price:
        raise HTTPException(
                    status_code=422, 
                    detail="Offset must be non-negative and limit must be positive"
                )
    filtered_items = [
        item for item in items.values() 
        if (show_deleted or item.is_actual) and min_price <= item.price <= max_price
    ]
    item_list = filtered_items[offset:offset + limit]
    return [item.to_dict() for item in item_list]

@app.get("/item/{item_id}")
def get_item(item_id: int):
    item = items.get(item_id)
    if not item or not item.is_actual:
        raise HTTPException(
                    status_code=404, 
                    detail="Item not found"
                )
    
    return item.to_dict()

@app.put("/item/{item_id}")
def put_item(item_id: int, item_: ItemUpdateRequest):
    item = items.get(item_id)
    if not item:
        raise HTTPException(
                    status_code=404,
                    detail="Item not found"
        )
    item.name = item_.name
    item.price = item_.price
    item.mark_as_actual()  # Mark the item as actual if it was previously marked as deleted
    return item.to_dict()

@app.patch("/item/{item_id}")
def patch_item(item_id: int, item_: ItemPatchRequest):
    item = items.get(item_id)
    if not item:
                raise HTTPException(
                            status_code=404,
                            detail="Item not found"
                )
    
    if not item.is_actual:
        return Response(status_code=304)
    
    if item_.name is not None:
        item.name = item_.name
    if item_.price is not None:
        item.price = item_.price
    
    return item.to_dict()

@app.delete("/item/{item_id}")
def delete_item(item_id: int):
    item = items.get(item_id)
    if not item:
        raise HTTPException(
                    status_code=404,
                    detail="Item not found"
        )
    item.mark_as_deleted()
    return {"item_id": item_id, "deleted": True}
