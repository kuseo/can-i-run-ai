from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import Field

from ..schemas.base import StrictModel


class SourcePageConfig(StrictModel):
    page_url: str


class SdkConfig(StrictModel):
    data_dir: str = "./data"
    raw_cache_dir: str = "./data/raw_cache"
    log_level: str = "INFO"
    prefer_live_requests: bool = False
    offline_seed_fallback: bool = True


class OpenAIParserConfig(StrictModel):
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5"
    max_retries: int = 3
    timeout_sec: int = 60


class WikipediaConfig(StrictModel):
    user_agent: str = "canirunai/0.1 (contact: unknown)"
    request_delay_sec: float = 1.0
    cpu_intel: SourcePageConfig
    cpu_amd_ryzen: SourcePageConfig
    gpu_nvidia: SourcePageConfig
    gpu_amd: SourcePageConfig


class HuggingFaceConfig(StrictModel):
    endpoint: str = "https://huggingface.co"
    request_delay_sec: float = 0.2
    max_models_total: int = 2000
    max_models_per_team: int = 200
    pipeline_tag: str = "text-generation"
    license_id: str = "apache-2.0"
    inference_provider: str = "all"
    num_parameters: str = "min:0.3B,max:200B"
    teams: list[str] = Field(default_factory=list)


class ScoringConfig(StrictModel):
    overhead_ratio: float = 0.08
    safe_context_ratio: float = 0.85
    min_context_tokens: int = 2048
    too_heavy_context_tokens: int = 4096
    tight_fit_headroom_ratio: float = 0.10
    min_decode_tps: float = 5.0
    good_decode_tps: float = 20.0
    great_decode_tps: float = 40.0
    great_context_tokens: int = 16384
    eff_bw: float = 0.72
    eff_flops: float = 0.45
    stream_reuse_factor: float = 0.8
    prefill_multiplier: float = 24.0
    default_kv_element_bits: int = 16
    host_ram_weight_fraction: float = 0.35
    cpu_threads_per_replica: int = 8


class AppConfig(StrictModel):
    sdk: SdkConfig
    openai_parser: OpenAIParserConfig
    wikipedia: WikipediaConfig
    huggingface: HuggingFaceConfig
    scoring: ScoringConfig


def load_config(path: str | Path | None = None) -> AppConfig:
    default_path = Path(__file__).with_name("default_config.toml")
    base = tomllib.loads(default_path.read_text(encoding="utf-8"))
    if path is not None:
        custom = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        base = _deep_merge(base, custom)
    resolved = _resolve_env_tokens(base)
    return AppConfig.model_validate(resolved)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def _resolve_env_tokens(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_env_tokens(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env_tokens(item) for item in value]
    if isinstance(value, str) and value.startswith("ENV:"):
        return os.getenv(value[4:], "")
    return value
