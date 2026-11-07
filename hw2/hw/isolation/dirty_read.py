from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from isolation.common import (
    READ_COMMITTED,
    READ_UNCOMMITTED,
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
        await t1.read(price_of(1), "цена товара 1")
        await t2.write(
            update(items).where(items.c.id == 1).values(price=200.0),
            "UPDATE цена товара 1 = 200, без COMMIT",
        )
        seen = await t1.read(price_of(1), "цена товара 1")
        await t2.rollback()
        await t1.commit()
    finally:
        await t1.close()
        await t2.close()

    # T1 увидел 200, а эту цену потом откатили: она никогда не существовала
    return seen == 200.0


DEMO = Demo(
    title="Dirty read",
    description="T1 читает цену, пока T2 изменил её и ещё не закоммитил, а потом откатил.",
    scenario=scenario,
    cases=[
        Case(
            READ_UNCOMMITTED,
            anomaly_expected=False,
            note=(
                "в PostgreSQL READ UNCOMMITTED работает как READ COMMITTED, "
                "незакоммиченные данные не видны никогда (документация, раздел 13.2)"
            ),
        ),
        Case(READ_COMMITTED, anomaly_expected=False, note="видны только закоммиченные данные"),
    ],
)

if __name__ == "__main__":
    main([DEMO])
