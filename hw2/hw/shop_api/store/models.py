from dataclasses import dataclass, field


@dataclass
class Item:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass
class Cart:
    id: int
    item_id_to_count: dict[int, int] = field(default_factory=dict)
