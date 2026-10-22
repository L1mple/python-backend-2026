from __future__ import annotations

from pydantic import BaseModel, ConfigDict, NonNegativeFloat

from shop_api.store import CartRecord, ItemRecord, get_item



class ItemRequest(BaseModel):
    name: str
    price: NonNegativeFloat


class PatchItemRequest(BaseModel):
    name: str | None = None
    price: NonNegativeFloat | None = None

    model_config = ConfigDict(extra="forbid")


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @staticmethod
    def from_record(item: ItemRecord) -> ItemResponse:
        return ItemResponse(
            id=item.id, name=item.name, price=item.price, deleted=item.deleted
        )



class CartIdResponse(BaseModel):
    id: int


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
    def from_record(cart: CartRecord) -> CartResponse:
        items: list[CartItemResponse] = []
        price = 0.0

        for item_id, quantity in cart.items.items():
            item = get_item(item_id)
            if item is None:  # товары не удаляются физически, но на всякий случай
                continue

            available = not item.deleted
            items.append(
                CartItemResponse(
                    id=item.id,
                    name=item.name,
                    quantity=quantity,
                    available=available,
                )
            )
            # цена считается по актуальным ценам; удалённые товары не оплачиваются
            if available:
                price += item.price * quantity

        return CartResponse(id=cart.id, items=items, price=price)

    @property
    def quantity(self) -> int:
        return sum(item.quantity for item in self.items)
