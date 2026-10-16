from dataclasses import dataclass, asdict, Field


@dataclass
class Item:
    id: int
    name: str
    price: float
    deleted: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        return cls(**data)


@dataclass
class Cart:
    id: int
    items: dict[int, int]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Cart":
        return cls(**data)

@dataclass
class CartItem:
    id: int
    name: str
    quantity: int
    available: bool


@dataclass
class FullCart:
    id: int
    items: list[CartItem]
    price: float
    quantity: int

