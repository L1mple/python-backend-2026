from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CartEntity:
    id: int
    items: dict[int, int] = field(default_factory=dict)
