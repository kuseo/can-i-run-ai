from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from ..parsers.normalization import lookup_key
from ..schemas.base import CollectionSource
from ..schemas.cpu import CpuCatalog, CpuSpec
from ..schemas.gpu import GpuCatalog, GpuSpec
from ..schemas.model import ModelCatalog, ModelSpec

ItemT = TypeVar("ItemT", CpuSpec, GpuSpec, ModelSpec)
CatalogT = TypeVar("CatalogT", CpuCatalog, GpuCatalog, ModelCatalog)


class JsonStore:
    def __init__(self, data_dir: str | Path, raw_cache_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.specs_dir = self.data_dir / "specs"
        self.specs_dir.mkdir(parents=True, exist_ok=True)
        self.raw_cache_dir = Path(raw_cache_dir)
        self.raw_cache_dir.mkdir(parents=True, exist_ok=True)

    def load_cpu_catalog(self) -> CpuCatalog:
        return self._load_catalog(
            self.specs_dir / "cpu.json",
            CpuCatalog,
            collector="canirunai.collectors.cpu_wikipedia",
        )

    def load_gpu_catalog(self) -> GpuCatalog:
        return self._load_catalog(
            self.specs_dir / "gpu.json",
            GpuCatalog,
            collector="canirunai.collectors.gpu_wikipedia",
        )

    def load_model_catalog(self) -> ModelCatalog:
        return self._load_catalog(
            self.specs_dir / "model.json",
            ModelCatalog,
            collector="canirunai.collectors.model_huggingface",
        )

    def save_cpu_catalog(self, catalog: CpuCatalog) -> None:
        self._save_catalog(self.specs_dir / "cpu.json", catalog)

    def save_gpu_catalog(self, catalog: GpuCatalog) -> None:
        self._save_catalog(self.specs_dir / "gpu.json", catalog)

    def save_model_catalog(self, catalog: ModelCatalog) -> None:
        self._save_catalog(self.specs_dir / "model.json", catalog)

    def merge_items(self, existing: list[ItemT], fresh: list[ItemT]) -> list[ItemT]:
        merged: dict[str, ItemT] = {lookup_key(item.canonical_name): item for item in existing}
        for item in fresh:
            merged[lookup_key(item.canonical_name)] = item
        return sorted(merged.values(), key=lambda item: item.canonical_name.casefold())

    def _load_catalog(self, path: Path, model: type[CatalogT], *, collector: str) -> CatalogT:
        if not path.exists():
            return model(source=CollectionSource(collector=collector, notes="empty catalog"))
        data = json.loads(path.read_text(encoding="utf-8"))
        return model.model_validate(data)

    def _save_catalog(self, path: Path, catalog: BaseModel) -> None:
        payload = json.dumps(catalog.model_dump(mode="json", exclude_none=True), indent=2, ensure_ascii=False)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(payload + "\n", encoding="utf-8")
        tmp_path.replace(path)
