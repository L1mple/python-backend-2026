from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .contracts import (
    CartCreateOut,
    CartItemOut,
    CartListOut,
    CartOut,
    ItemCreateIn,
    ItemListOut,
    ItemOut,
    ItemPatchIn,
    ItemPutIn,
)
from .store.db import get_session
from .store.tables import CartItemRow, CartRow, ItemRow

router2 = APIRouter()


@router2.post("/item", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: ItemCreateIn,
    session: Session = Depends(get_session),
) -> ItemOut:
    row = ItemRow(name=payload.name, price=payload.price, deleted=False)
    session.add(row)
    session.commit()
    return ItemOut(id=row.id, name=row.name, price=row.price, deleted=row.deleted)


@router2.get("/item/{item_id}", response_model=ItemOut)
def get_item(
    item_id: int,
    session: Session = Depends(get_session),
) -> ItemOut:
    item = session.get(ItemRow, item_id)
    if item is None or item.deleted:
        raise HTTPException(404, "item not found")
    return ItemOut(id=item.id, name=item.name, price=item.price, deleted=item.deleted)


@router2.get("/item", response_model=ItemListOut)
def list_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = Query(False),
    session: Session = Depends(get_session),
) -> ItemListOut:
    filters = []
    if not show_deleted:
        filters.append(ItemRow.deleted.is_(False))
    if min_price is not None:
        filters.append(ItemRow.price >= min_price)
    if max_price is not None:
        filters.append(ItemRow.price <= max_price)

    total = session.scalar(select(func.count()).select_from(ItemRow).where(*filters)) or 0
    rows = (
        session.scalars(
            select(ItemRow)
            .where(*filters)
            .order_by(ItemRow.id)
            .offset(offset)
            .limit(limit)
        )
        .all()
    )

    return ItemListOut(
        items=[
            ItemOut(id=i.id, name=i.name, price=i.price, deleted=i.deleted)
            for i in rows
        ],
        total=total,
    )


@router2.put("/item/{item_id}", response_model=ItemOut)
def replace_item(
    item_id: int,
    payload: ItemPutIn,
    session: Session = Depends(get_session),
) -> ItemOut:
    item = session.get(ItemRow, item_id)
    if item is None or item.deleted:
        raise HTTPException(404, "item not found")

    item.name = payload.name
    item.price = payload.price
    session.commit()
    return ItemOut(id=item.id, name=item.name, price=item.price, deleted=item.deleted)


@router2.patch("/item/{item_id}", response_model=ItemOut)
def patch_item(
    item_id: int,
    payload: ItemPatchIn,
    session: Session = Depends(get_session),
) -> ItemOut:
    item = session.get(ItemRow, item_id)
    if item is None or item.deleted:
        raise HTTPException(404, "item not found")

    if "name" in payload.model_fields_set:
        item.name = payload.name or ""
    if "price" in payload.model_fields_set:
        item.price = payload.price or 0.0

    session.commit()
    return ItemOut(id=item.id, name=item.name, price=item.price, deleted=item.deleted)


@router2.delete("/item/{item_id}", status_code=status.HTTP_200_OK)
def delete_item(
    item_id: int,
    session: Session = Depends(get_session),
) -> None:
    item = session.get(ItemRow, item_id)
    if item is None or item.deleted:
        raise HTTPException(404, "item not found")
    item.deleted = True
    session.commit()


@router2.post("/cart", response_model=CartCreateOut, status_code=status.HTTP_201_CREATED)
def create_cart(session: Session = Depends(get_session)) -> CartCreateOut:
    cart = CartRow(price=0.0)
    session.add(cart)
    session.commit()
    return CartCreateOut(id=cart.id)


def _cart_to_out(session: Session, cart: CartRow) -> CartOut:
    rows = session.scalars(
        select(CartItemRow).where(CartItemRow.cart_id == cart.id).order_by(CartItemRow.id)
    ).all()
    return CartOut(
        id=cart.id,
        items=[
            CartItemOut(
                item_id=r.item_id,
                name=r.name,
                quantity=r.quantity,
                available=r.available,
            )
            for r in rows
        ],
        price=cart.price,
    )


@router2.get("/cart/{cart_id}", response_model=CartOut)
def get_cart(
    cart_id: int,
    session: Session = Depends(get_session),
) -> CartOut:
    cart = session.get(CartRow, cart_id)
    if cart is None:
        raise HTTPException(404, "cart not found")
    return _cart_to_out(session, cart)


@router2.get("/cart", response_model=CartListOut)
def list_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
    session: Session = Depends(get_session),
) -> CartListOut:
    total_qty = (
        select(
            CartItemRow.cart_id.label("cart_id"),
            func.sum(CartItemRow.quantity).label("qty"),
        )
        .group_by(CartItemRow.cart_id)
        .subquery()
    )

    filters = []
    if min_price is not None:
        filters.append(CartRow.price >= min_price)
    if max_price is not None:
        filters.append(CartRow.price <= max_price)
    if min_quantity is not None:
        filters.append(func.coalesce(total_qty.c.qty, 0) >= min_quantity)
    if max_quantity is not None:
        filters.append(func.coalesce(total_qty.c.qty, 0) <= max_quantity)

    base = (
        select(CartRow)
        .outerjoin(total_qty, CartRow.id == total_qty.c.cart_id)
        .where(*filters)
    )
    total = session.scalar(
        select(func.count()).select_from(base.subquery())
    ) or 0
    carts = (
        session.scalars(base.order_by(CartRow.id).offset(offset).limit(limit)).all()
    )

    return CartListOut(
        items=[_cart_to_out(session, c) for c in carts],
        total=total,
    )


@router2.post("/cart/{cart_id}/add/{item_id}", response_model=CartOut)
def add_item_to_cart(
    cart_id: int,
    item_id: int,
    session: Session = Depends(get_session),
) -> CartOut:
    cart = session.get(CartRow, cart_id)
    if cart is None:
        raise HTTPException(404, "cart not found")

    item = session.get(ItemRow, item_id)
    if item is None or item.deleted:
        raise HTTPException(404, "item not found")

    cart_item = session.scalar(
        select(CartItemRow).where(
            CartItemRow.cart_id == cart.id,
            CartItemRow.item_id == item.id,
        )
    )
    if cart_item is not None:
        cart_item.quantity += 1
        cart_item.available = not item.deleted
    else:
        session.add(
            CartItemRow(
                cart_id=cart.id,
                item_id=item.id,
                name=item.name,
                quantity=1,
                available=not item.deleted,
            )
        )
    session.flush()

    price = session.scalar(
        select(func.coalesce(func.sum(CartItemRow.quantity * ItemRow.price), 0.0))
        .join(ItemRow, CartItemRow.item_id == ItemRow.id)
        .where(CartItemRow.cart_id == cart.id)
    )
    cart.price = float(price or 0.0)
    session.commit()

    return _cart_to_out(session, cart)
