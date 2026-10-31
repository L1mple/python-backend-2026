from pydantic import BaseModel, ConfigDict

from shop_api.store import ItemInfo


class ItemCreateRequest(BaseModel):
    name: str
    price: float


class ItemPutRequest(BaseModel):
    name: str
    price: float


class ItemPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = None


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @classmethod
    def from_entity(cls, item: ItemInfo) -> "ItemResponse":
        return cls(id=item.id, name=item.name, price=item.price, deleted=item.deleted)


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float