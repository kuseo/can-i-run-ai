from __future__ import annotations

from ..parsers.normalization import lookup_key
from ..schemas.base import CollectionSource
from ..schemas.cpu import CpuCatalog, CpuSpec
from ..store.json_store import JsonStore


class CpuLoader:
    def __init__(self, store: JsonStore) -> None:
        self.store = store

    def load(self) -> CpuCatalog:
        return self.store.load_cpu_catalog()

    def list(self) -> list[CpuSpec]:
        return self.load().items

    def get(self, name: str) -> CpuSpec:
        key = lookup_key(name)
        for item in self.list():
            if key == lookup_key(item.canonical_name):
                return item
            if any(key == lookup_key(alias) for alias in item.aliases):
                return item
        raise KeyError(f"Unknown CPU: {name}")

    def upsert(self, items: list[CpuSpec], notes: str) -> CpuCatalog:
        current = self.load()
        merged = self.store.merge_items(current.items, items)
        catalog = CpuCatalog(
            source=CollectionSource(collector="canirunai.collectors.cpu_wikipedia", notes=notes),
            items=merged,
        )
        self.store.save_cpu_catalog(catalog)
        return catalog
