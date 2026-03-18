from __future__ import annotations

from typing import Literal

from .base import StrictModel

Verdict = Literal["RUNS GREAT", "RUNS WELL", "TIGHT FIT", "TOO HEAVY", "IMPOSSIBLE"]


class ScoreInputs(StrictModel):
    cpu: list[str]
    gpu: list[str]
    memory_gb: float
    model: str


class PlacementEstimate(StrictModel):
    mode: str
    single_gpu_loadable: bool
    replica_count: int
    used_gpu_canonical_names: list[str]


class ContextEstimate(StrictModel):
    max_supported_context_tokens: int
    safe_context_tokens: int


class ThroughputEstimate(StrictModel):
    decode_tokens_per_sec: float
    prefill_tokens_per_sec: float


class MemoryEstimate(StrictModel):
    weights_vram_gb: float
    runtime_overhead_vram_gb: float
    kv_cache_gb_per_1k_tokens: float
    total_vram_gb_at_safe_context: float
    vram_headroom_gb: float
    host_ram_required_gb: float
    host_ram_headroom_gb: float


class LatencyEstimate(StrictModel):
    first_token_ms_per_1k_prompt_tokens: int
    generation_ms_per_128_output_tokens: int


class Bottlenecks(StrictModel):
    primary: str
    secondary: str


class ConfidenceEstimate(StrictModel):
    context: Literal["low", "medium", "high"]
    throughput: Literal["low", "medium", "high"]


class WideEstimate(StrictModel):
    memory_estimate: MemoryEstimate
    latency_estimate: LatencyEstimate
    bottlenecks: Bottlenecks
    confidence: ConfidenceEstimate


class ScoreReport(StrictModel):
    schema_version: int = 1
    verdict: Verdict
    score: int
    inputs: ScoreInputs
    placement_estimate: PlacementEstimate
    context_estimate: ContextEstimate
    throughput_estimate: ThroughputEstimate
    wide: WideEstimate
