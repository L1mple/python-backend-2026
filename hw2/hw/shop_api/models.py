from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


Price = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class ItemData(BaseModel):
    name: str
    price: Price
    deleted: bool = False


class Item(ItemData):
    id: int


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: Price | None = None

    @field_validator("name", "price")
    @classmethod
    def reject_null(cls, value: str | float | None) -> str | float:
        if value is None:
            raise ValueError("Item fields cannot be null")
        return value


class CartCreated(BaseModel):
    id: int


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float
