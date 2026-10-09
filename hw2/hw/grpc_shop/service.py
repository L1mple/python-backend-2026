from concurrent import futures

import grpc

from hw2.hw.grpc_shop import shop_pb2, shop_pb2_grpc
from hw2.hw.shop_api import store
from hw2.hw.shop_api.store.models import ItemInfo, PatchItemInfo


def item_response(entity):
    return shop_pb2.Item(
        id=entity.id,
        name=entity.info.name,
        price=entity.info.price,
        deleted=entity.info.deleted,
    )


def cart_response(entity):
    return shop_pb2.Cart(
        id=entity.id,
        items=[
            shop_pb2.CartItem(
                id=item.id,
                name=item.name,
                quantity=item.quantity,
                available=item.available,
            )
            for item in entity.items
        ],
        price=sum(item.price * item.quantity for item in entity.items),
    )


def optional_value(message, field):
    if message.HasField(field):
        return getattr(message, field)
    return None


class ShopService(shop_pb2_grpc.ShopServicer):
    def CreateItem(self, request, context):
        if not request.name or request.price <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Некорректные данные товара")
        item = store.add_item(ItemInfo(request.name, request.price))
        return item_response(item)

    def GetItem(self, request, context):
        item = store.get_item(request.id)
        if item is None or item.info.deleted:
            context.abort(grpc.StatusCode.NOT_FOUND, "Товар не найден")
        return item_response(item)

    def GetItems(self, request, context):
        limit = request.limit or 10
        items = store.get_items(
            request.offset,
            limit,
            optional_value(request, "min_price"),
            optional_value(request, "max_price"),
            request.show_deleted,
        )
        return shop_pb2.ItemList(items=[item_response(item) for item in items])

    def ReplaceItem(self, request, context):
        if not request.name or request.price <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Некорректные данные товара")
        item = store.update_item(
            request.id,
            ItemInfo(request.name, request.price),
        )
        if item is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "Товар не найден")
        return item_response(item)

    def PatchItem(self, request, context):
        name = optional_value(request, "name")
        price = optional_value(request, "price")
        if name == "" or (price is not None and price <= 0):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Некорректные данные товара")
        item = store.patch_item(request.id, PatchItemInfo(name, price))
        if item is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "Товар не найден")
        return item_response(item)

    def DeleteItem(self, request, context):
        item = store.delete_item(request.id)
        if item is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "Товар не найден")
        return item_response(item)

    def CreateCart(self, request, context):
        cart = store.add_cart()
        return shop_pb2.IdResponse(id=cart.id)

    def GetCart(self, request, context):
        cart = store.get_cart(request.id)
        if cart is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "Корзина не найдена")
        return cart_response(cart)

    def GetCarts(self, request, context):
        limit = request.limit or 10
        carts = store.get_carts(
            request.offset,
            limit,
            optional_value(request, "min_price"),
            optional_value(request, "max_price"),
            optional_value(request, "min_quantity"),
            optional_value(request, "max_quantity"),
        )
        return shop_pb2.CartList(carts=[cart_response(cart) for cart in carts])

    def AddItemToCart(self, request, context):
        cart = store.add_item_to_cart(request.cart_id, request.item_id)
        if cart is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "Корзина или товар не найдены")
        return cart_response(cart)


if __name__ == "__main__":
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    shop_pb2_grpc.add_ShopServicer_to_server(ShopService(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC-сервер магазина запущен на порту 50051")
    server.wait_for_termination()
