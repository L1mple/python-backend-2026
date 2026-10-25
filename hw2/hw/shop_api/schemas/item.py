from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class ItemListQuery(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(10, gt=0)
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    show_deleted: bool = False


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)

    model_config = ConfigDict(extra="forbid")


class ItemReplace(ItemCreate):
    pass


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    price: Optional[float] = Field(None, gt=0)

    model_config = ConfigDict(extra="forbid")


class ItemDB(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    model_config = ConfigDict(from_attributes=True)