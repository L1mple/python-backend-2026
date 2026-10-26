from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from store.db import Base


@dataclass(slots=True)
class ItemEntity:
    id: int
    name: str
    price: float
    deleted: bool = False


class ItemOrm(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float]
    deleted: Mapped[bool] = mapped_column(default=False)

    def to_entity(self) -> ItemEntity:
        return ItemEntity(
            id=self.id,
            name=self.name,
            price=self.price,
            deleted=self.deleted,
        )
