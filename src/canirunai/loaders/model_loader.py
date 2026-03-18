from __future__ import annotations

from ..parsers.normalization import lookup_key
from ..schemas.base import CollectionSource
from ..schemas.model import ModelCatalog, ModelSpec
from ..store.json_store import JsonStore


class ModelLoader:
    def __init__(self, store: JsonStore) -> None:
        self.store = store

    def load(self) -> ModelCatalog:
        return self.store.load_model_catalog()

    def list(self) -> list[ModelSpec]:
        return self.load().items

    def get(self, name: str) -> ModelSpec:
        key = lookup_key(name)
        for item in self.list():
            if key == lookup_key(item.canonical_name):
                return item
            if key == lookup_key(item.hf_repo_id):
                return item
            if any(key == lookup_key(alias) for alias in item.aliases):
                return item
        raise KeyError(f"Unknown model: {name}")

    def upsert(self, items: list[ModelSpec], notes: str) -> ModelCatalog:
        current = self.load()
        merged = self.store.merge_items(current.items, items)
        catalog = ModelCatalog(
            source=CollectionSource(collector="canirunai.collectors.model_huggingface", notes=notes),
            items=merged,
        )
        self.store.save_model_catalog(catalog)
        return catalog
