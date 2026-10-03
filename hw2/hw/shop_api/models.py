from pydantic import BaseModel, ConfigDict


class Item(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

class NewItem(BaseModel):
    name: str
    price: float

class UpdateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = None


class Cart(BaseModel):
    id: int
    items: list
    price: float

class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool