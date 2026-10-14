from pydantic import BaseModel, ConfigDict, Field, field_validator


class ItemCreate(BaseModel):
    name: str
    price: float = Field(ge=0, allow_inf_nan=False)


class ItemReplace(BaseModel):
    name: str
    price: float = Field(ge=0, allow_inf_nan=False)


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("name", "price")
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError("You cannot provide null fields")
        return value


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float
    deleted: bool


class CartCreated(BaseModel):
    id: int


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float
