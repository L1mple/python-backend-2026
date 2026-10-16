from pydantic import BaseModel, NonNegativeInt, PositiveInt, NonNegativeFloat, ConfigDict


class ItemCreateSchema(BaseModel):
    name: str
    price: float


class ItemPatchSchema(BaseModel):
    name: str | None = None
    price: float | None = None

    model_config = ConfigDict(extra='forbid')


class ItemSchema(ItemCreateSchema):
    id: int
    deleted: bool


class BaseFiltersSchema(BaseModel):
    offset: NonNegativeInt = 0
    limit: PositiveInt = 10
    min_price: NonNegativeFloat | None = None
    max_price: NonNegativeFloat | None = None


class ItemFiltersSchema(BaseFiltersSchema):
    show_deleted: bool = False


class CartFiltersSchema(BaseFiltersSchema):
    min_quantity: NonNegativeInt | None = None
    max_quantity: NonNegativeInt | None = None


class CartItemSchema(BaseModel):
    id: int
    name: str
    quantity: PositiveInt
    available: bool


class CartSchema(BaseModel):
    id: int
    items: list[CartItemSchema]
    price: float

