from __future__ import annotations

import math

from ..config.loader import ScoringConfig
from ..schemas.cpu import CpuSpec
from ..schemas.gpu import GpuSpec
from ..schemas.model import ModelSpec

GIB = 1024**3


class LlmEstimator:
    def __init__(self, config: ScoringConfig) -> None:
        self.config = config

    def weights_bytes(self, model: ModelSpec) -> int:
        if model.weights.total_size_bytes is not None:
            return model.weights.total_size_bytes
        if model.num_parameters is None:
            return 0
        return int(model.num_parameters * (self._parameter_bits(model) / 8))

    def kv_bytes_per_token(self, model: ModelSpec) -> int:
        if model.architecture_hint is None:
            return 0
        layers = model.architecture_hint.num_layers or 0
        hidden_size = model.architecture_hint.hidden_size or 0
        attn_heads = model.architecture_hint.num_attention_heads or 0
        kv_heads = model.architecture_hint.num_kv_heads or attn_heads or 1
        kv_ratio = kv_heads / attn_heads if attn_heads else 1.0
        bytes_per_element = self.config.default_kv_element_bits / 8
        return int(2 * layers * hidden_size * kv_ratio * bytes_per_element)

    def max_supported_context_tokens(self, *, model: ModelSpec, gpu: GpuSpec) -> int:
        available = int((gpu.memory_size_gib or 0) * GIB)
        weights = self.weights_bytes(model)
        runtime_overhead = int(available * self.config.overhead_ratio)
        kv_per_token = self.kv_bytes_per_token(model)
        if available <= weights + runtime_overhead:
            return 0
        if kv_per_token <= 0:
            declared = model.declared_context_tokens or 0
            return declared
        return max(0, (available - weights - runtime_overhead) // kv_per_token)

    def safe_context_tokens(self, *, max_context_tokens: int, model: ModelSpec) -> int:
        declared = model.declared_context_tokens or max_context_tokens
        return min(declared, math.floor(max_context_tokens * self.config.safe_context_ratio))

    def single_gpu_decode_tps(self, *, model: ModelSpec, gpu: GpuSpec) -> float:
        weights_bytes = self.weights_bytes(model)
        if not weights_bytes:
            return 0.0
        bandwidth = (gpu.memory_bandwidth_gbs or 0.0) * 1_000_000_000
        if bandwidth <= 0:
            return 0.0
        bytes_per_token_work = max(weights_bytes * self.config.stream_reuse_factor, 1.0)
        tps_bw = bandwidth * self.config.eff_bw / bytes_per_token_work

        flops = (gpu.processing_power_fp32_gflops or 0.0) * 1_000_000_000
        if flops > 0 and model.num_parameters:
            flops_per_token_work = max(2 * model.num_parameters, 1)
            tps_flops = flops * self.config.eff_flops / flops_per_token_work
            return min(tps_bw, tps_flops)
        return tps_bw

    def total_decode_tps(self, *, model: ModelSpec, gpus: list[GpuSpec], cpus: list[CpuSpec], replica_count: int) -> float:
        if replica_count == 0 or not gpus:
            return 0.0
        loadable_gpus = [gpu for gpu in gpus if self.max_supported_context_tokens(model=model, gpu=gpu) > 0]
        if not loadable_gpus:
            return 0.0
        single = self.single_gpu_decode_tps(model=model, gpu=loadable_gpus[0])
        total_threads = sum((cpu.threads or cpu.cores or 0) for cpu in cpus)
        cpu_cap_ratio = 1.0
        if total_threads:
            cpu_cap_ratio = min(1.0, total_threads / max(replica_count * self.config.cpu_threads_per_replica, 1))
        return single * replica_count * cpu_cap_ratio

    def prefill_tps(self, decode_tps: float) -> float:
        return decode_tps * self.config.prefill_multiplier

    def replica_count(self, *, model: ModelSpec, gpus: list[GpuSpec]) -> int:
        return sum(1 for gpu in gpus if self.max_supported_context_tokens(model=model, gpu=gpu) > 0)

    def host_ram_required_gb(self, model: ModelSpec) -> float:
        weights_gb = self.weights_bytes(model) / GIB
        return max(8.0, weights_gb * self.config.host_ram_weight_fraction + 4.0)

    def _parameter_bits(self, model: ModelSpec) -> int:
        quant = (model.variant.quantization or "").lower()
        precision = (model.variant.precision or "").lower()
        if quant.startswith("q4"):
            return 4
        if quant.startswith("q5"):
            return 5
        if quant.startswith("q8"):
            return 8
        if precision in {"fp32", "float32"}:
            return 32
        if precision in {"bf16", "fp16", "float16"}:
            return 16
        if precision == "int8":
            return 8
        return 16
