from __future__ import annotations

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
    if not single_gpu_loadable or safe_context_tokens < config.min_context_tokens:
        return "IMPOSSIBLE"
    if safe_context_tokens < config.too_heavy_context_tokens or decode_tokens_per_sec < config.min_decode_tps:
        return "TOO HEAVY"
    if vram_headroom_ratio < config.tight_fit_headroom_ratio or host_ram_headroom_gb < 0:
        return "TIGHT FIT"
    if safe_context_tokens >= config.great_context_tokens and decode_tokens_per_sec >= config.great_decode_tps:
        return "RUNS GREAT"
    return "RUNS WELL"
