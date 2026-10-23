from pydantic import BaseModel, ConfigDict

from shop_api.models import CartLine, CartView, ItemEntity


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @staticmethod
    def from_entity(entity: ItemEntity) -> "ItemResponse":
        return ItemResponse(
            id=entity.id,
            name=entity.name,
            price=entity.price,
            deleted=entity.deleted,
        )


class ItemRequest(BaseModel):
    name: str
    price: float

    model_config = ConfigDict(extra="forbid")


class ItemPatchRequest(BaseModel):
    name: str | None = None
    price: float | None = None

    model_config = ConfigDict(extra="forbid")


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool

    @staticmethod
    def from_line(line: CartLine) -> "CartItemResponse":
        return CartItemResponse(
            id=line.id,
            name=line.name,
            quantity=line.quantity,
            available=line.available,
        )


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float

    @staticmethod
    def from_view(view: CartView) -> "CartResponse":
        return CartResponse(
            id=view.id,
            items=[CartItemResponse.from_line(line) for line in view.items],
            price=view.price,
        )


class CartCreatedResponse(BaseModel):
    id: int
