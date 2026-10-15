from decimal import Decimal

from store.item.models import ItemEntity

from pydantic import BaseModel, Field, computed_field, ConfigDict


class CartItem(BaseModel):
    item: ItemEntity
    quantity: int = Field(default=1, ge=1)

    model_config = ConfigDict(extra="forbid")

    @computed_field
    @property
    def total_price(self) -> Decimal:
        return self.item.price * self.quantity


class Cart(BaseModel):
    id: int
    items: list[CartItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    def add_item(self, item: ItemEntity, quantity: int = 1) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than 0")

        for cart_item in self.items:
            if cart_item.item.id == item.id:
                cart_item.quantity += quantity
                return

        self.items.append(CartItem(item=item, quantity=quantity))

    @computed_field
    @property
    def price(self) -> Decimal:
        return sum((ci.total_price for ci in self.items), Decimal('0.00'))
