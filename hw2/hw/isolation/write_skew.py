from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from isolation.common import (
    REPEATABLE_READ,
    SERIALIZABLE,
    Case,
    Demo,
    Tx,
    active_count,
    is_serialization_failure,
    items,
    main,
    read_committed_state,
    reset_items,
)


async def scenario(engine: AsyncEngine, level: str) -> bool:
    await reset_items(engine, [("Молоко", 100.0), ("Хлеб", 50.0)])

    t1 = await Tx.start(engine, "T1", level)
    t2 = await Tx.start(engine, "T2", level)
    try:
        # Правило магазина: в продаже должен остаться хотя бы один товар.
        # Обе транзакции проверяют его, видят два товара и решают, что снять один можно
        await t1.read(active_count(), "товаров в продаже")
        await t2.read(active_count(), "товаров в продаже")
        await t1.write(
            update(items).where(items.c.id == 1).values(deleted=True),
            "UPDATE снять с продажи товар 1",
        )
        await t2.write(
            update(items).where(items.c.id == 2).values(deleted=True),
            "UPDATE снять с продажи товар 2",
        )
        await t1.commit()
        try:
            await t2.commit()
        except DBAPIError as error:
            if not is_serialization_failure(error):
                raise
            t2.log("ошибка сериализации (SQLSTATE 40001), транзакция откатилась")
            await t2.rollback()
    finally:
        await t1.close()
        await t2.close()

    left = await read_committed_state(engine, active_count())
    print(f"  После обеих транзакций в продаже товаров: {left}")
    # Каждая транзакция по отдельности правило соблюдала, а вместе нарушили
    return left == 0


DEMO = Demo(
    title="Serialization anomaly (write skew)",
    description=(
        "Правило: в продаже остаётся хотя бы один товар. T1 и T2 одновременно проверяют его "
        "и снимают с продажи разные товары."
    ),
    scenario=scenario,
    cases=[
        Case(
            REPEATABLE_READ,
            anomaly_expected=True,
            note=(
                "транзакции меняют разные строки, конфликта записи нет, и каждая "
                "читает свой снимок, где второй товар ещё в продаже"
            ),
        ),
        Case(
            SERIALIZABLE,
            anomaly_expected=False,
            note=(
                "PostgreSQL замечает, что результат не совпадает ни с одним "
                "последовательным порядком, и откатывает вторую транзакцию"
            ),
        ),
    ],
)

if __name__ == "__main__":
    main([DEMO])
