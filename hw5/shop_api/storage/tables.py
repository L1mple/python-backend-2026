from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ItemRecord(Base):
    __tablename__ = 'items'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float]
    deleted: Mapped[bool] = mapped_column(default=False, server_default='false')


class CartRecord(Base):
    __tablename__ = 'carts'

    id: Mapped[int] = mapped_column(primary_key=True)
    items: Mapped[list['CartItemRecord']] = relationship(lazy='selectin', order_by='CartItemRecord.item_id')


class CartItemRecord(Base):
    __tablename__ = 'cart_items'

    cart_id: Mapped[int] = mapped_column(ForeignKey('carts.id', ondelete='CASCADE'), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('items.id', ondelete='CASCADE'), primary_key=True)
    quantity: Mapped[int] = mapped_column(default=1)

    item: Mapped[ItemRecord] = relationship(lazy='joined')
