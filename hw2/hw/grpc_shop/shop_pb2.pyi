from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class IdRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: int
    def __init__(self, id: _Optional[int] = ...) -> None: ...

class IdResponse(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: int
    def __init__(self, id: _Optional[int] = ...) -> None: ...

class CreateItemRequest(_message.Message):
    __slots__ = ("name", "price")
    NAME_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    name: str
    price: float
    def __init__(self, name: _Optional[str] = ..., price: _Optional[float] = ...) -> None: ...

class ReplaceItemRequest(_message.Message):
    __slots__ = ("id", "name", "price")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    price: float
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., price: _Optional[float] = ...) -> None: ...

class PatchItemRequest(_message.Message):
    __slots__ = ("id", "name", "price")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    price: float
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., price: _Optional[float] = ...) -> None: ...

class GetItemsRequest(_message.Message):
    __slots__ = ("offset", "limit", "min_price", "max_price", "show_deleted")
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    MIN_PRICE_FIELD_NUMBER: _ClassVar[int]
    MAX_PRICE_FIELD_NUMBER: _ClassVar[int]
    SHOW_DELETED_FIELD_NUMBER: _ClassVar[int]
    offset: int
    limit: int
    min_price: float
    max_price: float
    show_deleted: bool
    def __init__(self, offset: _Optional[int] = ..., limit: _Optional[int] = ..., min_price: _Optional[float] = ..., max_price: _Optional[float] = ..., show_deleted: _Optional[bool] = ...) -> None: ...

class Item(_message.Message):
    __slots__ = ("id", "name", "price", "deleted")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    DELETED_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    price: float
    deleted: bool
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., price: _Optional[float] = ..., deleted: _Optional[bool] = ...) -> None: ...

class ItemList(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Item]
    def __init__(self, items: _Optional[_Iterable[_Union[Item, _Mapping]]] = ...) -> None: ...

class AddItemRequest(_message.Message):
    __slots__ = ("cart_id", "item_id")
    CART_ID_FIELD_NUMBER: _ClassVar[int]
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    cart_id: int
    item_id: int
    def __init__(self, cart_id: _Optional[int] = ..., item_id: _Optional[int] = ...) -> None: ...

class GetCartsRequest(_message.Message):
    __slots__ = ("offset", "limit", "min_price", "max_price", "min_quantity", "max_quantity")
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    MIN_PRICE_FIELD_NUMBER: _ClassVar[int]
    MAX_PRICE_FIELD_NUMBER: _ClassVar[int]
    MIN_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    MAX_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    offset: int
    limit: int
    min_price: float
    max_price: float
    min_quantity: int
    max_quantity: int
    def __init__(self, offset: _Optional[int] = ..., limit: _Optional[int] = ..., min_price: _Optional[float] = ..., max_price: _Optional[float] = ..., min_quantity: _Optional[int] = ..., max_quantity: _Optional[int] = ...) -> None: ...

class CartItem(_message.Message):
    __slots__ = ("id", "name", "quantity", "available")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    quantity: int
    available: bool
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., quantity: _Optional[int] = ..., available: _Optional[bool] = ...) -> None: ...

class Cart(_message.Message):
    __slots__ = ("id", "items", "price")
    ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    id: int
    items: _containers.RepeatedCompositeFieldContainer[CartItem]
    price: float
    def __init__(self, id: _Optional[int] = ..., items: _Optional[_Iterable[_Union[CartItem, _Mapping]]] = ..., price: _Optional[float] = ...) -> None: ...

class CartList(_message.Message):
    __slots__ = ("carts",)
    CARTS_FIELD_NUMBER: _ClassVar[int]
    carts: _containers.RepeatedCompositeFieldContainer[Cart]
    def __init__(self, carts: _Optional[_Iterable[_Union[Cart, _Mapping]]] = ...) -> None: ...
