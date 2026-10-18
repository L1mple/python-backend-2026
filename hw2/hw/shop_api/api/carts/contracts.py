from pydantic import BaseModel

from ...store import ItemEntity


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool

    @staticmethod
    def from_parts(item: ItemEntity, quantity: int) -> "CartItemResponse":
        return CartItemResponse(
            id=item.id,
            name=item.info.name,
            quantity=quantity,
            available=not item.deleted,
        )


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float
