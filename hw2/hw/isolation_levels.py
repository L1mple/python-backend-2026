import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:password@localhost:5432/shop")

def setup():
    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS isolation_demo"))
        conn.execute(text("CREATE TABLE isolation_demo (id INT PRIMARY KEY, value INT)"))
        conn.execute(text("INSERT INTO isolation_demo (id, value) VALUES (1, 10), (2, 20)"))
    print("Table isolation_demo created")

def reset_data():
    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM isolation_demo"))
        conn.execute(text("INSERT INTO isolation_demo (id, value) VALUES (1, 10), (2, 20)"))

def test_non_repeatable_read(isolation_level):
    reset_data()
    print(f"\nTest Non-Repeatable Read (Isolation Level: {isolation_level})")
    e1 = create_engine(DATABASE_URL, isolation_level=isolation_level)
    e2 = create_engine(DATABASE_URL, isolation_level="READ COMMITTED")
    
    s1, s2 = sessionmaker(bind=e1)(), sessionmaker(bind=e2)()
    
    val1 = s1.execute(text("SELECT value FROM isolation_demo WHERE id = 1")).scalar()
    print(f"Transaction 1: read value = {val1}")
    
    s2.execute(text("UPDATE isolation_demo SET value = 99 WHERE id = 1"))
    s2.commit()
    print("Transaction 2: updated value to 99 and committed")
    
    val2 = s1.execute(text("SELECT value FROM isolation_demo WHERE id = 1")).scalar()
    print(f"Transaction 1: read value again = {val2}")
    
    if val1 != val2:
        print("Anomaly: Non-Repeatable Read occurred")
    else:
        print("No anomaly: Non-Repeatable Read prevented")

def test_phantom_read(isolation_level):
    reset_data()
    print(f"\nTest Phantom Read (Isolation Level: {isolation_level})")
    e1 = create_engine(DATABASE_URL, isolation_level=isolation_level)
    e2 = create_engine(DATABASE_URL, isolation_level="READ COMMITTED")
    
    s1, s2 = sessionmaker(bind=e1)(), sessionmaker(bind=e2)()
    
    count1 = s1.execute(text("SELECT COUNT(*) FROM isolation_demo")).scalar()
    print(f"Transaction 1: read COUNT = {count1}")
    
    s2.execute(text("INSERT INTO isolation_demo (id, value) VALUES (3, 30)"))
    s2.commit()
    print("Transaction 2: inserted new row and committed")
    
    count2 = s1.execute(text("SELECT COUNT(*) FROM isolation_demo")).scalar()
    print(f"Transaction 1: read COUNT again = {count2}")
    
    if count1 != count2:
        print("Anomaly: Phantom Read occurred")
    else:
        print("No anomaly: Phantom Read prevented")

if __name__ == "__main__":
    setup()
    
    print("\nNote: In PostgreSQL READ UNCOMMITTED works as READ COMMITTED")
    print("Dirty Read is physically impossible, skipping this test\n")
    
    test_non_repeatable_read("READ COMMITTED")
    test_non_repeatable_read("REPEATABLE READ")
    
    test_phantom_read("READ COMMITTED")
    test_phantom_read("REPEATABLE READ")
    
    print("\nSerializable level in PostgreSQL prevents serialization anomalies (Write Skew)")