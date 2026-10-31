from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response

from .contracts import ItemCreate, ItemPatch, ItemReplace
from .db import create_tables, engine
from .models import Cart, Item
from .repository import ShopRepository, get_repository, item_response


@asynccontextmanager
async def lifespan(app):
    create_tables()
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="Shop API", lifespan=lifespan)
Repository = Annotated[ShopRepository, Depends(get_repository)]


def find_item(repository, item_id):
    item = repository.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def find_available_item(repository, item_id):
    item = find_item(repository, item_id)
    if item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def find_cart(repository, cart_id, lock=False):
    cart = repository.get_cart(cart_id, lock=lock)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


@app.post("/item", status_code=201)
def create_item(body: ItemCreate, response: Response, repository: Repository):
    with repository.session.begin():
        item = repository.save(Item(**body.model_dump()))
        response.headers["Location"] = f"/item/{item.id}"
        return item_response(item)


@app.get("/item/{item_id}")
def get_item(item_id: int, repository: Repository):
    return item_response(find_available_item(repository, item_id))


@app.get("/item")
def get_items(
    repository: Repository,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    max_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    show_deleted: bool = False,
):
    return repository.get_items(offset, limit, min_price, max_price, show_deleted)


@app.put("/item/{item_id}")
def replace_item(item_id: int, body: ItemReplace, repository: Repository):
    with repository.session.begin():
        item = find_item(repository, item_id)
        for field, value in body.model_dump().items():
            setattr(item, field, value)
        return item_response(item)


@app.patch("/item/{item_id}")
def patch_item(item_id: int, body: ItemPatch, repository: Repository):
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field.capitalize()} cannot be null")
    with repository.session.begin():
        item = find_item(repository, item_id)
        if item.deleted:
            return Response(status_code=304)
        for field, value in changes.items():
            setattr(item, field, value)
        return item_response(item)


@app.delete("/item/{item_id}")
def delete_item(item_id: int, repository: Repository):
    with repository.session.begin():
        find_item(repository, item_id).deleted = True
    return Response(status_code=200)


@app.post("/cart", status_code=201)
def create_cart(response: Response, repository: Repository):
    with repository.session.begin():
        cart = repository.save(Cart())
        response.headers["Location"] = f"/cart/{cart.id}"
        return {"id": cart.id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int, repository: Repository):
    find_cart(repository, cart_id)
    return repository.cart_responses([cart_id])[0]


@app.get("/cart")
def get_carts(
    repository: Repository,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    max_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    min_quantity: int | None = Query(default=None, ge=0),
    max_quantity: int | None = Query(default=None, ge=0),
):
    return repository.get_carts(offset, limit, min_price, max_price, min_quantity, max_quantity)


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int, repository: Repository):
    with repository.session.begin():
        find_cart(repository, cart_id, lock=True)
        find_available_item(repository, item_id)
        repository.add_item(cart_id, item_id)
        return repository.cart_responses([cart_id])[0]