from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from shop_api import crud
from shop_api.contracts import (
    CartCreatedResponse,
    CartItemResponse,
    CartResponse,
)
from shop_api.database import get_session

router = APIRouter(prefix="/cart", tags=["cart"])


def _build_cart_response(session: Session, cart_id: int) -> CartResponse:
    contents = crud.get_cart_contents(session, cart_id)
    assert contents is not None

    cart_items: list[CartItemResponse] = []
    total = 0.0

    for item_id, quantity in contents.items():
        item = crud.get_item(session, item_id)
        assert item is not None

        cart_items.append(
            CartItemResponse(
                id=item_id,
                name=item["name"],
                quantity=quantity,
                available=not item["deleted"],
            )
        )
        total += item["price"] * quantity

    return CartResponse(id=cart_id, items=cart_items, price=total)


@router.post("", status_code=HTTPStatus.CREATED)
def create_cart(
    response: Response,
    session: Session = Depends(get_session),
) -> CartCreatedResponse:
    cart_id = crud.create_cart(session)
    response.headers["location"] = f"/cart/{cart_id}"
    return CartCreatedResponse(id=cart_id)


@router.get("")
def list_carts(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
    session: Session = Depends(get_session),
) -> list[CartResponse]:
    cart_ids = crud.list_carts(
        session, offset, limit, min_price, max_price, min_quantity, max_quantity
    )
    return [_build_cart_response(session, cid) for cid in cart_ids]


@router.get("/{cart_id}")
def get_cart(
    cart_id: int,
    session: Session = Depends(get_session),
) -> CartResponse:
    if crud.get_cart_contents(session, cart_id) is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} not found")
    return _build_cart_response(session, cart_id)


@router.post("/{cart_id}/add/{item_id}")
def add_item(
    cart_id: int,
    item_id: int,
    session: Session = Depends(get_session),
) -> CartResponse:
    if crud.get_cart_contents(session, cart_id) is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} not found")

    item = crud.get_item(session, item_id)
    if item is None or item["deleted"]:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")

    crud.add_item_to_cart(session, cart_id, item_id)
    return _build_cart_response(session, cart_id)
