"""Non-repeatable read: T1 дважды читает одну строку, а между чтениями T2 её меняет и коммитит."""
import asyncio

from sqlalchemy import update

from shop_api.storage.tables import ItemRecord
from transactions.common import (
    cleanup, get_price, header, reset_demo_items, t1, t2, transaction, verdict,
)


async def demo(isolation_level: str) -> None:
    header(f'Non-repeatable read @ {isolation_level}')
    [item_id] = await reset_demo_items(('bread', 50.0))

    async with transaction(isolation_level) as conn1, transaction(isolation_level) as conn2:
        first = await get_price(conn1, item_id)
        t1(f'SELECT price -> {first}')

        await conn2.execute(update(ItemRecord).where(ItemRecord.id == item_id).values(price=75.0))
        await conn2.commit()
        t2('UPDATE price = 75; COMMIT')

        second = await get_price(conn1, item_id)
        t1(f'SELECT price -> {second}')
        await conn1.commit()

    verdict('non-repeatable read', first != second)


async def main() -> None:
    try:
        await demo('READ COMMITTED')
        await demo('REPEATABLE READ')
    finally:
        await cleanup()


if __name__ == '__main__':
    asyncio.run(main())
