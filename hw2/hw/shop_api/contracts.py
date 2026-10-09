from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .store.models import CartEntity, ItemEntity, ItemInfo, PatchItemInfo


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
    name: str = Field(min_length=1)
    price: float = Field(gt=0)

    model_config = ConfigDict(extra="forbid")

    def as_item_info(self) -> ItemInfo:
        return ItemInfo(name=self.name, price=self.price)


class PatchItemRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    price: float | None = Field(default=None, gt=0)

    model_config = ConfigDict(extra="forbid")

    def as_patch_item_info(self) -> PatchItemInfo:
        return PatchItemInfo(name=self.name, price=self.price)


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
    def from_entity(entity: CartEntity) -> CartResponse:
        return CartResponse(
            id=entity.id,
            items=[
                CartItemResponse(
                    id=item.id,
                    name=item.name,
                    quantity=item.quantity,
                    available=item.available,
                )
                for item in entity.items
            ],
            price=sum(item.price * item.quantity for item in entity.items),
        )
