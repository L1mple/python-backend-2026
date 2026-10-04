from shop_api.models import Item, Cart


class BaseStore[T]:
    _data: dict[int, T]
    _last_id: int

    def __init__(self, data: dict[int, T] | None = None):
        self._data = data or {}
        self._last_id = max(map(int, self._data.keys()), default=0)

    def _get_next_id(self) -> int:
        self._last_id += 1
        return self._last_id

    def get_all(self) -> list[T]:
        return list(self._data.values())

    def get(self, obj_id: int) -> T | None:
        return self._data.get(obj_id)

    def add(self, obj: T) -> T:
        obj.id = self._get_next_id()
        return self.set(obj)

    def set(self, obj: T) -> T:
        self._data[obj.id] = obj
        return obj

    def remove(self, obj_id: int) -> None:
        if obj_id in self._data:
            del self._data[obj_id]

    @property
    def dump(self) -> dict[int, dict]:
        return self._data


class ItemStore(BaseStore[Item]):
    pass


class CartStore(BaseStore[Cart]):
    pass


class Store:
    _items: ItemStore
    _carts: CartStore

    def __init__(self):
        self._items = ItemStore({})
        self._carts = CartStore({})

    @property
    def items(self) -> ItemStore:
        return self._items

    @property
    def carts(self) -> CartStore:
        return self._carts
