from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)


class CreateOrReplaceItemRequest(BaseModel):
    name: str
    price: float


class PartiallyUpdateItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = None

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
