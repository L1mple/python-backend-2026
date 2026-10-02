from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, NonNegativeFloat, NonNegativeInt, PositiveInt

app = FastAPI(title="Shop API")


@dataclass(slots=True)
class ItemEntity:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass(slots=True)
class CartEntity:
    id: int
    items: dict[int, int] = field(default_factory=dict)


_items: dict[int, ItemEntity] = {}
_carts: dict[int, CartEntity] = {}
_item_id_seq = 0
_cart_id_seq = 0


def next_item_id() -> int:
    """Возвращает следующий уникальный идентификатор для товара."""
    global _item_id_seq
    _item_id_seq += 1
    return _item_id_seq


def next_cart_id() -> int:
    """Возвращает следующий уникальный идентификатор для корзины."""
    global _cart_id_seq
    _cart_id_seq += 1
    return _cart_id_seq


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @staticmethod
    def from_entity(entity: ItemEntity) -> "ItemResponse":
        """Строит ответ API из внутренней сущности товара."""
        return ItemResponse(
            id=entity.id,
            name=entity.name,
            price=entity.price,
            deleted=entity.deleted,
        )


class ItemCreateRequest(BaseModel):
    name: str
    price: float


class ItemPutRequest(BaseModel):
    name: str
    price: float


class ItemPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = None


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float

    @staticmethod
    def from_entity(entity: CartEntity) -> "CartResponse":
        """Строит ответ API из внутренней сущности корзины, пересчитывая цену по текущим ценам товаров."""
        items = []
        total_price = 0.0

        for item_id, quantity in entity.items.items():
            item = _items.get(item_id)
            if item is None:
                continue

            items.append(
                CartItemResponse(
                    id=item.id,
                    name=item.name,
                    quantity=quantity,
                    available=not item.deleted,
                )
            )
            total_price += item.price * quantity

        return CartResponse(id=entity.id, items=items, price=total_price)


@app.post("/cart", status_code=HTTPStatus.CREATED)
async def post_cart(response: Response) -> dict[str, int]:
    """Создаёт новую пустую корзину и возвращает её идентификатор."""
    cart_id = next_cart_id()
    _carts[cart_id] = CartEntity(id=cart_id)
    response.headers["location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{id}")
async def get_cart(id: int) -> CartResponse:
    """Возвращает корзину по идентификатору или 404, если её нет."""
    cart = _carts.get(id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Корзина {id} не найдена")
    return CartResponse.from_entity(cart)


@app.get("/cart")
async def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    """Возвращает список корзин с фильтрацией по цене и суммарному количеству товаров и пагинацией."""
    result = []

    for cart in _carts.values():
        cart_response = CartResponse.from_entity(cart)
        quantity = sum(item.quantity for item in cart_response.items)

        if min_price is not None and cart_response.price < min_price:
            continue
        if max_price is not None and cart_response.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(cart_response)

    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    """Добавляет товар в корзину, увеличивая его количество, если он уже там есть."""
    cart = _carts.get(cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Корзина {cart_id} не найдена")

    item = _items.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Товар {item_id} не найден")

    cart.items[item_id] = cart.items.get(item_id, 0) + 1

    return CartResponse.from_entity(cart)


@app.post("/item", status_code=HTTPStatus.CREATED)
async def post_item(info: ItemCreateRequest, response: Response) -> ItemResponse:
    """Создаёт новый товар."""
    item_id = next_item_id()
    entity = ItemEntity(id=item_id, name=info.name, price=info.price)
    _items[item_id] = entity
    response.headers["location"] = f"/item/{item_id}"
    return ItemResponse.from_entity(entity)


@app.get("/item/{id}")
async def get_item(id: int) -> ItemResponse:
    """Возвращает товар по идентификатору. Удалённые товары считаются не найденными."""
    item = _items.get(id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Товар {id} не найден")
    return ItemResponse.from_entity(item)


@app.get("/item")
async def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    """Возвращает список товаров с фильтрацией по цене, флагом показа удалённых и пагинацией."""
    result = []

    for item in _items.values():
        if not show_deleted and item.deleted:
            continue
        if min_price is not None and item.price < min_price:
            continue
        if max_price is not None and item.price > max_price:
            continue

        result.append(ItemResponse.from_entity(item))

    return result[offset : offset + limit]


@app.put("/item/{id}")
async def put_item(id: int, info: ItemPutRequest) -> ItemResponse:
    """Полностью заменяет существующий товар. Создание нового товара через PUT запрещено."""
    item = _items.get(id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Товар {id} не найден")

    item.name = info.name
    item.price = info.price

    return ItemResponse.from_entity(item)


@app.patch("/item/{id}")
async def patch_item(id: int, info: ItemPatchRequest) -> ItemResponse:
    """Частично обновляет товар. Изменение поля deleted через этот метод запрещено."""
    item = _items.get(id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Товар {id} не найден")

    if info.name is not None:
        item.name = info.name
    if info.price is not None:
        item.price = info.price

    return ItemResponse.from_entity(item)


@app.delete("/item/{id}")
async def delete_item(id: int) -> Response:
    """Помечает товар как удалённый. Идемпотентна: повторный вызов не ломается."""
    item = _items.get(id)
    if item is not None:
        item.deleted = True
    return Response("")