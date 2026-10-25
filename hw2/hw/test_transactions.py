import os

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, func, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from shop_api.models import Item

PG_URL = os.getenv("ISOLATION_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not PG_URL,
    reason="Set ISOLATION_TEST_DATABASE_URL to run isolation tests against Postgres",
)


@pytest_asyncio.fixture(scope="session")
async def pg_engine():
    engine = create_async_engine(PG_URL, echo=False, future=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session_factory(pg_engine):
    return sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def seeded_item(pg_session_factory):
    """
    Вставляет один Item в реальную таблицу (схема из миграций),
    отдаёт его id в тест и удаляет после теста.
    """
    async with pg_session_factory() as s:
        item = Item(name="iso-test-item", price=100.0, deleted=False)
        s.add(item)
        await s.commit()
        await s.refresh(item)
        item_id = item.id

    yield item_id

    async with pg_session_factory() as s:
        await s.execute(delete(Item).where(Item.id == item_id))
        await s.commit()


async def _set_isolation(session: AsyncSession, level: str) -> None:
    """Устанавливает уровень изоляции для текущей транзакции."""
    await session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {level}"))


@pytest.mark.asyncio
async def test_no_dirty_read_at_read_uncommitted(pg_session_factory, seeded_item):
    """
    DIRTY READ
    Postgres не поддерживает READ UNCOMMITTED — уровень повышается
    до READ COMMITTED, поэтому грязного чтения нет даже "на слабом".
    """
    async with pg_session_factory() as s1, pg_session_factory() as s2:
        await s1.execute(text("BEGIN"))
        await _set_isolation(s1, "READ UNCOMMITTED")

        await s1.execute(
            text("UPDATE items SET price = 999 WHERE id = :id"),
            {"id": seeded_item},
        )

        await s2.execute(text("BEGIN"))
        await _set_isolation(s2, "READ UNCOMMITTED")
        value = (
            await s2.execute(
                select(Item.price).where(Item.id == seeded_item)
            )
        ).scalar()

        assert value == 100.0, (
            "Postgres не должен показывать незакоммиченные данные "
            "даже на READ UNCOMMITTED"
        )

        await s1.rollback()
        await s2.rollback()


@pytest.mark.asyncio
async def test_non_repeatable_read_at_read_committed(pg_session_factory, seeded_item):
    """Аномалия ВОСПРОИЗВОДИТСЯ на READ COMMITTED."""
    async with pg_session_factory() as s1, pg_session_factory() as s2:
        await s1.execute(text("BEGIN"))
        await _set_isolation(s1, "READ COMMITTED")

        first = (
            await s1.execute(select(Item.price).where(Item.id == seeded_item))
        ).scalar()

        await s2.execute(text("BEGIN"))
        await s2.execute(
            text("UPDATE items SET price = 999 WHERE id = :id"),
            {"id": seeded_item},
        )
        await s2.commit()

        second = (
            await s1.execute(select(Item.price).where(Item.id == seeded_item))
        ).scalar()

        assert first == 100.0
        assert second == 999.0, (
            "На READ COMMITTED значение должно измениться между двумя чтениями"
        )

        await s1.rollback()


@pytest.mark.asyncio
async def test_no_non_repeatable_read_at_repeatable_read(
    pg_session_factory, seeded_item
):
    """Аномалия РЕШЕНА на REPEATABLE READ."""
    async with pg_session_factory() as s1, pg_session_factory() as s2:
        await s1.execute(text("BEGIN"))
        await _set_isolation(s1, "REPEATABLE READ")

        first = (
            await s1.execute(select(Item.price).where(Item.id == seeded_item))
        ).scalar()

        await s2.execute(text("BEGIN"))
        await s2.execute(
            text("UPDATE items SET price = 999 WHERE id = :id"),
            {"id": seeded_item},
        )
        await s2.commit()

        second = (
            await s1.execute(select(Item.price).where(Item.id == seeded_item))
        ).scalar()

        assert first == 100.0
        assert second == 100.0, (
            "На REPEATABLE READ значение не должно меняться между чтениями"
        )

        await s1.rollback()


@pytest.mark.asyncio
async def test_phantom_read_at_read_committed(pg_session_factory, seeded_item):
    """Аномалия ВОСПРОИЗВОДИТСЯ на READ COMMITTED."""
    async with pg_session_factory() as s1, pg_session_factory() as s2:
        await s1.execute(text("BEGIN"))
        await _set_isolation(s1, "READ COMMITTED")

        first = (
            await s1.execute(select(func.count()).select_from(Item))
        ).scalar()

        await s2.execute(text("BEGIN"))
        await s2.execute(
            text(
                "INSERT INTO items (name, price, deleted) "
                "VALUES ('phantom-item', 50.0, false)"
            )
        )
        await s2.commit()

        second = (
            await s1.execute(select(func.count()).select_from(Item))
        ).scalar()

        assert second == first + 1, (
            "На READ COMMITTED должна появиться фантомная строка"
        )

        await s1.rollback()

        await s2.execute(
            text("DELETE FROM items WHERE name = 'phantom-item'")
        )
        await s2.commit()


@pytest.mark.asyncio
async def test_no_phantom_read_at_repeatable_read(pg_session_factory, seeded_item):
    """Аномалия РЕШЕНА на REPEATABLE READ (Postgres сильнее стандарта)."""
    async with pg_session_factory() as s1, pg_session_factory() as s2:
        await s1.execute(text("BEGIN"))
        await _set_isolation(s1, "REPEATABLE READ")

        first = (
            await s1.execute(select(func.count()).select_from(Item))
        ).scalar()

        await s2.execute(text("BEGIN"))
        await s2.execute(
            text(
                "INSERT INTO items (name, price, deleted) "
                "VALUES ('phantom-item-2', 50.0, false)"
            )
        )
        await s2.commit()

        second = (
            await s1.execute(select(func.count()).select_from(Item))
        ).scalar()

        assert first == second, (
            "На REPEATABLE READ фантомных строк быть не должно"
        )

        await s1.rollback()

        await s2.execute(
            text("DELETE FROM items WHERE name = 'phantom-item-2'")
        )
        await s2.commit()