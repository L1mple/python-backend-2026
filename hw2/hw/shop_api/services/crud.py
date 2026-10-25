from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shop_api.core.db import Base


class CRUDBase:
    def __init__(self, model: type[Base], session: AsyncSession):
        self.model = model
        self.session = session

    async def create(self, obj_in: BaseModel | None = None):
        data = obj_in.model_dump() if obj_in is not None else {}
        new_obj = self.model(**data)
        self.session.add(new_obj)
        await self.session.flush()
        return new_obj

    async def get_by_id(self, obj_id: int):
        db_obj = await self.session.execute(
            select(self.model).where(self.model.id == obj_id)
        )
        return db_obj.scalars().first()

    async def get_all(self):
        db_objs = await self.session.execute(
            select(self.model).order_by(self.model.id)
        )
        return list(db_objs.scalars().all())

    async def update(
        self, db_obj: Base, obj_in: BaseModel
    ):
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        await self.session.flush()
        return db_obj

    async def remove(self, db_obj: Base):
        await self.session.delete(db_obj)
        await self.session.flush()
        return db_obj
