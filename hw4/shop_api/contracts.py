"""Контракты API (тела запросов и ответов)."""

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, model_validator


class ItemRequest(BaseModel):
    """Тело POST /item и PUT /item/{id}: товар целиком."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    price: NonNegativeFloat


class PatchItemRequest(BaseModel):
    """Тело PATCH /item/{id}: любое подмножество полей, кроме `deleted`."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    price: NonNegativeFloat | None = None

    @model_validator(mode="after")
    def _no_explicit_nulls(self) -> "PatchItemRequest":
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be null")
        return self


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float
    deleted: bool = False


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float


class CartCreatedResponse(BaseModel):
    id: int
