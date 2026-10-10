from threading import Lock

from shop_api.models import (
    Cart,
    CartItem,
    Item,
)


class InMemoryShopStorage:
    def __init__(self) -> None:
        self.items_by_id: list[Item] = []
        self.item_quantities_by_cart_id: list[dict[int, int]] = []
        self.write_lock = Lock()

    def create_item(
        self,
        name: str,
        price: float,
    ) -> Item:
        with self.write_lock:
            new_item = Item(
                id=len(self.items_by_id),
                name=name,
                price=price,
            )
            self.items_by_id.append(new_item)
        return new_item

    def get_item_by_id(
        self,
        item_id: int,
    ) -> Item | None:
        if 0 <= item_id < len(self.items_by_id):
            return self.items_by_id[item_id]
        return None

    def get_all_items_including_deleted(self) -> list[Item]:
        return list(self.items_by_id)

    def create_empty_cart(self) -> int:
        with self.write_lock:
            self.item_quantities_by_cart_id.append({})
            return len(self.item_quantities_by_cart_id) - 1

    def cart_exists(
        self,
        cart_id: int,
    ) -> bool:
        return 0 <= cart_id < len(self.item_quantities_by_cart_id)

    def increase_item_quantity_in_cart_by_one(
        self,
        cart_id: int,
        item_id: int,
    ) -> None:
        with self.write_lock:
            item_quantities_in_cart = self.item_quantities_by_cart_id[cart_id]
            current_quantity_of_item = item_quantities_in_cart.get(
                item_id,
                0,
            )
            item_quantities_in_cart[item_id] = current_quantity_of_item + 1

    def build_cart_with_current_prices(
        self,
        cart_id: int,
    ) -> Cart:
        items_in_cart = [
            CartItem(
                id=item_id,
                name=self.items_by_id[item_id].name,
                quantity=quantity,
                available=not self.items_by_id[item_id].deleted,
            )
            for item_id, quantity in self.item_quantities_by_cart_id[cart_id].items()
        ]
        total_price_of_available_items = sum(
            self.items_by_id[item_in_cart.id].price * item_in_cart.quantity
            for item_in_cart in items_in_cart
            if item_in_cart.available
        )
        return Cart(
            id=cart_id,
            items=items_in_cart,
            price=total_price_of_available_items,
        )

    def build_all_carts_with_current_prices(self) -> list[Cart]:
        return [
            self.build_cart_with_current_prices(cart_id=cart_id)
            for cart_id in range(len(self.item_quantities_by_cart_id))
        ]
