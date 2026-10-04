from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt, field_validator

Price = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class ItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: Price


class ItemReplacement(ItemData):
    deleted: bool = False


class Item(ItemReplacement):
    id: int


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: Price | None = None

    @field_validator("name", "price", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class CartItem(BaseModel):
    id: int
    name: str
    quantity: PositiveInt
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


class CartCreated(BaseModel):
    id: int


class PriceFilters(BaseModel):
    offset: NonNegativeInt = 0
    limit: PositiveInt = 10
    min_price: Price | None = None
    max_price: Price | None = None


class ItemFilters(PriceFilters):
    show_deleted: bool = False


class CartFilters(PriceFilters):
    min_quantity: NonNegativeInt | None = None
    max_quantity: NonNegativeInt | None = None
