import asyncio

from psycopg import AsyncConnection, IsolationLevel

from .common import DATABASE_URL, doctors_table, level_sql, log_sql, log_value


async def run_scenario(level: IsolationLevel) -> tuple[int, int]:
    async with doctors_table() as table_name:
        async with await AsyncConnection.connect(DATABASE_URL) as t1:
            async with await AsyncConnection.connect(DATABASE_URL) as t2:
                t1_level = IsolationLevel.READ_COMMITTED

                t1_begin = f"BEGIN ISOLATION LEVEL {level_sql(t1_level)}"
                log_sql(1, t1_level, t1_begin)
                await t1.execute(t1_begin)

                t2_begin = f"BEGIN ISOLATION LEVEL {level_sql(level)}"
                log_sql(2, level, t2_begin)
                await t2.execute(t2_begin)

                update_t1 = f"UPDATE {table_name} SET on_call = false WHERE id = 1"
                log_sql(1, t1_level, update_t1)
                await t1.execute(update_t1)

                select_t2 = f"SELECT on_call FROM {table_name} WHERE id = 1"
                log_sql(2, level, select_t2)
                cursor = await t2.execute(select_t2)
                row = await cursor.fetchone()
                observed_value = row[0]
                log_value(2, level, observed_value)

                log_sql(1, t1_level, "ROLLBACK")
                await t1.execute("ROLLBACK")

                log_sql(2, level, select_t2)
                cursor = await t2.execute(select_t2)
                row = await cursor.fetchone()
                actual_value = row[0]
                log_value(2, level, actual_value)

                log_sql(2, level, "ROLLBACK")
                await t2.execute("ROLLBACK")

    return observed_value, actual_value


async def main() -> None:
    for level in (
        IsolationLevel.READ_UNCOMMITTED,
        IsolationLevel.READ_COMMITTED,
    ):
        await run_scenario(level)


if __name__ == "__main__":
    asyncio.run(main())
