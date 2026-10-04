from pydantic import BaseModel, ConfigDict, Field

from ...store import ItemEntity, ItemInfo, PatchItemInfo


class ItemRequest(BaseModel):
    name: str
    price: float = Field(ge=0)

    model_config = ConfigDict(extra="forbid")

    def as_item_info(self) -> ItemInfo:
        return ItemInfo(name=self.name, price=self.price)


class PatchItemRequest(BaseModel):
    name: str | None = None
    price: float | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")

    def as_patch_item_info(self) -> PatchItemInfo:
        return PatchItemInfo(name=self.name, price=self.price)


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @staticmethod
    def from_entity(entity: ItemEntity) -> "ItemResponse":
        return ItemResponse(
            id=entity.id,
            name=entity.info.name,
            price=entity.info.price,
            deleted=entity.deleted,
        )
