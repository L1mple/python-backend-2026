from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from isolation.common import (
    READ_COMMITTED,
    REPEATABLE_READ,
    Case,
    Demo,
    Tx,
    items,
    main,
    price_of,
    reset_items,
)


async def scenario(engine: AsyncEngine, level: str) -> bool:
    await reset_items(engine, [("Молоко", 100.0)])

    t1 = await Tx.start(engine, "T1", level)
    t2 = await Tx.start(engine, "T2", level)
    try:
        first = await t1.read(price_of(1), "цена товара 1")
        await t2.write(
            update(items).where(items.c.id == 1).values(price=150.0),
            "UPDATE цена товара 1 = 150",
        )
        await t2.commit()
        second = await t1.read(price_of(1), "цена товара 1 ещё раз")
        await t1.commit()
    finally:
        await t1.close()
        await t2.close()

    # Внутри одной транзакции одна и та же строка прочиталась по-разному
    return first != second


DEMO = Demo(
    title="Non-repeatable read",
    description="T1 дважды читает цену товара, а между чтениями T2 меняет её и коммитит.",
    scenario=scenario,
    cases=[
        Case(
            READ_COMMITTED,
            anomaly_expected=True,
            note="каждый запрос видит свежий снимок: всё, что закоммичено до его начала",
        ),
        Case(
            REPEATABLE_READ,
            anomaly_expected=False,
            note="вся транзакция читает один снимок, взятый на её первом запросе",
        ),
    ],
)

if __name__ == "__main__":
    main([DEMO])
