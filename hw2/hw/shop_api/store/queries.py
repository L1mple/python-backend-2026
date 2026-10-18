from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from .db import CartItemRow, CartRow, ItemRow, Session
from .models import (
    CartEntity,
    CartItem,
    ItemEntity,
    ItemInfo,
    PatchItemInfo,
)

# ---------------------------------------------------------------- items


def add_item(info: ItemInfo) -> ItemEntity:
    with Session.begin() as session:
        row = ItemRow(name=info.name, price=info.price, deleted=info.deleted)
        session.add(row)
        session.flush()

        return _as_item_entity(row)


def get_item(id: int) -> ItemEntity | None:
    """Возвращает товар, даже если он помечен удаленным.

    Отфильтровать удаленный товар — ответственность ручки: корзине он нужен,
    чтобы показать позицию как недоступную.
    """
    with Session() as session:
        row = session.get(ItemRow, id)

        return None if row is None else _as_item_entity(row)


def get_many_items(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> Iterable[ItemEntity]:
    query = select(ItemRow).order_by(ItemRow.id).offset(offset).limit(limit)

    if not show_deleted:
        query = query.where(ItemRow.deleted.is_(False))
    if min_price is not None:
        query = query.where(ItemRow.price >= min_price)
    if max_price is not None:
        query = query.where(ItemRow.price <= max_price)

    with Session() as session:
        return [_as_item_entity(row) for row in session.scalars(query)]


def update_item(id: int, info: ItemInfo) -> ItemEntity | None:
    """Полная замена существующего товара; создание новых запрещено."""
    with Session.begin() as session:
        row = session.get(ItemRow, id, with_for_update=True)

        if row is None or row.deleted:
            return None

        # флаг deleted не является частью представления товара и не заменяется
        row.name = info.name
        row.price = info.price

        return _as_item_entity(row)


def patch_item(id: int, patch_info: PatchItemInfo) -> ItemEntity | None:
    with Session.begin() as session:
        row = session.get(ItemRow, id, with_for_update=True)

        if row is None or row.deleted:
            return None

        if patch_info.name is not None:
            row.name = patch_info.name

        if patch_info.price is not None:
            row.price = patch_info.price

        return _as_item_entity(row)


def delete_item(id: int) -> None:
    """Мягкое удаление: запись остается, чтобы корзины сохранили свои позиции."""
    with Session.begin() as session:
        row = session.get(ItemRow, id)

        if row is not None:
            row.deleted = True


# ---------------------------------------------------------------- carts


def add_cart() -> CartEntity:
    with Session.begin() as session:
        row = CartRow()
        session.add(row)
        session.flush()

        return CartEntity(id=row.id, items=[], price=0.0)


def get_cart(id: int) -> CartEntity | None:
    with Session() as session:
        if session.get(CartRow, id) is None:
            return None

        return _load_carts(session, [id])[0]


def get_many_carts(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = None,
    max_quantity: int | None = None,
) -> Iterable[CartEntity]:
    price = func.coalesce(func.sum(ItemRow.price * CartItemRow.quantity), 0.0)
    quantity = func.coalesce(func.sum(CartItemRow.quantity), 0)

    query = (
        select(CartRow.id)
        .outerjoin(CartItemRow, CartItemRow.cart_id == CartRow.id)
        .outerjoin(ItemRow, ItemRow.id == CartItemRow.item_id)
        .group_by(CartRow.id)
        .order_by(CartRow.id)
        .offset(offset)
        .limit(limit)
    )

    if min_price is not None:
        query = query.having(price >= min_price)
    if max_price is not None:
        query = query.having(price <= max_price)
    if min_quantity is not None:
        query = query.having(quantity >= min_quantity)
    if max_quantity is not None:
        query = query.having(quantity <= max_quantity)

    with Session() as session:
        return _load_carts(session, list(session.scalars(query)))


def add_item_to_cart(cart_id: int, item_id: int) -> CartEntity | None:
    """Кладет товар в корзину, увеличивая количество, если он там уже есть."""
    with Session.begin() as session:
        if session.get(CartRow, cart_id) is None or session.get(ItemRow, item_id) is None:
            return None

        # upsert атомарен: параллельные добавления не потеряют приращение
        session.execute(
            insert(CartItemRow)
            .values(cart_id=cart_id, item_id=item_id, quantity=1)
            .on_conflict_do_update(
                index_elements=[CartItemRow.cart_id, CartItemRow.item_id],
                set_={"quantity": CartItemRow.quantity + 1},
            )
        )

        return _load_carts(session, [cart_id])[0]


# ---------------------------------------------------------------- helpers


def _as_item_entity(row: ItemRow) -> ItemEntity:
    return ItemEntity(
        id=row.id,
        info=ItemInfo(name=row.name, price=row.price, deleted=row.deleted),
    )


def _load_carts(session, cart_ids: list[int]) -> list[CartEntity]:
    """Собирает представление корзин из актуальных данных товаров."""
    positions = session.execute(
        select(CartItemRow.cart_id, ItemRow, CartItemRow.quantity)
        .join(ItemRow, ItemRow.id == CartItemRow.item_id)
        .where(CartItemRow.cart_id.in_(cart_ids))
        .order_by(CartItemRow.cart_id, CartItemRow.item_id)
    )

    items: dict[int, list[CartItem]] = {id: [] for id in cart_ids}
    prices: dict[int, float] = {id: 0.0 for id in cart_ids}

    for cart_id, item, quantity in positions:
        items[cart_id].append(
            CartItem(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )
        prices[cart_id] += item.price * quantity

    return [CartEntity(id=id, items=items[id], price=prices[id]) for id in cart_ids]
