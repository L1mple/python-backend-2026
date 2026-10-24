"""Serialization anomaly (write skew).

Бизнес-правило: в продаже должен остаться хотя бы один демо-товар.
T1 и T2 одновременно проверяют правило (видят 2 товара) и снимают с продажи РАЗНЫЕ товары.
Строки не пересекаются, поэтому REPEATABLE READ конфликт не замечает и в итоге в продаже 0 товаров:
ни один последовательный порядок выполнения T1 и T2 к такому результату не привёл бы.
SERIALIZABLE (SSI) отслеживает зависимости чтение-запись и откатывает одну из транзакций.
"""
import asyncio

from sqlalchemy import update
from sqlalchemy.exc import DBAPIError

from shop_api.storage.tables import ItemRecord
from transactions.common import (
    cleanup, count_demo_items, engine, header, is_serialization_failure,
    reset_demo_items, t1, t2, transaction, verdict,
)


async def demo(isolation_level: str) -> None:
    header(f'Write skew @ {isolation_level}')
    first_id, second_id = await reset_demo_items(('tea', 20.0), ('coffee', 30.0))

    async with transaction(isolation_level) as conn1, transaction(isolation_level) as conn2:
        on_sale = await count_demo_items(conn1, deleted=False)
        t1(f'SELECT count(*) WHERE NOT deleted -> {on_sale}')
        on_sale = await count_demo_items(conn2, deleted=False)
        t2(f'SELECT count(*) WHERE NOT deleted -> {on_sale}')

        await conn1.execute(update(ItemRecord).where(ItemRecord.id == first_id).values(deleted=True))
        t1('UPDATE tea SET deleted = true')
        await conn2.execute(update(ItemRecord).where(ItemRecord.id == second_id).values(deleted=True))
        t2('UPDATE coffee SET deleted = true')

        await conn1.commit()
        t1('COMMIT -> ok')
        try:
            await conn2.commit()
            t2('COMMIT -> ok')
        except DBAPIError as exc:
            if not is_serialization_failure(exc):
                raise
            t2('COMMIT -> ERROR 40001 could not serialize access, ROLLBACK')

    async with engine.connect() as conn:
        left = await count_demo_items(conn, deleted=False)
    print(f'  Итог: в продаже осталось {left} товар(ов)')
    verdict('serialization anomaly', left == 0)


async def main() -> None:
    try:
        await demo('REPEATABLE READ')
        await demo('SERIALIZABLE')
    finally:
        await cleanup()


if __name__ == '__main__':
    asyncio.run(main())
