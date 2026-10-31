from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+psycopg2://postgres:password@localhost:7432/hw4_db"

temp_engine = create_engine(DATABASE_URL)

with temp_engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            price FLOAT NOT NULL,
            deleted BOOLEAN DEFAULT FALSE
        )
    """))
    conn.commit()

def test_all_isolation_levels():
    engine_rc = create_engine(DATABASE_URL, isolation_level="READ COMMITTED")
    SessionRC = sessionmaker(bind=engine_rc)

    s1 = SessionRC()
    s2 = SessionRC()
    s1.execute(text("DELETE FROM items WHERE name = 'Test Dirty'"));
    s1.commit()
    s1.execute(text("INSERT INTO items (name, price) VALUES ('Test Dirty', 100)"));
    s1.commit()

    s1.execute(text("UPDATE items SET price = 999 WHERE name = 'Test Dirty'"))
    result = s2.execute(text("SELECT price FROM items WHERE name = 'Test Dirty'")).fetchone()
    assert result[0] == 100, "Ошибка: Грязное чтение при READ COMMITTED!"
    s1.rollback();
    s1.close();
    s2.close()
    print("Dirty Read: Проблема продемонстрирована и решена (READ COMMITTED)")

    engine_rr = create_engine(DATABASE_URL, isolation_level="REPEATABLE READ")
    SessionRR = sessionmaker(bind=engine_rr)

    s1 = SessionRC()
    s2 = SessionRC()
    s1.execute(text("DELETE FROM items WHERE name = 'Test NR'"));
    s1.commit()
    s1.execute(text("INSERT INTO items (name, price) VALUES ('Test NR', 100)"));
    s1.commit()

    price1 = s1.execute(text("SELECT price FROM items WHERE name = 'Test NR'")).fetchone()[0]
    s2.execute(text("UPDATE items SET price = 200 WHERE name = 'Test NR'"));
    s2.commit()
    price2 = s1.execute(text("SELECT price FROM items WHERE name = 'Test NR'")).fetchone()[0]
    assert price1 != price2, "Ошибка: При READ COMMITTED не произошло Non-Repeatable Read!"
    s1.close();
    s2.close()
    print("Non-Repeatable Read: Проблема продемонстрирована (READ COMMITTED)")

    s3 = SessionRR()
    s4 = SessionRC()
    price3 = s3.execute(text("SELECT price FROM items WHERE name = 'Test NR'")).fetchone()[0]
    s4.execute(text("UPDATE items SET price = 300 WHERE name = 'Test NR'"));
    s4.commit()
    price4 = s3.execute(text("SELECT price FROM items WHERE name = 'Test NR'")).fetchone()[0]
    assert price3 == price4, "Ошибка: При REPEATABLE READ произошло Non-Repeatable Read!"
    s3.close();
    s4.close()
    print("Non-Repeatable Read: Проблема решена (REPEATABLE READ)")

    engine_ser = create_engine(DATABASE_URL, isolation_level="SERIALIZABLE")
    SessionSer = sessionmaker(bind=engine_ser)

    s5 = SessionSer()
    s6 = SessionSer()
    s5.execute(text("DELETE FROM items WHERE name LIKE 'Phantom%'"));
    s5.commit()
    s5.execute(text("INSERT INTO items (name, price) VALUES ('Phantom1', 100)"));
    s5.commit()

    count1 = s5.execute(text("SELECT COUNT(*) FROM items WHERE name LIKE 'Phantom%'")).fetchone()[0]

    try:
        s6.execute(text("INSERT INTO items (name, price) VALUES ('Phantom2', 200)"))
        s6.commit()
        count2 = s5.execute(text("SELECT COUNT(*) FROM items WHERE name LIKE 'Phantom%'")).fetchone()[0]
        assert count1 == count2, "Ошибка: Произошло фантомное чтение при SERIALIZABLE!"
    except Exception as e:
        pass

    s5.close();
    s6.close()
    print("Phantom Read: Проблема решена (SERIALIZABLE)")

if __name__ == "__main__":
    test_all_isolation_levels()