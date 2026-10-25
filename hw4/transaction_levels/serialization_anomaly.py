import asyncio

from psycopg import AsyncConnection, IsolationLevel
from psycopg.errors import SerializationFailure

from .common import DATABASE_URL, doctors_table, level_sql, log_sql, log_value


async def run_scenario(level: IsolationLevel) -> tuple[int, bool]:
    async with doctors_table() as table_name:
        async with await AsyncConnection.connect(DATABASE_URL) as t1:
            async with await AsyncConnection.connect(DATABASE_URL) as t2:
                t2_committed = False

                t1_begin = f"BEGIN ISOLATION LEVEL {level_sql(level)}"
                log_sql(1, level, t1_begin)
                await t1.execute(t1_begin)

                t2_begin = f"BEGIN ISOLATION LEVEL {level_sql(level)}"
                log_sql(2, level, t2_begin)
                await t2.execute(t2_begin)

                select_sql = f"SELECT count(*) FROM {table_name} WHERE on_call"
                log_sql(1, level, select_sql)
                cursor = await t1.execute(select_sql)
                row = await cursor.fetchone()
                t1_on_call = row[0]
                log_value(1, level, t1_on_call)

                log_sql(2, level, select_sql)
                cursor = await t2.execute(select_sql)
                row = await cursor.fetchone()
                t2_on_call = row[0]
                log_value(2, level, t2_on_call)

                update_t1 = f"UPDATE {table_name} SET on_call = false WHERE id = 1"
                log_sql(1, level, update_t1)
                await t1.execute(update_t1)

                update_t2 = f"UPDATE {table_name} SET on_call = false WHERE id = 2"
                log_sql(2, level, update_t2)
                await t2.execute(update_t2)

                log_sql(1, level, "COMMIT")
                await t1.execute("COMMIT")

                try:
                    log_sql(2, level, "COMMIT")
                    await t2.execute("COMMIT")
                    t2_committed = True
                except SerializationFailure:
                    log_sql(2, level, "COMMIT -> SERIALIZATION FAILURE (40001)")
                    await t2.execute("ROLLBACK")

                observer_level = IsolationLevel.READ_COMMITTED
                observer_begin = f"BEGIN ISOLATION LEVEL {level_sql(observer_level)}"
                log_sql(1, observer_level, observer_begin)
                await t1.execute(observer_begin)
                log_sql(1, observer_level, select_sql)
                cursor = await t1.execute(select_sql)
                row = await cursor.fetchone()
                final_on_call = row[0]
                log_value(1, observer_level, final_on_call)
                log_sql(1, observer_level, "ROLLBACK")
                await t1.execute("ROLLBACK")

    return final_on_call, t2_committed


async def main() -> None:
    for level in (
        IsolationLevel.REPEATABLE_READ,
        IsolationLevel.SERIALIZABLE,
    ):
        await run_scenario(level)


if __name__ == "__main__":
    asyncio.run(main())
