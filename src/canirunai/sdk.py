from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from loguru import logger

from .collectors.cpu_wikipedia import CpuWikipediaCollector
from .collectors.gpu_wikipedia import GpuWikipediaCollector
from .collectors.model_huggingface import ModelHuggingFaceCollector
from .config.loader import AppConfig, load_config
from .loaders.cpu_loader import CpuLoader
from .loaders.gpu_loader import GpuLoader
from .loaders.model_loader import ModelLoader
from .scoring.engine import ScoringEngine
from .schemas.base import BaseSpec
from .schemas.cpu import CpuCatalog
from .schemas.gpu import GpuCatalog
from .schemas.model import ModelCatalog
from .schemas.score import ScoreReport
from .store.json_store import JsonStore
from .store.raw_cache import RawCache

ResourceKind = Literal["cpu", "gpu", "model"]


class CanIRunAI:
    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config: AppConfig = load_config(config_path)
        self._configure_logging()
        self.store = JsonStore(
            data_dir=self.config.sdk.data_dir,
            raw_cache_dir=self.config.sdk.raw_cache_dir,
        )
        self.raw_cache = RawCache(self.config.sdk.raw_cache_dir)
        self.cpu_loader = CpuLoader(self.store)
        self.gpu_loader = GpuLoader(self.store)
        self.model_loader = ModelLoader(self.store)
        self.scoring = ScoringEngine(self.config.scoring)

    def update_cpu(self) -> CpuCatalog:
        collector = CpuWikipediaCollector(self.config, self.raw_cache)
        result = collector.collect()
        return self.cpu_loader.upsert(result.items, result.notes)

    def update_gpu(self) -> GpuCatalog:
        collector = GpuWikipediaCollector(self.config, self.raw_cache)
        result = collector.collect()
        return self.gpu_loader.upsert(result.items, result.notes)

    def update_model(self, hf_repo_id: str | None = None) -> ModelCatalog:
        collector = ModelHuggingFaceCollector(self.config, self.raw_cache)
        result = collector.collect(hf_repo_id=hf_repo_id)
        return self.model_loader.upsert(result.items, result.notes)

    def list_specs(self, kind: ResourceKind) -> list[BaseSpec]:
        if kind == "cpu":
            return list(self.cpu_loader.list())
        if kind == "gpu":
            return list(self.gpu_loader.list())
        return list(self.model_loader.list())

    def get_spec(self, kind: ResourceKind, name: str) -> BaseSpec:
        if kind == "cpu":
            return self.cpu_loader.get(name)
        if kind == "gpu":
            return self.gpu_loader.get(name)
        return self.model_loader.get(name)

    def check(
        self,
        *,
        cpu_names: list[str],
        gpu_names: list[str],
        memory_gb: float,
        model_name: str,
    ) -> ScoreReport:
        cpus = [self.cpu_loader.get(name) for name in cpu_names]
        gpus = [self.gpu_loader.get(name) for name in gpu_names]
        model = self.model_loader.get(model_name)
        return self.scoring.score(cpus=cpus, gpus=gpus, memory_gb=memory_gb, model=model)

    def _configure_logging(self) -> None:
        logger.remove()
        logger.add(sys.__stderr__, level=self.config.sdk.log_level)
