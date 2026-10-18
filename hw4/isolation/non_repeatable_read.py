"""Non-repeatable read"""
from isolation.common import cleanup, connect, create_item, get_price, real_level, set_price


def demo(level: str) -> None:
    cleanup()
    item_id = create_item("демо: кружка", 300)

    with connect(level) as a, connect("READ COMMITTED") as b:
        print(f"\n=== A на уровне {level} (Postgres: {real_level(a)})")
        first = get_price(a, item_id)
        print(f"A: читает цену → {first}")
        set_price(b, item_id, 350)
        b.commit()
        print("B: поменяла цену на 350 и закоммитила")
        second = get_price(a, item_id)
        print(f"A: в той же транзакции читает снова → {second}")
        a.commit()

    if first != second:
        print("❗ non-repeatable read: одна строка в одной транзакции дала разные значения")
    else:
        print("✅ non-repeatable read нет: повторное чтение дало то же значение")
    cleanup()


if __name__ == "__main__":
    demo("READ COMMITTED")
    demo("REPEATABLE READ")
