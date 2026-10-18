"""Phantom read"""
from isolation.common import cleanup, connect, count_items, create_item, insert_item, real_level

NAME = "демо: фантом"


def demo(level: str) -> None:
    cleanup()
    create_item(NAME, 100)
    create_item(NAME, 100)

    with connect(level) as a, connect("READ COMMITTED") as b:
        print(f"\n=== A на уровне {level} (Postgres: {real_level(a)})")
        first = count_items(a, NAME)
        print(f"A: считает товары «{NAME}» → {first}")
        insert_item(b, NAME, 100)
        b.commit()
        print("B: добавила ещё один такой товар и закоммитила")
        second = count_items(a, NAME)
        print(f"A: в той же транзакции считает снова → {second}")
        a.commit()

    if first != second:
        print("❗ phantom read: в наборе строк появилась новая — «фантом»")
    else:
        print("✅ phantom read нет: набор строк не изменился")
    cleanup()


if __name__ == "__main__":
    demo("READ COMMITTED")
    demo("REPEATABLE READ")
    demo("SERIALIZABLE")
