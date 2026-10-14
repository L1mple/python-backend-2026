from pydantic import BaseModel, ConfigDict, Field, field_validator


class ItemInput(BaseModel):
    """Editable item fields."""

    name: str
    price: float = Field(ge=0, allow_inf_nan=False)
    deleted: bool = False


class Item(ItemInput):
    """Stored item with a server identifier."""

    id: int


class ItemPatch(BaseModel):
    """Allowed partial item changes."""

    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("name", "price")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Value cannot be null")
        return value


class CartItem(BaseModel):
    """Current item information and cart quantity."""

    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    """Cart representation with the current total price."""

    id: int
    items: list[CartItem]
    price: float
