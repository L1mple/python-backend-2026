from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class Item(SQLModel, table=True):
    __tablename__ = "items"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    price: float
    deleted: bool = Field(default=False)

    cart_links: List["CartItem"] = Relationship(back_populates="item")


class Cart(SQLModel, table=True):
    __tablename__ = "carts"

    id: Optional[int] = Field(default=None, primary_key=True)

    item_links: List["CartItem"] = Relationship(back_populates="cart")


class CartItem(SQLModel, table=True):
    __tablename__ = "cart_items"

    cart_id: Optional[int] = Field(
        default=None, foreign_key="carts.id", primary_key=True
    )
    item_id: Optional[int] = Field(
        default=None, foreign_key="items.id", primary_key=True
    )
    quantity: int = 1

    cart: Optional[Cart] = Relationship(back_populates="item_links")
    item: Optional[Item] = Relationship(back_populates="cart_links")