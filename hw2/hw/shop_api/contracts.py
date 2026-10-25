from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from store import (
    AddItemInfo,
    ItemEntity,
    ItemInfo,
    PatchItemInfo,
    CartEntity,
    CartInfo,
)


# ---------- Item contracts ----------

class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @staticmethod
    def from_entity(entity: ItemEntity) -> ItemResponse:
        return ItemResponse(
            id=entity.id,
            name=entity.info.name,
            price=entity.info.price,
            deleted=entity.info.deleted,
        )


class ItemRequest(BaseModel):
    name: str
    price: float

    def as_add_item_info(self) -> AddItemInfo:
        return AddItemInfo(name=self.name, price=self.price)


class PatchItemRequest(BaseModel):
    name: str | None = None
    price: float | None = None

    model_config = ConfigDict(extra="forbid")

    def as_patch_item_info(self) -> PatchItemInfo:
        return PatchItemInfo(name=self.name, price=self.price)


# ---------- Cart contracts ----------

class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float

    @staticmethod
    def from_entity(entity: CartEntity, item_lookup) -> CartResponse:
        return CartResponse(
            id=entity.id,
            items=[
                CartItemResponse(
                    id=item_id,
                    name=item_lookup(item_id).name,
                    quantity=qty,
                    available=not item_lookup(item_id).deleted,
                )
                for item_id, qty in entity.info.positions.items()
            ],
            price=entity.info.price,
        )


class CartCreatedResponse(BaseModel):
    id: int