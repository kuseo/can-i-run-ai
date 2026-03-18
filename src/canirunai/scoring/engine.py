from __future__ import annotations

from ..config.loader import ScoringConfig
from ..schemas.cpu import CpuSpec
from ..schemas.gpu import GpuSpec
from ..schemas.model import ModelSpec
from ..schemas.score import (
    Bottlenecks,
    ConfidenceEstimate,
    ContextEstimate,
    LatencyEstimate,
    MemoryEstimate,
    PlacementEstimate,
    ScoreInputs,
    ScoreReport,
    ThroughputEstimate,
    WideEstimate,
)
from .llm_estimator import GIB, LlmEstimator
from .verdict import determine_verdict


class ScoringEngine:
    def __init__(self, config: ScoringConfig) -> None:
        self.config = config
        self.estimator = LlmEstimator(config)

    def score(self, *, cpus: list[CpuSpec], gpus: list[GpuSpec], memory_gb: float, model: ModelSpec) -> ScoreReport:
        replica_count = self.estimator.replica_count(model=model, gpus=gpus)
        loadable_gpus = [gpu for gpu in gpus if self.estimator.max_supported_context_tokens(model=model, gpu=gpu) > 0]
        single_gpu_loadable = bool(loadable_gpus)

        if loadable_gpus:
            primary_gpu = min(loadable_gpus, key=lambda gpu: gpu.memory_size_gib or 0.0)
            max_context_tokens = self.estimator.max_supported_context_tokens(model=model, gpu=primary_gpu)
        else:
            primary_gpu = gpus[0]
            max_context_tokens = 0

        safe_context_tokens = self.estimator.safe_context_tokens(
            max_context_tokens=max_context_tokens,
            model=model,
        )
        decode_tps = self.estimator.total_decode_tps(
            model=model,
            gpus=loadable_gpus or gpus,
            cpus=cpus,
            replica_count=replica_count,
        )
        prefill_tps = self.estimator.prefill_tps(decode_tps)

        available_vram_gb = primary_gpu.memory_size_gib or 0.0
        weights_vram_gb = self.estimator.weights_bytes(model) / GIB
        runtime_overhead_vram_gb = available_vram_gb * self.config.overhead_ratio
        kv_cache_gb_per_1k = self.estimator.kv_bytes_per_token(model) * 1000 / GIB
        total_vram_at_safe = weights_vram_gb + runtime_overhead_vram_gb + (kv_cache_gb_per_1k * safe_context_tokens / 1000)
        vram_headroom_gb = available_vram_gb - total_vram_at_safe
        vram_headroom_ratio = 0.0 if available_vram_gb <= 0 else max(vram_headroom_gb, 0.0) / available_vram_gb

        host_ram_required_gb = self.estimator.host_ram_required_gb(model)
        host_ram_headroom_gb = memory_gb - host_ram_required_gb

        verdict = determine_verdict(
            single_gpu_loadable=single_gpu_loadable,
            safe_context_tokens=safe_context_tokens,
            decode_tokens_per_sec=decode_tps,
            vram_headroom_gb=vram_headroom_gb,
            vram_headroom_ratio=vram_headroom_ratio,
            host_ram_headroom_gb=host_ram_headroom_gb,
            config=self.config,
        )
        score = _compute_score(
            safe_context_tokens=safe_context_tokens,
            declared_context_tokens=model.declared_context_tokens or max_context_tokens or 1,
            decode_tps=decode_tps,
            vram_headroom_ratio=vram_headroom_ratio,
            host_ram_headroom_gb=host_ram_headroom_gb,
            verdict=verdict,
            config=self.config,
        )

        primary_bottleneck = "gpu_vram"
        if single_gpu_loadable and decode_tps >= self.config.min_decode_tps:
            if host_ram_headroom_gb < 0:
                primary_bottleneck = "system_ram"
            elif primary_gpu.memory_bandwidth_gbs:
                primary_bottleneck = "gpu_bandwidth"
            else:
                primary_bottleneck = "gpu_compute"
        secondary_bottleneck = "cpu_threads" if sum((cpu.threads or cpu.cores or 0) for cpu in cpus) < replica_count * self.config.cpu_threads_per_replica else "gpu_compute"

        confidence = ConfidenceEstimate(
            context="high" if model.architecture_hint and primary_gpu.memory_size_gib else "medium",
            throughput="medium" if primary_gpu.memory_bandwidth_gbs else "low",
        )

        first_token_ms = int(round(1_000_000 / prefill_tps)) if prefill_tps > 0 else 0
        generation_ms = int(round((128 / decode_tps) * 1000)) if decode_tps > 0 else 0

        return ScoreReport(
            verdict=verdict,
            score=score,
            inputs=ScoreInputs(
                cpu=[cpu.canonical_name for cpu in cpus],
                gpu=[gpu.canonical_name for gpu in gpus],
                memory_gb=memory_gb,
                model=model.canonical_name,
            ),
            placement_estimate=PlacementEstimate(
                mode="replicated_serving",
                single_gpu_loadable=single_gpu_loadable,
                replica_count=replica_count,
                used_gpu_canonical_names=[gpu.canonical_name for gpu in loadable_gpus[:replica_count]],
            ),
            context_estimate=ContextEstimate(
                max_supported_context_tokens=max_context_tokens,
                safe_context_tokens=safe_context_tokens,
            ),
            throughput_estimate=ThroughputEstimate(
                decode_tokens_per_sec=round(decode_tps, 2),
                prefill_tokens_per_sec=round(prefill_tps, 2),
            ),
            wide=WideEstimate(
                memory_estimate=MemoryEstimate(
                    weights_vram_gb=round(weights_vram_gb, 2),
                    runtime_overhead_vram_gb=round(runtime_overhead_vram_gb, 2),
                    kv_cache_gb_per_1k_tokens=round(kv_cache_gb_per_1k, 4),
                    total_vram_gb_at_safe_context=round(total_vram_at_safe, 2),
                    vram_headroom_gb=round(vram_headroom_gb, 2),
                    host_ram_required_gb=round(host_ram_required_gb, 2),
                    host_ram_headroom_gb=round(host_ram_headroom_gb, 2),
                ),
                latency_estimate=LatencyEstimate(
                    first_token_ms_per_1k_prompt_tokens=first_token_ms,
                    generation_ms_per_128_output_tokens=generation_ms,
                ),
                bottlenecks=Bottlenecks(primary=primary_bottleneck, secondary=secondary_bottleneck),
                confidence=confidence,
            ),
        )


def _compute_score(
    *,
    safe_context_tokens: int,
    declared_context_tokens: int,
    decode_tps: float,
    vram_headroom_ratio: float,
    host_ram_headroom_gb: float,
    verdict: str,
    config: ScoringConfig,
) -> int:
    context_ratio = min(safe_context_tokens / max(declared_context_tokens, 1), 1.0)
    speed_ratio = min(decode_tps / max(config.good_decode_tps, 1.0), 1.0)
    headroom_ratio = max(0.0, min(vram_headroom_ratio / 0.25, 1.0))
    ram_ratio = 1.0 if host_ram_headroom_gb >= 0 else max(0.0, 1.0 + (host_ram_headroom_gb / 16.0))
    raw_score = int(round((context_ratio * 0.4 + speed_ratio * 0.35 + headroom_ratio * 0.15 + ram_ratio * 0.10) * 100))

    if verdict == "IMPOSSIBLE":
        return min(raw_score, 15)
    if verdict == "TOO HEAVY":
        return min(max(raw_score, 16), 39)
    if verdict == "TIGHT FIT":
        return min(max(raw_score, 40), 59)
    if verdict == "RUNS WELL":
        return min(max(raw_score, 60), 84)
    return max(raw_score, 85)
