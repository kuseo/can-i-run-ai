from __future__ import annotations

from typing import Any

from loguru import logger

from ..config.loader import OpenAIParserConfig


class OpenAIStructuredParser:
    def __init__(self, config: OpenAIParserConfig) -> None:
        self.config = config

    def parse(self, *, raw_html: str, source_url: str, schema_name: str) -> Any:
        logger.info(
            "OpenAI structured parser requested for schema={} source_url={}",
            schema_name,
            source_url,
        )
        raise NotImplementedError(
            "Live Structured Outputs integration is intentionally left as a narrow interface "
            "in this offline-capable MVP. Wire an OpenAI client here when enabling live parsing."
        )
