from sqlalchemy import select

from shop_api.database import SessionLocal, engine, get_session
from shop_api.db_models import CartLineRecord, CartRecord, ItemRecord


def test_data_survives_engine_reconnect(client, cart, item):
    cart_path = f"/cart/{cart['id']}"
    assert client.post(f"{cart_path}/add/{item['id']}").status_code == 200
    expected = client.get(cart_path).json()

    engine.dispose()

    assert client.get(f"/item/{item['id']}").json() == item
    assert client.get(cart_path).json() == expected
    with SessionLocal() as session:
        line = session.scalar(select(CartLineRecord))
        assert line.cart_id == cart["id"]
        assert line.item_id == item["id"]
        assert line.quantity == 1


def test_uncommitted_data_is_rolled_back():
    sessions = get_session()
    session = next(sessions)
    item = ItemRecord(name="Uncommitted", price=10.0)
    session.add(item)
    session.flush()
    item_id = item.id

    sessions.close()

    with SessionLocal() as session:
        assert session.get(ItemRecord, item_id) is None


def test_cart_deletion_removes_its_lines(client, cart, item):
    assert client.post(f"/cart/{cart['id']}/add/{item['id']}").status_code == 200
    with SessionLocal.begin() as session:
        session.delete(session.get(CartRecord, cart["id"]))

    with SessionLocal() as session:
        assert session.get(CartRecord, cart["id"]) is None
        assert session.scalar(select(CartLineRecord)) is None
        assert session.get(ItemRecord, item["id"]) is not None
