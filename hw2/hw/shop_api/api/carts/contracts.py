from pydantic import BaseModel

from ...store.models import CartItem, CartWithPrice


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool

    @staticmethod
    def from_entity(cart_item: CartItem) -> "CartItemResponse":
        return CartItemResponse(
            id=cart_item.item_id,
            name=cart_item.item.name,
            quantity=cart_item.quantity,
            available=not cart_item.item.deleted,
        )


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float

    @staticmethod
    def from_entity(cart_with_price: CartWithPrice) -> "CartResponse":
        cart, price = cart_with_price
        return CartResponse(
            id=cart.id,
            items=[CartItemResponse.from_entity(cart_item) for cart_item in cart.items],
            price=price,
        )
