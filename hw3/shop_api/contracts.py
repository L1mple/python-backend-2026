from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from shop_api.store.models import Cart, Item


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

class ItemCreateIn(StrictRequest):
    name: str = Field(min_length=1)
    price: float = Field(ge=0)

    def to_domain(self) -> Item:
        return Item(id=0, name=self.name, price=self.price, deleted=False)


class ItemPutIn(StrictRequest):
    name: str = Field(min_length=1)
    price: float = Field(ge=0)


class ItemPatchIn(StrictRequest):
    name: str | None = Field(default=None, min_length=1)
    price: float | None = Field(default=None, ge=0)


class ItemOut(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @classmethod
    def from_domain(cls, item: Item) -> "ItemOut":
        return cls(id=item.id, name=item.name, price=item.price, deleted=item.deleted)


class ItemListOut(BaseModel):
    items: list[ItemOut]
    total: int

class CartItemOut(BaseModel):
    item_id: int
    name: str
    quantity: int
    available: bool


class CartCreateOut(BaseModel):
    id: int


class CartOut(BaseModel):
    id: int
    items: list[CartItemOut]
    price: float

    @classmethod
    def from_domain(cls, cart: Cart) -> "CartOut":
        return cls(
            id=cart.id,
            items=[
                CartItemOut(
                    item_id=i.item_id,
                    name=i.name,
                    quantity=i.quantity,
                    available=i.available,
                )
                for i in cart.items
            ],
            price=cart.price,
        )


class CartListOut(BaseModel):
    items: list[CartOut]
    total: int