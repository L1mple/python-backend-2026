

from .models import Cart, Item



def int_item_id_generator():
    i = 0
    while True:
        yield i
        i += 1


item_id_generator = int_item_id_generator()




def int_cart_id_generator():
    i = 0
    while True:
        yield i
        i += 1


cart_id_generator = int_cart_id_generator()


carts: dict[int, Cart] = {}
items: dict[int, Item] = {}