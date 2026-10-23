from pydantic import BaseModel, ConfigDict, NonNegativeFloat
from ...store.models import Item


class ItemRequest(BaseModel):
    name: str
    price: NonNegativeFloat


class ItemPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    price: NonNegativeFloat | None = None


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @staticmethod
    def from_entity(item: Item):
        return ItemResponse(
            id=item.id,
            name=item.name,
            price=item.price,
            deleted=item.deleted,
        )
