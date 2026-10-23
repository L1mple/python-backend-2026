from sqlalchemy import select, update

from shop_api.store.models import Item

from .common import Isolation, cleanup, new_item, run, tag, tx

OLD = 100.0
NEW = 777.0


async def price(session, item_id):
    return await session.scalar(select(Item.price).where(Item.id == item_id))


async def demo(level):
    print(f"--- {level.lower()}")
    prefix = tag("non-repeatable-read")
    item_id = await new_item(prefix, OLD)
    try:
        async with tx(level) as reader:
            first = await price(reader, item_id)
            print(f"first read: {first}")

            async with tx(Isolation.READ_COMMITTED) as writer:
                await writer.execute(
                    update(Item).where(Item.id == item_id).values(price=NEW)
                )
                await writer.commit()
            print(f"writer committed {NEW}")

            second = await price(reader, item_id)
            print(f"second read: {second}")

        return first, second
    finally:
        await cleanup(prefix)


async def main():
    first, second = await demo(Isolation.READ_COMMITTED)
    assert (first, second) == (OLD, NEW), "expected a non-repeatable read"

    print()

    first, second = await demo(Isolation.REPEATABLE_READ)
    assert (first, second) == (OLD, OLD), "snapshot should have held"


if __name__ == "__main__":
    run(main)
