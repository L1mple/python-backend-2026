from sqlalchemy import (
    Select,
    case,
    create_engine,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import (
    Session,
    selectinload,
    sessionmaker,
)

from shop_api.database import (
    Base,
    CartItemRecord,
    CartRecord,
    ItemRecord,
)
from shop_api.models import (
    Cart,
    CartItem,
    Item,
)

# Ids are INTEGER columns: Postgres fails on a larger number in a query instead of finding nothing
SMALLEST_RECORD_ID = -(2**31)
LARGEST_RECORD_ID = 2**31 - 1

PRICE_OF_AVAILABLE_ITEMS_IN_CART = func.sum(
    case(
        (ItemRecord.deleted.is_(False), ItemRecord.price * CartItemRecord.quantity),
        else_=0.0,
    )
)
QUANTITY_OF_ALL_ITEMS_IN_CART = func.coalesce(
    func.sum(CartItemRecord.quantity),
    0,
)


class DatabaseShopStorage:
    def __init__(
        self,
        database_url: str,
    ) -> None:
        engine = create_engine(database_url)
        Base.metadata.create_all(bind=engine)
        self.session_factory = sessionmaker(bind=engine)

    def create_item(
        self,
        name: str,
        price: float,
    ) -> Item:
        with self.session_factory.begin() as session:
            new_item_record = ItemRecord(
                name=name,
                price=price,
            )
            session.add(new_item_record)
            session.flush()
            return _convert_item_record_to_item(item_record=new_item_record)

    def get_item_by_id(
        self,
        item_id: int,
    ) -> Item | None:
        with self.session_factory.begin() as session:
            item_record = _get_item_record_by_id(
                session=session,
                item_id=item_id,
                lock_for_update=False,
            )
            if item_record is None:
                return None
            return _convert_item_record_to_item(item_record=item_record)

    def list_items_page_filtered_by_price(
        self,
        offset: int,
        limit: int,
        min_price: float | None,
        max_price: float | None,
        show_deleted: bool,
    ) -> list[Item]:
        items_query = select(ItemRecord)
        if not show_deleted:
            items_query = items_query.where(ItemRecord.deleted.is_(False))
        if min_price is not None:
            items_query = items_query.where(ItemRecord.price >= min_price)
        if max_price is not None:
            items_query = items_query.where(ItemRecord.price <= max_price)
        page_of_items_query = items_query.order_by(ItemRecord.id).offset(offset).limit(limit)

        with self.session_factory.begin() as session:
            return [
                _convert_item_record_to_item(item_record=item_record)
                for item_record in session.scalars(page_of_items_query)
            ]

    def update_item_fields_by_id(
        self,
        item_id: int,
        changed_item_fields: dict[str, str | float],
    ) -> Item | None:
        with self.session_factory.begin() as session:
            item_record = _get_item_record_by_id(
                session=session,
                item_id=item_id,
                lock_for_update=True,
            )
            if item_record is None:
                return None
            # A deleted item is returned unchanged: PUT answers 404 for it, PATCH answers 304
            if not item_record.deleted:
                for field_name, new_value in changed_item_fields.items():
                    setattr(
                        item_record,
                        field_name,
                        new_value,
                    )
            return _convert_item_record_to_item(item_record=item_record)

    def mark_item_as_deleted_by_id(
        self,
        item_id: int,
    ) -> Item | None:
        with self.session_factory.begin() as session:
            item_record = _get_item_record_by_id(
                session=session,
                item_id=item_id,
                lock_for_update=True,
            )
            if item_record is None:
                return None
            item_record.deleted = True
            return _convert_item_record_to_item(item_record=item_record)

    def create_empty_cart(self) -> int:
        with self.session_factory.begin() as session:
            new_cart_record = CartRecord()
            session.add(new_cart_record)
            session.flush()
            return new_cart_record.id

    def cart_exists(
        self,
        cart_id: int,
    ) -> bool:
        if not SMALLEST_RECORD_ID <= cart_id <= LARGEST_RECORD_ID:
            return False
        with self.session_factory.begin() as session:
            cart_record = session.get(
                entity=CartRecord,
                ident=cart_id,
            )
            return cart_record is not None

    def increase_item_quantity_in_cart_by_one(
        self,
        cart_id: int,
        item_id: int,
    ) -> None:
        # Upsert is one atomic statement, so concurrent additions to the same cart do not lose increments
        add_one_item_to_cart_query = (
            insert(CartItemRecord)
            .values(
                cart_id=cart_id,
                item_id=item_id,
                quantity=1,
            )
            .on_conflict_do_update(
                index_elements=[CartItemRecord.cart_id, CartItemRecord.item_id],
                set_={"quantity": CartItemRecord.quantity + 1},
            )
        )
        with self.session_factory.begin() as session:
            session.execute(add_one_item_to_cart_query)

    def get_cart_by_id(
        self,
        cart_id: int,
    ) -> Cart | None:
        if not SMALLEST_RECORD_ID <= cart_id <= LARGEST_RECORD_ID:
            return None
        found_carts = self._build_carts(carts_query=_select_carts_with_price().where(CartRecord.id == cart_id))
        return found_carts[0] if found_carts else None

    def list_carts_page_filtered_by_price_and_quantity(
        self,
        offset: int,
        limit: int,
        min_price: float | None,
        max_price: float | None,
        min_quantity: int | None,
        max_quantity: int | None,
    ) -> list[Cart]:
        carts_query = _select_carts_with_price()
        if min_price is not None:
            carts_query = carts_query.having(PRICE_OF_AVAILABLE_ITEMS_IN_CART >= min_price)
        if max_price is not None:
            carts_query = carts_query.having(PRICE_OF_AVAILABLE_ITEMS_IN_CART <= max_price)
        if min_quantity is not None:
            carts_query = carts_query.having(QUANTITY_OF_ALL_ITEMS_IN_CART >= min_quantity)
        if max_quantity is not None:
            carts_query = carts_query.having(QUANTITY_OF_ALL_ITEMS_IN_CART <= max_quantity)
        page_of_carts_query = carts_query.order_by(CartRecord.id).offset(offset).limit(limit)
        return self._build_carts(carts_query=page_of_carts_query)

    def _build_carts(
        self,
        carts_query: Select,
    ) -> list[Cart]:
        with self.session_factory.begin() as session:
            # Carts and their items are read by two queries, REPEATABLE READ gives both the same snapshot
            session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            return [
                Cart(
                    id=cart_record.id,
                    items=[
                        CartItem(
                            id=cart_item_record.item_id,
                            name=cart_item_record.item.name,
                            quantity=cart_item_record.quantity,
                            available=not cart_item_record.item.deleted,
                        )
                        for cart_item_record in cart_record.cart_items
                    ],
                    price=price_of_cart,
                )
                for cart_record, price_of_cart in session.execute(carts_query)
            ]


def _get_item_record_by_id(
    session: Session,
    item_id: int,
    lock_for_update: bool,
) -> ItemRecord | None:
    if not SMALLEST_RECORD_ID <= item_id <= LARGEST_RECORD_ID:
        return None
    return session.get(
        entity=ItemRecord,
        ident=item_id,
        with_for_update=lock_for_update,
    )


def _convert_item_record_to_item(
    item_record: ItemRecord,
) -> Item:
    return Item.model_validate(
        obj=item_record,
        from_attributes=True,
    )


def _select_carts_with_price() -> Select:
    return (
        select(
            CartRecord,
            PRICE_OF_AVAILABLE_ITEMS_IN_CART,
        )
        .outerjoin(CartRecord.cart_items)
        .outerjoin(CartItemRecord.item)
        .group_by(CartRecord.id)
        .options(selectinload(CartRecord.cart_items).joinedload(CartItemRecord.item))
    )
