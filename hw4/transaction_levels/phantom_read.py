import asyncio

from psycopg import AsyncConnection, IsolationLevel

from .common import DATABASE_URL, doctors_table, level_sql, log_sql, log_value


async def run_scenario(level: IsolationLevel) -> tuple[int, int]:
    async with doctors_table() as table_name:
        async with await AsyncConnection.connect(DATABASE_URL) as t1:
            async with await AsyncConnection.connect(DATABASE_URL) as t2:
                t2_level = IsolationLevel.READ_COMMITTED

                t1_begin = f"BEGIN ISOLATION LEVEL {level_sql(level)}"
                log_sql(1, level, t1_begin)
                await t1.execute(t1_begin)

                t2_begin = f"BEGIN ISOLATION LEVEL {level_sql(t2_level)}"
                log_sql(2, t2_level, t2_begin)
                await t2.execute(t2_begin)

                select_t1 = f"SELECT count(*) FROM {table_name} WHERE on_call"
                log_sql(1, level, select_t1)
                cursor = await t1.execute(select_t1)
                row = await cursor.fetchone()
                first_count = row[0]
                log_value(1, level, first_count)

                insert_t2 = f"INSERT INTO {table_name}(id, name, on_call) VALUES (3, 'Charlie', true)"
                log_sql(2, t2_level, insert_t2)
                await t2.execute(insert_t2)
                log_sql(2, t2_level, "COMMIT")
                await t2.execute("COMMIT")

                log_sql(1, level, select_t1)
                cursor = await t1.execute(select_t1)
                row = await cursor.fetchone()
                second_count = row[0]
                log_value(1, level, second_count)

                log_sql(1, level, "ROLLBACK")
                await t1.execute("ROLLBACK")

    return first_count, second_count


async def main() -> None:
    for level in (
        IsolationLevel.REPEATABLE_READ,
        IsolationLevel.SERIALIZABLE,
    ):
        await run_scenario(level)


if __name__ == "__main__":
    asyncio.run(main())
