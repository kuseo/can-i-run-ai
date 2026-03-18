from __future__ import annotations

from loguru import logger

from ..config.loader import AppConfig
from ..store.raw_cache import RawCache
from .base import CollectionResult
from .seed_catalog import cpu_seed_specs
from .wikipedia_client import WikipediaClient


class CpuWikipediaCollector:
    def __init__(self, config: AppConfig, raw_cache: RawCache) -> None:
        self.config = config
        self.raw_cache = raw_cache
        self.client = WikipediaClient(config.wikipedia)

    def collect(self) -> CollectionResult:
        if self.config.sdk.prefer_live_requests:
            try:
                for label, page in (
                    ("intel-processors", self.config.wikipedia.cpu_intel.page_url),
                    ("amd-ryzen-processors", self.config.wikipedia.cpu_amd_ryzen.page_url),
                ):
                    snapshot = self.client.fetch_page_snapshot(page)
                    self.raw_cache.write_text("wiki/cpu", label, snapshot.html, suffix=".html")
                logger.warning("Live CPU collection fetched raw pages but parser wiring is not enabled; using seed catalog.")
                return CollectionResult(
                    items=cpu_seed_specs(),
                    notes="live wikipedia fetch succeeded; offline seed parser fallback used",
                )
            except Exception as exc:
                logger.warning("CPU live collection failed, using seed fallback: {}", exc)

        return CollectionResult(items=cpu_seed_specs(), notes="offline seed fallback")
