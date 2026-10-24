from dataclasses import dataclass, field
from typing import List, Dict, TypeAlias


@dataclass(slots=True)
class AddItemInfo:
    name: str
    price: float

@dataclass(slots=True)
class ItemInfo:
    name: str
    price: float
    deleted: bool = False

@dataclass(slots=True)
class ItemEntity:
    id: int
    info: ItemInfo

@dataclass(slots=True)
class PatchItemInfo:
    name: str|None
    price: float|None

CartPositionsInfo : TypeAlias = Dict[int, int]

@dataclass(slots=True)
class CartInfo:
    positions: CartPositionsInfo = field(default_factory=dict)
    price: float = 0
    quantity: int = 0

@dataclass(slots=True)
class CartEntity:
    id: int
    info: CartInfo = field(default_factory=CartInfo)
