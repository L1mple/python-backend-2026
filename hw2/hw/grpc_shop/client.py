import grpc

from hw2.hw.grpc_shop import shop_pb2, shop_pb2_grpc


if __name__ == "__main__":
    with grpc.insecure_channel("localhost:50051") as channel:
        client = shop_pb2_grpc.ShopStub(channel)

        item = client.CreateItem(
            shop_pb2.CreateItemRequest(name="Молоко", price=159.99)
        )
        print("Создан товар:", item)

        cart = client.CreateCart(shop_pb2.Empty())
        print("Создана корзина:", cart)

        result = client.AddItemToCart(
            shop_pb2.AddItemRequest(cart_id=cart.id, item_id=item.id)
        )
        print("Товар добавлен в корзину:", result)
