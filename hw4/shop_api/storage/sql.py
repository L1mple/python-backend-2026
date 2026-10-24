from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shop_api.models import Item, Cart, CartItem
from shop_api.schema import ItemFiltersSchema, CartFiltersSchema
from shop_api.storage.base import ItemRepository, CartRepository
from shop_api.storage.tables import ItemRecord, CartRecord, CartItemRecord


class SqlItemRepository(ItemRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_model(record: ItemRecord) -> Item:
        return Item(id=record.id, name=record.name, price=record.price, deleted=record.deleted)

    async def get(self, item_id: int) -> Item | None:
        record = await self._session.get(ItemRecord, item_id, populate_existing=True)
        return self._to_model(record) if record else None

    async def get_all(self, filters: ItemFiltersSchema) -> list[Item]:
        stmt = select(ItemRecord)
        if not filters.show_deleted:
            stmt = stmt.where(ItemRecord.deleted.is_(False))
        if filters.min_price is not None:
            stmt = stmt.where(ItemRecord.price >= filters.min_price)
        if filters.max_price is not None:
            stmt = stmt.where(ItemRecord.price <= filters.max_price)
        stmt = stmt.order_by(ItemRecord.id).offset(filters.offset).limit(filters.limit)
        return [self._to_model(record) for record in await self._session.scalars(stmt)]

    async def add(self, item: Item) -> Item:
        result = await self._session.execute(
            insert(ItemRecord)
            .values(name=item.name, price=item.price, deleted=item.deleted)
            .returning(ItemRecord.id)
        )
        item.id = result.scalar_one()
        await self._session.commit()
        return item

    async def save(self, item: Item) -> Item:
        await self._session.execute(
            update(ItemRecord)
            .where(ItemRecord.id == item.id)
            .values(name=item.name, price=item.price, deleted=item.deleted)
        )
        await self._session.commit()
        return item

    async def mark_deleted(self, item_id: int) -> None:
        await self._session.execute(update(ItemRecord).where(ItemRecord.id == item_id).values(deleted=True))
        await self._session.commit()


class SqlCartRepository(CartRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_model(record: CartRecord) -> Cart:
        cart = Cart(id=record.id)
        for row in record.items:
            cart.items.append(CartItem(
                id=row.item.id,
                name=row.item.name,
                quantity=row.quantity,
                available=not row.item.deleted,
            ))
            cart.price += row.item.price * row.quantity
            cart.quantity += row.quantity
        return cart

    async def get(self, cart_id: int) -> Cart | None:
        record = await self._session.get(CartRecord, cart_id, populate_existing=True)
        return self._to_model(record) if record else None

    async def get_all(self, filters: CartFiltersSchema) -> list[Cart]:
        price = func.coalesce(func.sum(ItemRecord.price * CartItemRecord.quantity), 0.0)
        quantity = func.coalesce(func.sum(CartItemRecord.quantity), 0)

        ids_stmt = (
            select(CartRecord.id)
            .outerjoin(CartItemRecord, CartItemRecord.cart_id == CartRecord.id)
            .outerjoin(ItemRecord, ItemRecord.id == CartItemRecord.item_id)
            .group_by(CartRecord.id)
        )
        if filters.min_price is not None:
            ids_stmt = ids_stmt.having(price >= filters.min_price)
        if filters.max_price is not None:
            ids_stmt = ids_stmt.having(price <= filters.max_price)
        if filters.min_quantity is not None:
            ids_stmt = ids_stmt.having(quantity >= filters.min_quantity)
        if filters.max_quantity is not None:
            ids_stmt = ids_stmt.having(quantity <= filters.max_quantity)
        ids_stmt = ids_stmt.order_by(CartRecord.id).offset(filters.offset).limit(filters.limit)

        stmt = (
            select(CartRecord)
            .where(CartRecord.id.in_(ids_stmt.scalar_subquery()))
            .order_by(CartRecord.id)
            .execution_options(populate_existing=True)
        )
        return [self._to_model(record) for record in await self._session.scalars(stmt)]

    async def add(self) -> Cart:
        result = await self._session.execute(insert(CartRecord).returning(CartRecord.id))
        cart_id = result.scalar_one()
        await self._session.commit()
        return Cart(id=cart_id)

    async def add_item(self, cart_id: int, item_id: int) -> None:
        stmt = insert(CartItemRecord).values(cart_id=cart_id, item_id=item_id, quantity=1)
        stmt = stmt.on_conflict_do_update(
            index_elements=[CartItemRecord.cart_id, CartItemRecord.item_id],
            set_={'quantity': CartItemRecord.quantity + 1},
        )
        await self._session.execute(stmt)
        await self._session.commit()
