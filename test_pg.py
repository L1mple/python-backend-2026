import asyncio, asyncpg
async def _():
    conn = await asyncpg.connect(database='postgres', user='postgres', password='postgres', host='127.0.0.1', port=5432)
    print(conn.fetchval('SELECT version()'))
    conn.close()
asyncio.run(_)
