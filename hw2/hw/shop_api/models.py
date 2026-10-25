from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    @model_validator(mode="after")
    def reject_null_fields(self) -> "ItemPatch":
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("name and price cannot be null")
        return self


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


class ListFilters(BaseModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=10, gt=0)
    min_price: Price | None = None
    max_price: Price | None = None


class ItemFilters(ListFilters):
    show_deleted: bool = False


class CartFilters(ListFilters):
    min_quantity: int | None = Field(default=None, ge=0)
    max_quantity: int | None = Field(default=None, ge=0)
