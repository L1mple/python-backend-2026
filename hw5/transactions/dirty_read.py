"""Dirty read: T2 читает изменения T1, которые ещё не закоммичены (и будут откачены).

В Postgres READ UNCOMMITTED работает как READ COMMITTED (MVCC никогда не отдаёт
чужие незакоммиченные версии строк), поэтому dirty read здесь не воспроизвести
ни на одном уровне. Скрипт это и показывает.
"""
import asyncio

from sqlalchemy import update

from shop_api.storage.tables import ItemRecord
from transactions.common import (
    cleanup, get_price, header, reset_demo_items, t1, t2, transaction, verdict,
)


async def demo(isolation_level: str) -> None:
    header(f'Dirty read @ {isolation_level}')
    [item_id] = await reset_demo_items(('milk', 100.0))

    async with transaction(isolation_level) as conn1, transaction(isolation_level) as conn2:
        await conn1.execute(update(ItemRecord).where(ItemRecord.id == item_id).values(price=999.0))
        t1('UPDATE price = 999 (без COMMIT)')

        seen = await get_price(conn2, item_id)
        t2(f'SELECT price -> {seen}')

        await conn1.rollback()
        t1('ROLLBACK')
        await conn2.commit()

    verdict('dirty read', seen == 999.0)


async def main() -> None:
    try:
        await demo('READ UNCOMMITTED')
        print('  Postgres: READ UNCOMMITTED == READ COMMITTED, грязное чтение невозможно.')
        await demo('READ COMMITTED')
    finally:
        await cleanup()


if __name__ == '__main__':
    asyncio.run(main())
