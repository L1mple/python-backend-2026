from dataclasses import dataclass, field
from typing import List, Dict, TypeAlias
from typing import Dict, List, Optional

from sqlalchemy import (
    Boolean, Column, Float, ForeignKey, Integer, String, DateTime,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base

@dataclass(slots=True)
class AddItemInfo:
    name: str
    price: float

@dataclass(slots=True)
class ItemInfo:
    name: str
    price: float
    deleted: bool = False

@dataclass(slots=True)
class ItemEntity:
    id: int
    info: ItemInfo

@dataclass(slots=True)
class PatchItemInfo:
    name: str|None
    price: float|None

CartPositionsInfo : TypeAlias = Dict[int, int]

@dataclass(slots=True)
class CartInfo:
    positions: CartPositionsInfo = field(default_factory=dict)
    price: float = 0
    quantity: int = 0

@dataclass(slots=True)
class CartEntity:
    id: int
    info: CartInfo = field(default_factory=CartInfo)

class ItemOrm(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class CartOrm(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=func.now())

    positions = relationship("CartPositionOrm", back_populates="cart", cascade="all, delete-orphan")


class CartPositionOrm(Base):
    __tablename__ = "cart_positions"

    cart_id = Column(Integer, ForeignKey("carts.id"), primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), primary_key=True)
    quantity = Column(Integer, nullable=False, default=1)

    cart = relationship("CartOrm", back_populates="positions")


# === Mappers ===

class ItemMapper:
    @staticmethod
    def to_domain(orm: ItemOrm) -> ItemEntity:
        return ItemEntity(
            id=orm.id,
            info=ItemInfo(name=orm.name, price=orm.price, deleted=orm.deleted),
        )

    @staticmethod
    def to_orm(domain_info: ItemInfo, orm: Optional[ItemOrm] = None) -> ItemOrm:
        if orm is None:
            orm = ItemOrm()
        orm.name = domain_info.name
        orm.price = domain_info.price
        orm.deleted = domain_info.deleted
        return orm


class CartMapper:
    @staticmethod
    def to_domain(orm: CartOrm, item_lookup) -> CartEntity:
        positions: CartPositionsInfo = {}
        price = 0.0
        quantity = 0
        for pos in orm.positions:
            positions[pos.item_id] = pos.quantity
            item_info = item_lookup(pos.item_id)  # ItemInfo
            price += item_info.price * pos.quantity
            quantity += pos.quantity
        return CartEntity(
            id=orm.id,
            info=CartInfo(positions=positions, price=price, quantity=quantity),
        )