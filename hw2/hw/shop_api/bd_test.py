from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DB_URL = "postgresql+psycopg2://user:password@localhost:5432/shop_db"
engine = create_engine(DB_URL)

def get_session(iso_level):
    return sessionmaker(bind=engine.execution_options(isolation_level=iso_level))()

def setup_db():
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS test_items;"))
        conn.execute(text("CREATE TABLE test_items (id SERIAL PRIMARY KEY, name VARCHAR, price FLOAT);"))
        conn.execute(text("INSERT INTO test_items (name, price) VALUES ('Item1', 100);"))
        conn.commit()

# 1. NON-REPEATABLE READ
def test_non_repeatable_read(iso_level):
    print(f"\n Тест: Non-Repeatable Read (Уровень: {iso_level})")
    setup_db()
    t1 = get_session(iso_level)
    t2 = get_session(iso_level)

    try:
        res1 = t1.execute(text("SELECT price FROM test_items WHERE id = 1")).fetchone()

        # Клиент 2 меняет данные и коммитит
        t2.execute(text("UPDATE test_items SET price = 555 WHERE id = 1"))
        t2.commit()

        res2 = t1.execute(text("SELECT price FROM test_items WHERE id = 1")).fetchone()

        if res1[0] != res2[0]:
            print("ОБНАРУЖЕНО Non-Repeatable Read! Данные изменились между чтениями")
        else:
            print("НЕ ОБНАРУЖЕНО Non-Repeatable Read. Клиент 1 видит стабильные данные")
    finally:
        t1.rollback()
        t1.close()
        t2.close()

# 2. PHANTOM READ
def test_phantom_read(iso_level):
    print(f"\n Тест: Phantom Read (Уровень: {iso_level})")
    setup_db()
    t1 = get_session(iso_level)
    t2 = get_session(iso_level)

    try:
        res1 = t1.execute(text("SELECT COUNT(*) FROM test_items")).fetchone()

        # Клиент 2 добавляет новую строку и коммитит
        t2.execute(text("INSERT INTO test_items (name, price) VALUES ('Item2', 200)"))
        t2.commit()

        res2 = t1.execute(text("SELECT COUNT(*) FROM test_items")).fetchone()

        if res1[0] != res2[0]:
            print("ОБНАРУЖЕНО Phantom Read! Появились новые строки в выборке")
        else:
            print("НЕ ОБНАРУЖЕН Phantom Read")
    finally:
        t1.rollback()
        t1.close()
        t2.close()

if __name__ == "__main__":
    # В Postgres Dirty Read архитектурно невозможно  

    # 1. Показываем, что на RC есть неповторяющееся чтение, а на RR - нет
    test_non_repeatable_read("READ COMMITTED")
    test_non_repeatable_read("REPEATABLE READ")

    # 2. Показываем фантомное чтение
    test_phantom_read("READ COMMITTED")

    # На уровне SERIALIZABLE (и RR) Postgres его гарантированно блокирует
    test_phantom_read("SERIALIZABLE")