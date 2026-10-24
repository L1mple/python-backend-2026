"""Ветки, до которых не добраться через HTTP: сервисы и репозитории проверяют входные данные раньше."""
import pytest

from shop_api.exceptions import NotFoundError
from shop_api.models import Item
from shop_api.service import ChatService
from shop_api.storage import Store, InMemoryItemRepository, InMemoryCartRepository
from shop_api.storage.memory import BaseStore


def test_base_store_continues_ids_after_initial_data() -> None:
    store = BaseStore[str]({3: 'c', 1: 'a'})

    assert store.add('d') == 4
    assert store.get_all_with_ids() == [(3, 'c'), (1, 'a'), (4, 'd')]


async def test_mark_deleted_missing_item_is_noop() -> None:
    repo = InMemoryItemRepository(Store())

    await repo.mark_deleted(1)

    assert await repo.get(1) is None


async def test_item_repository_returns_copies() -> None:
    repo = InMemoryItemRepository(Store())
    item = await repo.add(Item(id=0, name='milk', price=10.0))

    item.name = 'changed'

    assert (await repo.get(item.id)).name == 'milk'


async def test_add_item_to_missing_cart_raises() -> None:
    repo = InMemoryCartRepository(Store())

    with pytest.raises(NotFoundError):
        await repo.add_item(1, 1)


async def test_cart_skips_unknown_items() -> None:
    store = Store()
    carts = InMemoryCartRepository(store)
    cart = await carts.add()

    await carts.add_item(cart.id, 42)
    stored = await carts.get(cart.id)

    assert stored.items == []
    assert stored.price == 0.0


async def test_publish_to_unknown_chat_is_noop() -> None:
    await ChatService().publish('nobody', 'user', 'hello')


def test_unsubscribe_from_unknown_chat_is_noop() -> None:
    ChatService().unsubscribe('nobody', object())


def test_generate_username() -> None:
    username = ChatService.generate_username()

    assert len(username) == 10
    assert username.isalpha() and username.islower()
