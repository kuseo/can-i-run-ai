from __future__ import annotations

from ..parsers.normalization import lookup_key
from ..schemas.base import CollectionSource
from ..schemas.gpu import GpuCatalog, GpuSpec
from ..store.json_store import JsonStore


class GpuLoader:
    def __init__(self, store: JsonStore) -> None:
        self.store = store

    def load(self) -> GpuCatalog:
        return self.store.load_gpu_catalog()

    def list(self) -> list[GpuSpec]:
        return self.load().items

    def get(self, name: str) -> GpuSpec:
        key = lookup_key(name)
        for item in self.list():
            if key == lookup_key(item.canonical_name):
                return item
            if any(key == lookup_key(alias) for alias in item.aliases):
                return item
        raise KeyError(f"Unknown GPU: {name}")

    def upsert(self, items: list[GpuSpec], notes: str) -> GpuCatalog:
        current = self.load()
        merged = self.store.merge_items(current.items, items)
        catalog = GpuCatalog(
            source=CollectionSource(collector="canirunai.collectors.gpu_wikipedia", notes=notes),
            items=merged,
        )
        self.store.save_gpu_catalog(catalog)
        return catalog
