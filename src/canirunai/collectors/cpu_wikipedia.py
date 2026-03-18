from __future__ import annotations

from loguru import logger

from ..config.loader import AppConfig
from ..store.raw_cache import RawCache
from .base import CollectionResult
from .seed_catalog import cpu_seed_specs
from .wikipedia_live_parser import parse_cpu_specs_from_snapshot
from .wikipedia_client import WikipediaClient


class CpuWikipediaCollector:
    def __init__(self, config: AppConfig, raw_cache: RawCache, *, verbose: bool = False) -> None:
        self.config = config
        self.raw_cache = raw_cache
        self.client = WikipediaClient(config.wikipedia, verbose=verbose)

    def collect(self) -> CollectionResult:
        if self.config.sdk.prefer_live_requests:
            try:
                items = []
                for cache_label, page_url, vendor in (
                    ("intel-processors", self.config.wikipedia.cpu_intel.page_url, "intel"),
                    ("amd-ryzen-processors", self.config.wikipedia.cpu_amd_ryzen.page_url, "amd"),
                ):
                    snapshot = self.client.fetch_page_snapshot(page_url)
                    cache_key = self.raw_cache.write_text("wiki/cpu", cache_label, snapshot.html, suffix=".html")
                    items.extend(
                        parse_cpu_specs_from_snapshot(
                            snapshot,
                            vendor=vendor,
                            cache_key=cache_key,
                        )
                    )
                if items:
                    logger.info("Collected {} CPU specs from live Wikipedia pages.", len(items))
                    return CollectionResult(items=items, notes="live wikipedia collection")
                raise RuntimeError("Live CPU collection produced no specs.")
            except Exception as exc:
                if not self.config.sdk.offline_seed_fallback:
                    raise
                logger.warning("CPU live collection failed, using seed fallback: {}", exc)

        if self.config.sdk.offline_seed_fallback:
            return CollectionResult(items=cpu_seed_specs(), notes="offline seed fallback")
        raise RuntimeError("CPU collection failed and offline seed fallback is disabled.")
