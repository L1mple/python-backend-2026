from pydantic import BaseModel, ConfigDict, Field

class ItemCreate(BaseModel):
    name: str
    price: float = Field(ge=0)
    model_config = ConfigDict(extra="forbid")

class ItemPut(BaseModel):
    name: str
    price: float = Field(ge=0)
    model_config = ConfigDict(extra="forbid")

class ItemPatch(BaseModel):
    name: str | None = None
    price: float | None = Field(default=None, ge=0)
    model_config = ConfigDict(extra="forbid")

class ItemResponse(BaseModel):
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