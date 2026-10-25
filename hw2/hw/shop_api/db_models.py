from typing import Optional

from sqlmodel import Field, SQLModel


class ItemDB(SQLModel, table=True):
    __tablename__ = "items"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    price: float
    deleted: bool = False


class CartDB(SQLModel, table=True):
    __tablename__ = "carts"

    id: Optional[int] = Field(default=None, primary_key=True)


class CartItemDB(SQLModel, table=True):
    __tablename__ = "cart_items"

    cart_id: int = Field(foreign_key="carts.id", primary_key=True)
    item_id: int = Field(foreign_key="items.id", primary_key=True)
    quantity: int = 1