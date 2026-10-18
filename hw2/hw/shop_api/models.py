from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

ItemPrice = Annotated[
    float,
    Field(
        ge=0,
        allow_inf_nan=False,
    ),
]


class CreateOrReplaceItemRequest(BaseModel):
    name: str
    price: ItemPrice


class PartiallyUpdateItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: ItemPrice | None = None

    @field_validator(
        "name",
        "price",
    )
    @classmethod
    def reject_explicit_null(
        cls,
        value: str | float | None,
    ) -> str | float:
        if value is None:
            raise ValueError("field may be omitted, but must not be null")
        return value


class Item(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool = False


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float
