from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict

from store.item.models import (
    ItemInfo,
    ItemEntity,
    PatchItemInfo
)


class ItemResponse(BaseModel):
    id: int
    name: str
    price: Decimal

    model_config = ConfigDict(
        json_encoders={
            Decimal: lambda v: float(v)
        }
    )

    @staticmethod
    def from_entity(entity: ItemEntity) -> "ItemResponse":
        return ItemResponse(
            id=entity.id,
            name=entity.name,
            price=entity.price,
        )


class ItemRequest(BaseModel):
    name: str
    price: Decimal = Field(ge=0)

    model_config = ConfigDict(
        extra="forbid",
        json_encoders={
            Decimal: lambda v: float(v)
        }
    )

    def as_item_info(self) -> ItemInfo:
        return ItemInfo(name=self.name, price=self.price)


class PatchItemRequest(BaseModel):
    name: str | None = None
    price: Decimal | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")

    def as_patch_item_info(self) -> PatchItemInfo:
        data = self.model_dump(exclude_unset=True)

        if not data:
            return PatchItemInfo.model_construct()
        return PatchItemInfo(**data)
