"""Dirty read: читает изменения, которые ещё не закоммитили."""
from isolation.common import cleanup, connect, create_item, get_price, real_level, set_price


def demo(level: str) -> None:
    cleanup()
    item_id = create_item("демо: чайник", 1500)

    with connect(level) as a, connect("READ COMMITTED") as b:
        print(f"\n=== A на уровне {level} (Postgres: {real_level(a)})")
        set_price(b, item_id, 1)
        print("B: поставила цену 1 и НЕ закоммитила")
        price = get_price(a, item_id)
        print(f"A: читает цену → {price}")
        b.rollback()
        print("B: откатилась — цены 1 в базе никогда не было")
        a.commit()

    if price == 1:
        print("❗ dirty read: A увидела незакоммиченные данные")
    else:
        print("✅ dirty read нет: A видит только закоммиченные данные")
    cleanup()


if __name__ == "__main__":
    demo("READ UNCOMMITTED")
    demo("READ COMMITTED")
