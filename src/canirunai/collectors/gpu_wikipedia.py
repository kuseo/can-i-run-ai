from __future__ import annotations

from loguru import logger

from ..config.loader import AppConfig
from ..store.raw_cache import RawCache
from .base import CollectionResult
from .seed_catalog import gpu_seed_specs
from .wikipedia_client import WikipediaClient


class GpuWikipediaCollector:
    def __init__(self, config: AppConfig, raw_cache: RawCache) -> None:
        self.config = config
        self.raw_cache = raw_cache
        self.client = WikipediaClient(config.wikipedia)

    def collect(self) -> CollectionResult:
        if self.config.sdk.prefer_live_requests:
            try:
                for label, page in (
                    ("nvidia-gpus", self.config.wikipedia.gpu_nvidia.page_url),
                    ("amd-gpus", self.config.wikipedia.gpu_amd.page_url),
                ):
                    snapshot = self.client.fetch_page_snapshot(page)
                    self.raw_cache.write_text("wiki/gpu", label, snapshot.html, suffix=".html")
                logger.warning("Live GPU collection fetched raw pages but parser wiring is not enabled; using seed catalog.")
                return CollectionResult(
                    items=gpu_seed_specs(),
                    notes="live wikipedia fetch succeeded; offline seed parser fallback used",
                )
            except Exception as exc:
                logger.warning("GPU live collection failed, using seed fallback: {}", exc)

        return CollectionResult(items=gpu_seed_specs(), notes="offline seed fallback")
