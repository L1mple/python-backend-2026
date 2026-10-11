import os

from fastapi import HTTPException
from sqlalchemy import case, create_engine, event, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from .database import Base, CartPosition, CartRow, ItemRow
from .models import Cart, CartItem, Item, ItemInput, ItemPatch


class Shop:
    """Transactional inventory and carts."""

    def __init__(self, database_url: str | URL | None = None):
        url = database_url or os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://shop:local-homework@127.0.0.1:15432/shop",
        )
        self.engine = create_engine(url, pool_pre_ping=True)
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", self._sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @staticmethod
    def _sqlite_foreign_keys(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @staticmethod
    def _item(row: ItemRow) -> Item:
        return Item(id=row.id, name=row.name, price=row.price, deleted=row.deleted)

    @staticmethod
    def _get_item(session: Session, item_id: int, include_deleted=False) -> ItemRow:
        row = session.get(ItemRow, item_id)
        if row is None or (row.deleted and not include_deleted):
            raise HTTPException(404, "Item not found")
        return row

    def create_item(self, data: ItemInput) -> Item:
        with self.sessions.begin() as session:
            row = ItemRow(**data.model_dump())
            session.add(row)
            session.flush()
            return self._item(row)

    def get_item(self, item_id: int, include_deleted: bool = False) -> Item:
        with self.sessions() as session:
            return self._item(self._get_item(session, item_id, include_deleted))

    def list_items(self, offset, limit, min_price, max_price, show_deleted):
        query = select(ItemRow).order_by(ItemRow.id)
        if not show_deleted:
            query = query.where(ItemRow.deleted.is_(False))
        if min_price is not None:
            query = query.where(ItemRow.price >= min_price)
        if max_price is not None:
            query = query.where(ItemRow.price <= max_price)
        with self.sessions() as session:
            return [
                self._item(row)
                for row in session.scalars(query.offset(offset).limit(limit))
            ]

    def replace_item(self, item_id: int, data: ItemInput) -> Item:
        with self.sessions.begin() as session:
            row = self._get_item(session, item_id, include_deleted=True)
            for field, value in data.model_dump().items():
                setattr(row, field, value)
            session.flush()
            return self._item(row)

    def patch_item(self, item_id: int, data: ItemPatch) -> Item | None:
        with self.sessions.begin() as session:
            row = self._get_item(session, item_id, include_deleted=True)
            if row.deleted:
                return None
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(row, field, value)
            session.flush()
            return self._item(row)

    def delete_item(self, item_id: int):
        with self.sessions.begin() as session:
            self._get_item(session, item_id, include_deleted=True).deleted = True

    def create_cart(self) -> int:
        with self.sessions.begin() as session:
            row = CartRow()
            session.add(row)
            session.flush()
            return row.id

    @staticmethod
    def _carts(session: Session, cart_ids: list[int]) -> list[Cart]:
        carts = {cart_id: Cart(id=cart_id, items=[], price=0) for cart_id in cart_ids}
        query = (
            select(CartPosition, ItemRow)
            .join(ItemRow)
            .where(CartPosition.cart_id.in_(cart_ids))
            .order_by(CartPosition.id)
        )
        for position, item in session.execute(query):
            cart = carts[position.cart_id]
            cart.items.append(
                CartItem(
                    id=item.id,
                    name=item.name,
                    quantity=position.quantity,
                    available=not item.deleted,
                )
            )
            if not item.deleted:
                cart.price += item.price * position.quantity
        return list(carts.values())

    def get_cart(self, cart_id: int) -> Cart:
        with self.sessions() as session:
            if session.get(CartRow, cart_id) is None:
                raise HTTPException(404, "Cart not found")
            return self._carts(session, [cart_id])[0]

    def list_carts(
        self, offset, limit, min_price, max_price, min_quantity, max_quantity
    ):
        totals = (
            select(
                CartRow.id,
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ItemRow.deleted.is_(False),
                                ItemRow.price * CartPosition.quantity,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("price"),
                func.coalesce(func.sum(CartPosition.quantity), 0).label("quantity"),
            )
            .select_from(CartRow)
            .outerjoin(CartPosition)
            .outerjoin(ItemRow)
            .group_by(CartRow.id)
            .subquery()
        )
        query = select(totals.c.id).order_by(totals.c.id)
        for column, lower, upper in (
            (totals.c.price, min_price, max_price),
            (totals.c.quantity, min_quantity, max_quantity),
        ):
            if lower is not None:
                query = query.where(column >= lower)
            if upper is not None:
                query = query.where(column <= upper)
        with self.sessions() as session:
            ids = list(session.scalars(query.offset(offset).limit(limit)))
            return self._carts(session, ids)

    def add_item(self, cart_id: int, item_id: int) -> Cart:
        with self.sessions.begin() as session:
            if session.get(CartRow, cart_id) is None:
                raise HTTPException(404, "Cart not found")
            item = session.scalar(
                select(ItemRow).where(ItemRow.id == item_id).with_for_update(read=True)
            )
            if item is None or item.deleted:
                raise HTTPException(404, "Item not found")
            insert = (
                pg_insert if self.engine.dialect.name == "postgresql" else sqlite_insert
            )
            statement = insert(CartPosition).values(
                cart_id=cart_id, item_id=item_id, quantity=1
            )
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=[CartPosition.cart_id, CartPosition.item_id],
                    set_={"quantity": CartPosition.quantity + 1},
                )
            )
            return self._carts(session, [cart_id])[0]
