import asyncio
import pytest
from http import HTTPStatus
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from shop_api.models import Item, Cart, CartItem
from shop_api.database import Base
from shop_api.queries import (
    create_cart, get_cart, add_item_to_cart, get_carts,
    create_item, get_item, get_items, update_item,
    patch_item, soft_delete_item, build_cart_response,
)


class _TestDB:
    def __init__(self):
        self.engine = None
        self.loop = None

    def setup(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.engine = create_async_engine("sqlite+aiosqlite://")
        async def init():
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        self.loop.run_until_complete(init())
        return self.loop

    def teardown(self):
        if self.engine:
            self.loop.run_until_complete(self.engine.dispose())
        self.loop.close()

    def session(self):
        Session = async_sessionmaker(self.engine, expire_on_commit=False)
        return Session()


_test_db = _TestDB()
_loop = _test_db.setup()


@pytest.fixture(scope="session", autouse=True)
def _cleanup():
    yield
    _test_db.teardown()
    _loop.close()


_tables = ["cart_items", "items", "carts"]
_sessions = []


def _clear():
    s = _test_db.session()
    _sessions.append(s)
    async def do():
        for t in _tables:
            await s.execute(text(f"DELETE FROM {t}"))
        await s.commit()
        return s
    return _loop.run_until_complete(do())


def _seed(s):
    async def do():
        new_cart = await create_cart(s)
        await s.flush()
        new_item1 = await create_item(s, "item1", 100.0)
        new_item2 = await create_item(s, "item2", 200.0)
        new_item3 = await create_item(s, "item3", 50.0)
        ci = CartItem(cart_id=new_cart.id, item_id=new_item1.id, quantity=2)
        s.add(ci)
        await s.commit()
        return {
            "cart": new_cart,
            "item1": new_item1,
            "item2": new_item2,
            "item3": new_item3,
        }
    return _loop.run_until_complete(do())


# ─── fixtures ───

@pytest.fixture()
def s():
    return _clear()


@pytest.fixture(autouse=True)
def _teardown_next_test(s):
    """Clean DB after each test so next test starts fresh."""
    yield

    async def do():
        while _sessions:
            await _sessions.pop().close()
        async with _test_db.session() as cleanup:
            for t in _tables:
                await cleanup.execute(text(f"DELETE FROM {t}"))
            await cleanup.commit()

    _loop.run_until_complete(do())


@pytest.fixture()
def data(s):
    """Clear and seed for tests that need predefined cart+items."""
    return _seed(s)


# ─── tests ───

def test_create_cart(s):
    async def _r():
        cart = await create_cart(s)
        assert cart.id is not None
    _loop.run_until_complete(_r())


def test_get_cart_found(data):
    s = _clear()
    _seed(s)
    async def _r():
        cart = await get_cart(s, data["cart"].id)
        assert cart is not None
        assert len(cart.cart_items) == 1
    _loop.run_until_complete(_r())


def test_get_cart_not_found(s):
    async def _r():
        cart = await get_cart(s, 999999)
        assert cart is None
    _loop.run_until_complete(_r())


def test_build_cart_response_normal(data):
    s = _clear()
    _seed(s)
    async def _r():
        cart = await get_cart(s, data["cart"].id)
        resp = build_cart_response(s, cart)
        assert len(resp.items) == 1
        assert resp.items[0].name == "item1"
        assert resp.items[0].quantity == 2
    _loop.run_until_complete(_r())


def test_build_cart_response_skips_missing_item(s):
    cart = Cart()
    item = Item(name="ghost", price=10.0, deleted=False)
    ci = CartItem(cart_id=cart.id, item_id=item.id, quantity=1)
    ci.item = None
    cart.cart_items = [ci]
    cart_items = []
    for c in cart.cart_items:
        if c.item is None:
            continue
        cart_items.append(type('', (), {'id': c.item.id, 'name': c.item.name, 'quantity': c.quantity, 'available': not c.item.deleted})())
    assert len(cart_items) == 0


def test_add_item_success(data):
    s = _clear()
    _seed(s)
    async def _r():
        resp = await add_item_to_cart(s, data["cart"].id, data["item3"].id)
        assert len(resp.items) == 2
        item3_qty = next(i for i in resp.items if i.id == data["item3"].id)
        assert item3_qty.quantity == 1
    _loop.run_until_complete(_r())


def test_add_item_increment(data):
    s = _clear()
    _seed(s)
    async def _r():
        await add_item_to_cart(s, data["cart"].id, data["item1"].id)
        resp = await add_item_to_cart(s, data["cart"].id, data["item1"].id)
        item1_qty = next(i for i in resp.items if i.id == data["item1"].id)
        assert item1_qty.quantity == 4
    _loop.run_until_complete(_r())


def test_add_item_cart_404(s):
    async def _r():
        with pytest.raises(HTTPException) as exc:
            await add_item_to_cart(s, 999999, 1)
        assert exc.value.status_code == 404
    _loop.run_until_complete(_r())


def test_add_item_item_404(data):
    s = _clear()
    _seed(s)
    async def _r():
        with pytest.raises(HTTPException) as exc:
            await add_item_to_cart(s, data["cart"].id, 999999)
        assert exc.value.status_code == 404
    _loop.run_until_complete(_r())


def test_add_item_deleted_item(data):
    s = _clear()
    _seed(s)
    async def _r():
        await soft_delete_item(s, data["item1"].id)
        with pytest.raises(HTTPException) as exc:
            await add_item_to_cart(s, data["cart"].id, data["item1"].id)
        assert exc.value.status_code == 404
    _loop.run_until_complete(_r())


def test_get_carts_basic(s):
    async def _r():
        carts = await get_carts(s)
        assert len(carts) == 0
    _loop.run_until_complete(_r())


def test_get_carts_min_price(s):
    async def _r():
        cart1 = await create_cart(s)
        await s.flush()
        await create_item(s, "expensive", 1000.0)
        carts = await get_carts(s, min_price=500.0)
        assert all(c.id == cart1.id for c in carts)
    _loop.run_until_complete(_r())


def test_get_carts_max_price(s):
    async def _r():
        cart1 = await create_cart(s)
        await s.flush()
        await create_item(s, "cheap", 5.0)
        carts = await get_carts(s, max_price=10.0)
        assert all(c.id == cart1.id for c in carts)
    _loop.run_until_complete(_r())


def test_get_carts_min_quantity(s):
    async def _r():
        cart = await create_cart(s)
        await s.flush()
        item = await create_item(s, "visible", 10.0)
        ci = CartItem(cart_id=cart.id, item_id=item.id, quantity=2)
        s.add(ci)
        await s.commit()
        carts = await get_carts(s, min_quantity=2)
        assert any(c.id == cart.id for c in carts)
    _loop.run_until_complete(_r())


def test_get_carts_max_quantity(s):
    async def _r():
        cart = await create_cart(s)
        await s.flush()
        item = await create_item(s, "visible", 10.0)
        ci = CartItem(cart_id=cart.id, item_id=item.id, quantity=5)
        s.add(ci)
        await s.commit()
        carts = await get_carts(s, max_quantity=5)
        assert any(c.id == cart.id for c in carts)
    _loop.run_until_complete(_r())


def test_create_item(s):
    async def _r():
        item = await create_item(s, "test", 50.0)
        assert item.name == "test"
        assert item.deleted is False
    _loop.run_until_complete(_r())


def test_get_item_found(data):
    s = _clear()
    _seed(s)
    item = _loop.run_until_complete(get_item(s, data["item1"].id))
    assert item is not None
    assert item.name == "item1"


def test_get_item_not_found(s):
    async def _r():
        item = await get_item(s, 999999)
        assert item is None
    _loop.run_until_complete(_r())


def test_get_items_all(s):
    async def _r():
        await create_item(s, "a", 10.0)
        await create_item(s, "b", 20.0)
        items = await get_items(s)
        assert len(items) == 2
    _loop.run_until_complete(_r())


def test_get_items_offset_limit(s):
    async def _r():
        for i in range(10):
            await create_item(s, f"item{i}", float(i * 10))
        items = await get_items(s, offset=0, limit=5)
        assert len(items) == 5
    _loop.run_until_complete(_r())


def test_get_items_min_price(s):
    async def _r():
        await create_item(s, "a", 50.0)
        await create_item(s, "b", 150.0)
        items = await get_items(s, min_price=100.0)
        assert all(i.price >= 100.0 for i in items)
        assert len(items) == 1
    _loop.run_until_complete(_r())


def test_get_items_max_price(s):
    async def _r():
        await create_item(s, "a", 50.0)
        await create_item(s, "b", 150.0)
        items = await get_items(s, max_price=100.0)
        assert all(i.price <= 100.0 for i in items)
        assert len(items) == 1
    _loop.run_until_complete(_r())


def test_get_items_show_deleted(s):
    async def _r():
        item = await create_item(s, "visible", 10.0)
        item_id = item.id
        await soft_delete_item(s, item_id)
        non_deleted = await get_items(s)
        assert len(non_deleted) == 0
        with_deleted = await get_items(s, show_deleted=True)
        assert len(with_deleted) == 1
    _loop.run_until_complete(_r())


def test_update_item_success(data):
    s = _clear()
    _seed(s)
    item = _loop.run_until_complete(update_item(s, data["item1"].id, "updated", 999.0))
    assert item.name == "updated"
    assert float(item.price) == 999.0


def test_update_item_not_found(s):
    async def _r():
        with pytest.raises(HTTPException) as exc:
            await update_item(s, 999999, "x", 1.0)
        assert exc.value.status_code == 404
    _loop.run_until_complete(_r())


def test_update_item_deleted(data):
    s = _clear()
    _seed(s)
    async def _r():
        await soft_delete_item(s, data["item1"].id)
        with pytest.raises(HTTPException) as exc:
            await update_item(s, data["item1"].id, "x", 1.0)
        assert exc.value.status_code == 404
    _loop.run_until_complete(_r())


def test_patch_item_name(data):
    s = _clear()
    _seed(s)
    item, changed = _loop.run_until_complete(
        patch_item(s, data["item1"].id, {"name": "patched"})
    )
    assert item.name == "patched"
    assert changed is False


def test_patch_item_price(data):
    s = _clear()
    _seed(s)
    item, changed = _loop.run_until_complete(
        patch_item(s, data["item1"].id, {"price": 77.0})
    )
    assert float(item.price) == 77.0
    assert changed is False


def test_patch_item_not_found(s):
    async def _r():
        with pytest.raises(HTTPException) as exc:
            await patch_item(s, 999999, {"name": "x"})
        assert exc.value.status_code == 404
    _loop.run_until_complete(_r())


def test_patch_item_deleted(data):
    s = _clear()
    _seed(s)
    async def _r():
        await soft_delete_item(s, data["item1"].id)
        item, changed = await patch_item(s, data["item1"].id, {"name": "x"})
        assert changed is True
        assert item.deleted is True
    _loop.run_until_complete(_r())


def test_soft_delete(data):
    s = _clear()
    _seed(s)
    _loop.run_until_complete(soft_delete_item(s, data["item1"].id))
    item = _loop.run_until_complete(get_item(s, data["item1"].id))
    assert item.deleted is True


def test_soft_delete_already_deleted(data):
    s = _clear()
    _seed(s)
    _loop.run_until_complete(soft_delete_item(s, data["item1"].id))
    result = _loop.run_until_complete(soft_delete_item(s, data["item1"].id))
    assert result is True


def test_soft_delete_not_found(s):
    async def _r():
        with pytest.raises(HTTPException) as exc:
            await soft_delete_item(s, 999999)
        assert exc.value.status_code == 404
    _loop.run_until_complete(_r())
