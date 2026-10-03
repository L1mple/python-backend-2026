from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ItemEntity:
    id: int
    name: str
    price: float
    deleted: bool = False
