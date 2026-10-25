from shop_api.models.item import Item
from shop_api.schemas.item import ItemCreate, ItemListQuery, ItemUpdate, ItemReplace
from shop_api.services.exceptions import ItemNotFoundError
from shop_api.services.crud import CRUDBase
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


class ItemService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CRUDBase(Item, session)

    async def create_item(self, obj_in: ItemCreate) -> Item:
        return await self.crud.create(obj_in)

    async def get_items(self, query: ItemListQuery) -> list[Item]:
        selection = select(Item)
        if not query.show_deleted:
            selection = selection.where(Item.deleted.is_(False))
        if query.min_price is not None:
            selection = selection.where(Item.price >= query.min_price)
        if query.max_price is not None:
            selection = selection.where(Item.price <= query.max_price)
        selection = selection.order_by(Item.id).limit(query.limit).offset(query.offset)
        db_objs = await self.session.execute(selection)
        return list(db_objs.scalars().all())

    async def get_item_by_id(self, item_id: int) -> Item:
        item = await self.crud.get_by_id(item_id)
        if item is None:
            raise ItemNotFoundError(f"Item with id {item_id} not found")
        return item

    async def get_active_item_by_id(self, item_id: int) -> Item:
        item = await self.get_item_by_id(item_id)
        if item.deleted:
            raise ItemNotFoundError(f"Item with id {item_id} not found")
        return item

    async def update_item_by_id(self, obj_in: ItemReplace | ItemUpdate, item_id: int):
        item = await self.get_item_by_id(item_id)
        return await self.crud.update(item, obj_in)

    async def delete_item_by_id(self, item_id: int) -> Item:
        item = await self.get_item_by_id(item_id)
        item.deleted = True
        await self.session.flush()
        return item
