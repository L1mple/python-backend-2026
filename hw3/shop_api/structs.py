from dataclasses import dataclass, field


@dataclass(slots=True)
class Item:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass(slots=True)
class Cart:
    id: int
    items: dict[int, int] = field(default_factory=dict)
