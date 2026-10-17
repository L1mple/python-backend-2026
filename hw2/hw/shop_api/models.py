from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

Price = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Name = Annotated[str, Field(min_length=1)]


class ItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    price: Price
    deleted: bool = False


class Item(ItemData):
    id: int


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    price: Price | None = None

    @field_validator("name", "price")
    @classmethod
    def reject_null(cls, value: str | float | None) -> str | float:
        if value is None:
            raise ValueError("The field must not be null")
        return value


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: Price


class CartCreated(BaseModel):
    id: int
