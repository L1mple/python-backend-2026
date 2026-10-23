from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

engine = create_engine('postgresql+psycopg2://postgres:password@localhost:5432/shop_db')
Session = sessionmaker(bind=engine)


def reset():
    with engine.begin() as conn:
        conn.execute(text('DROP TABLE IF EXISTS demo_items'))
        conn.execute(text(
            'CREATE TABLE demo_items (id SERIAL PRIMARY KEY, name TEXT, price FLOAT)'
        ))
        conn.execute(text("INSERT INTO demo_items (name, price) VALUES ('milk', 100)"))


def price(s):
    return s.execute(text('SELECT price FROM demo_items WHERE id = 1')).scalar()


def count(s):
    return s.execute(text('SELECT COUNT(*) FROM demo_items')).scalar()


def begin(s, level):
    s.execute(text(f'BEGIN ISOLATION LEVEL {level}'))


def test_dirty_read_uncommitted():
    reset()
    a, b = Session(), Session()
    begin(a, 'READ UNCOMMITTED')
    a.execute(text('UPDATE demo_items SET price = 999 WHERE id = 1'))
    begin(b, 'READ UNCOMMITTED')
    assert price(b) == 100
    a.rollback()
    b.rollback()
    a.close()
    b.close()
    print('ok: dirty read / READ UNCOMMITTED')


def test_no_dirty_read_committed():
    reset()
    a, b = Session(), Session()
    begin(a, 'READ COMMITTED')
    a.execute(text('UPDATE demo_items SET price = 999 WHERE id = 1'))
    begin(b, 'READ COMMITTED')
    assert price(b) == 100
    a.rollback()
    b.rollback()
    a.close()
    b.close()
    print('ok: no dirty read / READ COMMITTED')


def test_non_repeatable_read_committed():
    reset()
    a, b = Session(), Session()
    begin(a, 'READ COMMITTED')
    first = price(a)
    begin(b, 'READ COMMITTED')
    b.execute(text('UPDATE demo_items SET price = 200 WHERE id = 1'))
    b.commit()
    second = price(a)
    assert first == 100 and second == 200
    a.rollback()
    a.close()
    b.close()
    print('ok: non-repeatable read / READ COMMITTED')


def test_no_non_repeatable_repeatable_read():
    reset()
    a, b = Session(), Session()
    begin(a, 'REPEATABLE READ')
    first = price(a)
    begin(b, 'READ COMMITTED')
    b.execute(text('UPDATE demo_items SET price = 200 WHERE id = 1'))
    b.commit()
    second = price(a)
    assert first == 100 and second == 100
    a.rollback()
    a.close()
    b.close()
    print('ok: no non-repeatable read / REPEATABLE READ')


def test_phantom_repeatable_read():
    reset()
    a, b = Session(), Session()
    begin(a, 'REPEATABLE READ')
    first = count(a)
    begin(b, 'READ COMMITTED')
    b.execute(text("INSERT INTO demo_items (name, price) VALUES ('bread', 50)"))
    b.commit()
    second = count(a)
    assert first == second == 1
    a.rollback()
    a.close()
    b.close()

    reset()
    a, b = Session(), Session()
    begin(a, 'READ COMMITTED')
    first = count(a)
    begin(b, 'READ COMMITTED')
    b.execute(text("INSERT INTO demo_items (name, price) VALUES ('bread', 50)"))
    b.commit()
    second = count(a)
    assert first == 1 and second == 2
    a.rollback()
    a.close()
    b.close()
    print('ok: phantom read / REPEATABLE READ (и сравнение с READ COMMITTED)')


def test_no_phantom_serializable():
    reset()
    a, b = Session(), Session()
    begin(a, 'SERIALIZABLE')
    first = count(a)
    begin(b, 'SERIALIZABLE')
    b.execute(text("INSERT INTO demo_items (name, price) VALUES ('bread', 50)"))
    b.commit()
    second = count(a)
    assert first == second == 1
    a.rollback()
    a.close()
    b.close()
    print('ok: no phantom read / SERIALIZABLE')


if __name__ == '__main__':
    test_dirty_read_uncommitted()
    test_no_dirty_read_committed()
    test_non_repeatable_read_committed()
    test_no_non_repeatable_repeatable_read()
    test_phantom_repeatable_read()
    test_no_phantom_serializable()
