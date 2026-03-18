from __future__ import annotations

import math

from ..config.loader import ScoringConfig
from ..schemas.score import Verdict


def determine_verdict(
    *,
    single_gpu_loadable: bool,
    safe_context_tokens: int,
    decode_tokens_per_sec: float,
    vram_headroom_ratio: float,
    host_ram_headroom_gb: float,
    config: ScoringConfig,
) -> Verdict:
    if not single_gpu_loadable or safe_context_tokens <= 0:
        return "IMPOSSIBLE"
    if safe_context_tokens < config.min_context_tokens or decode_tokens_per_sec < config.min_decode_tps:
        return "TOO HEAVY"
    great_context_threshold = max(
        config.too_heavy_context_tokens,
        math.floor(config.great_context_tokens * config.safe_context_ratio),
    )
    comfortable_context_threshold = max(
        config.min_context_tokens,
        config.min_context_tokens + config.too_heavy_context_tokens,
    )
    tight_resources = vram_headroom_ratio < config.tight_fit_headroom_ratio or host_ram_headroom_gb < 0

    if safe_context_tokens >= great_context_threshold and decode_tokens_per_sec >= config.great_decode_tps:
        if tight_resources:
            return "RUNS WELL"
        return "RUNS GREAT"

    if tight_resources:
        if host_ram_headroom_gb >= 0 and safe_context_tokens >= comfortable_context_threshold and decode_tokens_per_sec >= config.good_decode_tps:
            return "RUNS WELL"
        return "TIGHT FIT"
    return "RUNS WELL"
