import json
import pathlib

from shop_api.models import Item, Cart

JSON_PATH = "./data.json"


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

    @property
    def items(self) -> ItemStore:
        return self._items

    @property
    def carts(self) -> CartStore:
        return self._carts

    @staticmethod
    def _from_dicts(obj_type, objs: dict[int, dict]):
        return {int(key): obj_type.from_dict(obj) for key, obj in objs.items()}

    @staticmethod
    def _to_dicts(objs: dict):
        return {key: obj.to_dict() for key, obj in objs.items()}

    def load_from_file(self):
        if pathlib.Path(JSON_PATH).exists():
            with open(JSON_PATH, "r") as f:
                data = json.load(f)
        else:
            data = {
                "items": {},
                "carts": {},
            }

        self._items = ItemStore(self._from_dicts(Item, data["items"]))
        self._carts = CartStore(self._from_dicts(Cart, data["carts"]))

    def save_to_file(self):
        with open(JSON_PATH, "w+") as f:
            data = {
                "items": self._to_dicts(self._items.dump),
                "carts": self._to_dicts(self._carts.dump),
            }
            json.dump(data, f, indent=4)

    def __enter__(self):
        self.load_from_file()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save_to_file()
