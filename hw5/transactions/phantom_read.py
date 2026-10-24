"""Phantom read: T1 дважды выполняет запрос по условию, а T2 между ними вставляет подходящую строку.

По стандарту SQL фантомы допустимы на REPEATABLE READ, но в Postgres REPEATABLE READ —
это snapshot isolation: вся транзакция видит один снимок, поэтому фантомов нет уже на нём.
Для наглядности показываем фантом на READ COMMITTED и его отсутствие на REPEATABLE READ
и SERIALIZABLE.
"""
import asyncio

from sqlalchemy import insert

from shop_api.storage.tables import ItemRecord
from transactions.common import (
    DEMO_PREFIX, cleanup, count_demo_items, header, reset_demo_items, t1, t2, transaction, verdict,
)


async def demo(isolation_level: str) -> None:
    header(f'Phantom read @ {isolation_level}')
    await reset_demo_items(('caviar', 500.0), ('cheese', 300.0), ('water', 10.0))

    async with transaction(isolation_level) as conn1, transaction(isolation_level) as conn2:
        first = await count_demo_items(conn1, min_price=100)
        t1(f'SELECT count(*) WHERE price >= 100 -> {first}')

        await conn2.execute(insert(ItemRecord).values(name=f'{DEMO_PREFIX}: truffle', price=900.0))
        await conn2.commit()
        t2('INSERT truffle (price = 900); COMMIT')

        second = await count_demo_items(conn1, min_price=100)
        t1(f'SELECT count(*) WHERE price >= 100 -> {second}')
        await conn1.commit()

    verdict('phantom read', first != second)


async def main() -> None:
    try:
        await demo('READ COMMITTED')
        await demo('REPEATABLE READ')
        print('  Postgres: REPEATABLE READ строже стандарта (snapshot) — фантомов нет.')
        await demo('SERIALIZABLE')
    finally:
        await cleanup()


if __name__ == '__main__':
    asyncio.run(main())
