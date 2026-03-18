from __future__ import annotations

import math

from ..config.loader import ScoringConfig
from ..gpu_compute import gpu_metric_value
from ..schemas.cpu import CpuSpec
from ..schemas.gpu import GpuSpec
from ..schemas.model import ModelSpec

GIB = 1024**3
FALLBACK_KV_PARAMETER_DIVISOR = 16_384
GPT_OSS_ACTIVE_PARAMETERS = {
    "openai/gpt-oss-20b": 3_600_000_000,
    "openai/gpt-oss-120b": 5_100_000_000,
}


class LlmEstimator:
    def __init__(self, config: ScoringConfig) -> None:
        self.config = config

    def weights_bytes(self, model: ModelSpec) -> int:
        derived_runtime_size = self._derived_runtime_weight_bytes(model)
        if derived_runtime_size is not None and self._prefer_runtime_weight_estimate(model):
            return derived_runtime_size
        if model.weights.total_size_bytes is not None:
            return model.weights.total_size_bytes
        if derived_runtime_size is not None:
            return derived_runtime_size
        if model.num_parameters is None:
            return 0
        return int(model.num_parameters * (self._parameter_bits(model) / 8))

    def kv_bytes_per_token(self, model: ModelSpec) -> int:
        if model.architecture_hint is None:
            return self._fallback_kv_bytes_per_token(model)
        layers = model.architecture_hint.num_layers or 0
        hidden_size = model.architecture_hint.hidden_size or 0
        attn_heads = model.architecture_hint.num_attention_heads or 0
        kv_heads = model.architecture_hint.num_kv_heads or attn_heads or 1
        kv_ratio = kv_heads / attn_heads if attn_heads else 1.0
        bytes_per_element = self.config.default_kv_element_bits / 8
        estimated = int(2 * layers * hidden_size * kv_ratio * bytes_per_element)
        if estimated > 0:
            return estimated
        return self._fallback_kv_bytes_per_token(model)

    def max_supported_context_tokens(self, *, model: ModelSpec, gpu: GpuSpec) -> int:
        available = int((gpu.memory_size_gib or 0) * GIB)
        weights = self.weights_bytes(model)
        runtime_overhead = int(available * self.config.overhead_ratio)
        kv_per_token = self.kv_bytes_per_token(model)
        if available <= weights + runtime_overhead:
            return 0
        if kv_per_token <= 0:
            declared = model.declared_context_tokens or 0
            if declared > 0:
                return declared
            return self.config.too_heavy_context_tokens
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

        flops = self._gpu_compute_gflops_for_model(model=model, gpu=gpu) * 1_000_000_000
        effective_parameters = self._effective_inference_parameters(model)
        if flops > 0 and effective_parameters is not None:
            flops_per_token_work = max(2 * effective_parameters, 1)
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
        if quant in {"mxfp4", "nvfp4", "fp4"} or quant.endswith("4bit"):
            return 4
        if quant in {"fp8", "nvfp8"} or quant.endswith("8bit"):
            return 8
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
        if precision == "fp8":
            return 8
        return 16

    def _fallback_kv_bytes_per_token(self, model: ModelSpec) -> int:
        effective_parameters = self._effective_inference_parameters(model)
        if effective_parameters is None:
            return 0
        return max(int(effective_parameters / FALLBACK_KV_PARAMETER_DIVISOR), 1)

    def _effective_inference_parameters(self, model: ModelSpec) -> int | None:
        hf_repo_id = model.hf_repo_id.casefold()
        if model.architecture_hint and model.architecture_hint.model_type == "gpt_oss":
            for repo_id, active_parameters in GPT_OSS_ACTIVE_PARAMETERS.items():
                if hf_repo_id == repo_id:
                    return active_parameters
        return model.num_parameters

    def _derived_runtime_weight_bytes(self, model: ModelSpec) -> int | None:
        bits = self._parameter_bits(model)
        if model.num_parameters is None or bits <= 0:
            return None
        return int(model.num_parameters * (bits / 8))

    def _prefer_runtime_weight_estimate(self, model: ModelSpec) -> bool:
        quant = (model.variant.quantization or "").lower()
        return quant in {"mxfp4", "nvfp4", "fp4"} or quant.endswith("4bit")

    def _gpu_compute_gflops_for_model(self, *, model: ModelSpec, gpu: GpuSpec) -> float:
        for metric in self._preferred_gpu_compute_metrics(model=model):
            value = gpu_metric_value(metric, gpu)
            if value:
                return float(value)
        return 0.0

    def _preferred_gpu_compute_metrics(self, *, model: ModelSpec) -> tuple[str, ...]:
        quant = (model.variant.quantization or "").lower()
        precision = (model.variant.precision or "").lower()

        if quant in {"mxfp4", "nvfp4", "fp4"} or quant.endswith("4bit") or quant.startswith("q4"):
            return (
                "processing_power_fp8_gflops",
                "processing_power_int8_gops",
                "processing_power_bf16_gflops",
                "processing_power_fp16_gflops",
                "processing_power_fp32_gflops",
            )
        if quant in {"fp8", "nvfp8"} or quant.endswith("8bit"):
            return (
                "processing_power_fp8_gflops",
                "processing_power_int8_gops",
                "processing_power_bf16_gflops",
                "processing_power_fp16_gflops",
                "processing_power_fp32_gflops",
            )
        if quant.startswith("q5") or quant.startswith("q8") or precision == "int8":
            return (
                "processing_power_int8_gops",
                "processing_power_fp8_gflops",
                "processing_power_bf16_gflops",
                "processing_power_fp16_gflops",
                "processing_power_fp32_gflops",
            )
        if precision == "bf16":
            return (
                "processing_power_bf16_gflops",
                "processing_power_fp16_gflops",
                "processing_power_fp32_gflops",
            )
        if precision in {"fp16", "float16"}:
            return (
                "processing_power_fp16_gflops",
                "processing_power_bf16_gflops",
                "processing_power_fp32_gflops",
            )
        return ("processing_power_fp32_gflops",)
