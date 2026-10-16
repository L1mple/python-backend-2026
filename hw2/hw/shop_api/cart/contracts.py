from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from store.cart.models import Cart


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: Decimal

    model_config = ConfigDict(
        json_encoders={
            Decimal: lambda v: float(v)
        }
    )

    @staticmethod
    def from_entity(entity: Cart) -> "CartResponse":
        return CartResponse(
            id=entity.id,
            price=entity.price,
            items=[
                CartItemResponse(
                    id=ci.item.id,
                    name=ci.item.name,
                    quantity=ci.quantity,
                    available=not ci.item.deleted
                )
                for ci in entity.items
            ]
        )
