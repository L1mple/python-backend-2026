"""Request and response schemas for the shop API."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

Name = Annotated[str, Field(min_length=1)]
Price = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class ItemData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Name
    price: Price
    deleted: bool = False


class Item(ItemData):
    id: int


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Name | None = None
    price: Price | None = None

    @field_validator("name", "price")
    @classmethod
    def reject_null(cls, value: str | float | None) -> str | float:
        """Omitted fields are allowed; explicit null cannot replace item data."""
        if value is None:
            raise ValueError("Item fields cannot be null")
        return value


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


class CartCreated(BaseModel):
    id: int
