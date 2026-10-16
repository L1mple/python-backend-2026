from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ItemCreate(BaseModel):
    name: str
    price: float


class ItemUpdate(BaseModel):
    name: str
    price: float


class ItemPatch(BaseModel):
    name: str | None = None
    price: float | None = None

    model_config = ConfigDict(extra="forbid")


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool


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
