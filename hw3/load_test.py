"""
Нагрузочный тест для shop_api.
Имитирует N «пользователей» и M запросов каждого.
"""
import asyncio
import random
import time
from typing import Any

import httpx

BASE_URL = "http://localhost:8000"
CONCURRENT_USERS = 50      # сколько одновременных «пользователей»
REQUESTS_PER_USER = 20     # сколько запросов каждый сделает
ITEM_NAMES = [
    "Молоко", "Хлеб", "Сыр", "Кефир", "Масло",
    "Йогурт", "Яйца", "Курица", "Рыба", "Мясо",
    "Чай", "Кофе", "Сахар", "Соль", "Специи",
]


async def make_item(client: httpx.AsyncClient, name: str) -> int | None:
    """POST /item — создаёт товар, возвращает id."""
    try:
        r = await client.post(
            f"{BASE_URL}/item",
            json={"name": name, "price": round(random.uniform(10, 500), 2)},
        )
        if r.status_code == 201:
            return r.json()["id"]
    except Exception:
        pass
    return None


async def user_session(user_id: int, stats: dict[str, Any]) -> None:
    """Один «пользователь»: создаёт товары, корзины, добавляет в корзину."""
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        item_ids: list[int] = []
        cart_id: int | None = None

        for _ in range(REQUESTS_PER_USER):
            action = random.choice([
                "create_item", "create_item", "get_items",
                "create_cart", "add_to_cart", "get_cart",
                "error_404", "error_422",
            ])
            try:
                if action == "create_item":
                    name = f"{random.choice(ITEM_NAMES)}-{user_id}-{random.randint(1, 9999)}"
                    item_id = await make_item(client, name)
                    if item_id:
                        item_ids.append(item_id)
                        stats["201"] += 1

                elif action == "get_items":
                    r = await client.get(f"{BASE_URL}/item")
                    stats[str(r.status_code)] += 1

                elif action == "create_cart":
                    r = await client.post(f"{BASE_URL}/cart")
                    if r.status_code == 201:
                        cart_id = r.json()["id"]
                    stats[str(r.status_code)] += 1

                elif action == "add_to_cart" and cart_id and item_ids:
                    item_id = random.choice(item_ids)
                    r = await client.post(f"{BASE_URL}/cart/{cart_id}/add/{item_id}")
                    stats[str(r.status_code)] += 1

                elif action == "get_cart" and cart_id:
                    r = await client.get(f"{BASE_URL}/cart/{cart_id}")
                    stats[str(r.status_code)] += 1

                elif action == "error_404":
                    r = await client.get(f"{BASE_URL}/item/999999")
                    stats[str(r.status_code)] += 1

                elif action == "error_422":
                    r = await client.get(f"{BASE_URL}/item", params={"limit": 0})
                    stats[str(r.status_code)] += 1

            except Exception as e:
                stats["errors"] += 1

        # финальный GET корзины, чтобы был 200
        if cart_id:
            await client.get(f"{BASE_URL}/cart/{cart_id}")


async def main() -> None:
    print(f"Запускаю {CONCURRENT_USERS} пользователей × {REQUESTS_PER_USER} запросов...")
    stats: dict[str, Any] = {"201": 0, "200": 0, "404": 0, "422": 0, "errors": 0}
    start = time.time()

    tasks = [user_session(i, stats) for i in range(CONCURRENT_USERS)]
    await asyncio.gather(*tasks)

    duration = time.time() - start
    total = sum(v for k, v in stats.items() if isinstance(v, int))
    print(f"\nГотово за {duration:.1f} сек")
    print(f"Всего запросов: {total}")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
