import os
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select


database_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:password@localhost:5432/shop")
engine = create_engine(database_url)
metadata = MetaData()
example = Table("example_db", metadata, Column("id", Integer, primary_key=True), Column("value", Integer, nullable=False))
metadata.create_all(engine)


def reset_db() -> None:
    with engine.connect() as connect:
        transaction = connect.begin()
        connect.execute(example.delete())
        connect.execute(example.insert().values(id=1, value=100))
        transaction.commit()


reset_db()
print("dirty read")
with engine.connect().execution_options(isolation_level="READ UNCOMMITTED") as connect1, \
        engine.connect().execution_options(isolation_level="READ UNCOMMITTED") as connect2:
    transaction1 = connect1.begin()
    value1 = connect1.execute(select(example.c.value).where(example.c.id == 1)).scalar_one()
    with connect2.begin():
        connect2.execute(example.update().where(example.c.id == 1).values(value=200))
        value2 = connect1.execute(select(example.c.value).where(example.c.id == 1)).scalar_one()
    transaction1.commit()
print(f"Первое чтение: {value1}")
print(f"Второе чтение: {value2}")
print("Dirty read?", value1 != value2)
print()


reset_db()
print("read commited")
with engine.connect().execution_options(isolation_level="READ COMMITTED") as connect1, \
        engine.connect().execution_options(isolation_level="READ COMMITTED") as connect2:
    transaction1 = connect1.begin()
    value1 = connect1.execute(select(example.c.value).where(example.c.id == 1)).scalar_one()
    with connect2.begin():
        connect2.execute(example.update().where(example.c.id == 1).values(value=200))
        value2 = connect1.execute(select(example.c.value).where(example.c.id == 1)).scalar_one()
    transaction1.commit()
print(f"Первое чтение: {value1}")
print(f"Второе чтение: {value2}")
print("Dirty read?", value1 != value2)
print()


reset_db()
print("non-repeatable read")
with engine.connect().execution_options(isolation_level="READ COMMITTED") as connect1, \
        engine.connect().execution_options(isolation_level="READ COMMITTED") as connect2:
    transaction1 = connect1.begin()
    value1 = connect1.execute(select(example.c.value).where(example.c.id == 1)).scalar_one()
    with connect2.begin():
        connect2.execute(example.update().where(example.c.id == 1).values(value=200))
    value2 = connect1.execute(select(example.c.value).where(example.c.id == 1)).scalar_one()
    transaction1.commit()
print(f"Первое чтение: {value1}")
print(f"Второе чтение: {value2}")
print("Non-repeatable read?", value1 != value2)
print()


reset_db()
print("repeatable read")
with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connect1, \
        engine.connect().execution_options(isolation_level="REPEATABLE READ") as connect2:
    transaction1 = connect1.begin()
    value1 = connect1.execute(select(example.c.value).where(example.c.id == 1)).scalar_one()
    with connect2.begin():
        connect2.execute(example.update().where(example.c.id == 1).values(value=200))
    value2 = connect1.execute(select(example.c.value).where(example.c.id == 1)).scalar_one()
    transaction1.commit()
print(f"Первое чтение: {value1}")
print(f"Второе чтение: {value2}")
print("Non-repeatable read?", value1 != value2)
print()


reset_db()
print("phantom read")
with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connect1, \
        engine.connect().execution_options(isolation_level="REPEATABLE READ") as connect2:
    transaction1 = connect1.begin()
    value1 = list(connect1.execute(select(example.c.id).where(example.c.value == 100)))
    with connect2.begin():
        connect2.execute(example.insert().values(id=2, value=100))
    value2 = list(connect1.execute(select(example.c.id).where(example.c.value == 100)))
    transaction1.commit()
print(f"Первое чтение: {value1}")
print(f"Второе чтение: {value2}")
print("Phantom read?", value1 != value2)
print()


reset_db()
print("serializable read")
with engine.connect().execution_options(isolation_level="SERIALIZABLE") as connect1, \
        engine.connect().execution_options(isolation_level="SERIALIZABLE") as connect2:
    transaction1 = connect1.begin()
    value1 = list(connect1.execute(select(example.c.id).where(example.c.value == 100)))
    with connect2.begin():
        connect2.execute(example.insert().values(id=2, value=100))
    value2 = list(connect1.execute(select(example.c.id).where(example.c.value == 100)))
    transaction1.commit()
print(f"Первое чтение: {value1}")
print(f"Второе чтение: {value2}")
print("Phantom read?", value1 != value2)
