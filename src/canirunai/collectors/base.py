from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar


ItemT = TypeVar("ItemT")


@dataclass(slots=True)
class CollectionResult(Generic[ItemT]):
    items: list[ItemT]
    notes: str
