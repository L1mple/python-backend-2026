from prometheus_client import Counter, Gauge

# Бизнес-метрики магазина. HTTP-метрики (запросы, коды, задержки)
# собирает prometheus-fastapi-instrumentator в main.py

ITEMS_CREATED = Counter("shop_items_created", "Сколько товаров создано")
ITEMS_DELETED = Counter("shop_items_deleted", "Сколько товаров удалено")
CARTS_CREATED = Counter("shop_carts_created", "Сколько корзин создано")
CART_ITEMS_ADDED = Counter("shop_cart_items_added", "Сколько раз товар добавили в корзину")
CHAT_CONNECTIONS = Gauge("shop_chat_connections", "Сколько клиентов сейчас в чатах")
