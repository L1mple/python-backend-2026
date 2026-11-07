from sqlalchemy.ext.asyncio import AsyncEngine

from isolation.common import (
    READ_COMMITTED,
    REPEATABLE_READ,
    SERIALIZABLE,
    Case,
    Demo,
    Tx,
    items,
    main,
    names_cheaper_than,
    reset_items,
)


async def scenario(engine: AsyncEngine, level: str) -> bool:
    await reset_items(engine, [("Молоко", 100.0), ("Хлеб", 50.0)])

    t1 = await Tx.start(engine, "T1", level)
    t2 = await Tx.start(engine, "T2", level)
    try:
        first = await t1.read(names_cheaper_than(200.0), "товары дешевле 200")
        await t2.write(items.insert().values(name="Сыр", price=150.0), "INSERT товар «Сыр» за 150")
        await t2.commit()
        second = await t1.read(names_cheaper_than(200.0), "товары дешевле 200 ещё раз")
        await t1.commit()
    finally:
        await t1.close()
        await t2.close()

    # Тот же запрос с тем же условием вернул другой набор строк
    return first != second


DEMO = Demo(
    title="Phantom read",
    description="T1 дважды выбирает товары дешевле 200, а между выборками T2 добавляет новый.",
    scenario=scenario,
    cases=[
        Case(
            READ_COMMITTED,
            anomaly_expected=True,
            note="новая строка закоммичена до второго запроса, и он её видит",
        ),
        Case(
            REPEATABLE_READ,
            anomaly_expected=False,
            note=(
                "в PostgreSQL REPEATABLE READ читает снимок данных, и новых строк в нём нет. "
                "Стандарт SQL фантомы здесь допускает, PostgreSQL нет "
                "(таблица 13.1 документации: «Allowed, but not in PG»)"
            ),
        ),
        Case(SERIALIZABLE, anomaly_expected=False, note="тот же снимок плюс проверка конфликтов"),
    ],
)

if __name__ == "__main__":
    main([DEMO])
