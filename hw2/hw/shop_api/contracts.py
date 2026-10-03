from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

class ItemCreate(BaseModel):
    name: str
    price: float = Field(ge=0)

class Item(ItemCreate):
    id: int
    deleted: bool = False

class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0)

class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool

class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float