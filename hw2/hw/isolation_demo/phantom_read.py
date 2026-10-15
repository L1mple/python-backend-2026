from sqlalchemy import func, insert, select
from sqlalchemy.exc import DBAPIError

from shop_api.store.models import Item

from .common import Isolation, cleanup, new_item, run, tag, tx


async def count(session, prefix):
    return await session.scalar(
        select(func.count()).select_from(Item).where(Item.name.like(f"{prefix}%"))
    )


async def add(session, name):
    await session.execute(insert(Item).values(name=name, price=1.0))


async def recount(level):
    print(f"--- {level.lower()}")
    prefix = tag("phantom-read")
    await new_item(f"{prefix}-a", 10.0)

    try:
        async with tx(level) as reader:
            first = await count(reader, prefix)
            print(f"rows before: {first}")

            async with tx(Isolation.READ_COMMITTED) as writer:
                await add(writer, f"{prefix}-b")
                await writer.commit()
            print("another transaction inserted a matching row and committed")

            second = await count(reader, prefix)
            print(f"rows after: {second}")

        assert first == second, f"{level}: {first} -> {second}"
    finally:
        await cleanup(prefix)


async def concurrent_inserts(level):
    print(f"--- {level.lower()}, concurrent inserts")
    prefix = tag("phantom-concurrent")
    failed = ""

    try:
        async with tx(level) as a, tx(level) as b:
            print(f"A counted: {await count(a, prefix)}")
            print(f"B counted: {await count(b, prefix)}")

            await add(a, f"{prefix}-a")
            await add(b, f"{prefix}-b")
            print("both inserted their row")

            await a.commit()
            print("A committed")

            try:
                await b.commit()
                print("B committed")
            except DBAPIError as error:
                failed = error.orig.sqlstate
                print(f"B rejected, sqlstate {failed}")

        async with tx(Isolation.READ_COMMITTED) as check:
            total = await count(check, prefix)
        print(f"rows left: {total}")

        return failed, total
    finally:
        await cleanup(prefix)


async def main():
    await recount(Isolation.REPEATABLE_READ)
    print()
    await recount(Isolation.SERIALIZABLE)
    print()

    failed, total = await concurrent_inserts(Isolation.REPEATABLE_READ)
    assert (failed, total) == ("", 2), "both should have committed"

    print()

    failed, total = await concurrent_inserts(Isolation.SERIALIZABLE)
    assert (failed, total) == ("40001", 1), f"expected 40001, got {failed!r}"


if __name__ == "__main__":
    run(main)
