from sqlalchemy import select, text, update

from shop_api.store.models import Item

from .common import Isolation, cleanup, new_item, run, tag, tx


START = 100.0
DIRTY = 999.0


async def read_price(session, item_id):
    return await session.scalar(select(Item.price).where(Item.id == item_id))


async def demo(level):
    print(f"--- {level.lower()}")
    prefix = tag("dirty-read")
    item_id = await new_item(prefix, START)

    try:
        async with tx(Isolation.READ_COMMITTED) as writer, tx(level) as reader:
            print(f"price before: {await read_price(reader, item_id)}")
            print(
                "SHOW transaction_isolation:",
                await reader.scalar(text("SHOW transaction_isolation")),
            )

            await writer.execute(
                update(Item).where(Item.id == item_id).values(price=DIRTY)
            )
            print(f"writer set {DIRTY}, no commit")

            seen = await read_price(reader, item_id)
            print(f"reader sees: {seen}")

            await writer.rollback()
            print(f"after writer rollback: {await read_price(reader, item_id)}")

        assert seen == START, f"dirty read on {level}: {seen}"
    finally:
        await cleanup(prefix)


async def main():
    await demo(Isolation.READ_UNCOMMITTED)
    print()
    await demo(Isolation.READ_COMMITTED)


if __name__ == "__main__":
    run(main)
