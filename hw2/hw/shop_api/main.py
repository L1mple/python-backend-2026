from fastapi import FastAPI,  Query, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Shop API")
class ItemToModify(BaseModel):
    name: str | None = None
    price: float | None = None
class ItemToCreate(BaseModel): # сущность товара
    name: str
    price: float
class Item(ItemToCreate): # сущность товара
    id: int
    deleted: bool
class CartItem(BaseModel): # сущность товаров в корзине
    id: int
    name: str
    quantity: int
    available: bool
class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float

carts: dict[int, Cart] = {}
items: dict[int, Item] = {}

current_key = 0

def generate_key() -> int:
    global current_key
    current_key = current_key + 1
    return current_key

@app.post('/cart')
async def create_cart() -> Cart:
    cart_id = generate_key()
    carts[cart_id] = Cart(id=cart_id, items=[], price=0.0)
    return carts[cart_id]

@app.get('/cart/{id}')
async def get_cart(id: int) -> Cart:
    if id not in carts:
        raise HTTPException(status_code=404)
    return carts[id]

@app.get('/cart')
async def get_carts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = Query(default=None, ge=0),
    max_quantity: int | None = Query(default=None, ge=0)
) -> list[Cart]:
    list_by_query = []

    for cart in carts.values():
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue

        items_quantity = sum(item.quantity for item in cart.items)

        if min_quantity is not None and items_quantity < min_quantity:
            continue
        if max_quantity is not None and items_quantity > max_quantity:
            continue

        if offset > 0:
            offset = offset - 1
            continue

        list_by_query.append(cart)

        if len(list_by_query) >= limit:
            break

    return list_by_query

@app.post('/cart/{cart_id}/add/{item_id}')
async def add_item_to_cart(cart_id: int, item_id: int) -> None:
    if cart_id not in carts or item_id not in items or items[item_id].deleted:
        raise HTTPException(status_code=404)

    cart = carts[cart_id]
    item = items[item_id]

    for cart_item in cart.items:
        if cart_item.id != item_id:
            continue
        cart_item.quantity += 1
        cart.price = cart.price + item.price
        return

    cart.items.append(CartItem(id=item_id, name=item.name, quantity=1, available=True))
    cart.price = cart.price + item.price
    return

@app.post('/item')
async def create_item(item: ItemToCreate) -> Item:
    item_id = generate_key()
    current_item = Item(name=item.name, price=item.price, id=item_id, deleted=False)
    items[item_id] = current_item
    return current_item

@app.get('/item/{id}')
async def get_item(id: int) -> Item:
    if id not in items or items[id].deleted:
        raise HTTPException(status_code=404)
    return items[id]

@app.get('/item')
async def get_items(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False
) -> list[Item]:

    items_by_query = []

    for item in items.values():
        if min_price is not None and item.price < min_price:
            continue
        if max_price is not None and item.price > max_price:
            continue
        if not show_deleted and item.deleted:
            continue

        if offset > 0:
            offset -= 1
            continue

        items_by_query.append(item)

        if len(items_by_query) >= limit:
            break

    return items_by_query

@app.put('/item/{id}')
async def replace_item(id: int, replacing_item: ItemToCreate) -> Item:

    item = await get_item(id)
    item.name = replacing_item.name
    item.price = replacing_item.price

    return item

@app.patch('/item/{id}')
async def modify_item(id: int, modifying_item: ItemToModify) -> Item:

    item = await get_item(id)

    if modifying_item.name is not None:
        item.name = modifying_item.name

    if modifying_item.price is not None:
        item.price = modifying_item.price

    return item

@app.delete('/item/{id}')
async def delete_item(id: int) -> None:
    if id not in items or items[id].deleted:
        return

    items[id].deleted = True

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
