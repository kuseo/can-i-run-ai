from __future__ import annotations

from .schemas.gpu import GpuSpec


def normalize_gpu_compute_metrics(spec: GpuSpec) -> GpuSpec:
    updates: dict[str, float] = {}
    for metric in (
        "processing_power_fp16_gflops",
        "processing_power_bf16_gflops",
        "processing_power_fp8_gflops",
        "processing_power_int8_gops",
    ):
        derived = _derived_tensor_metric(metric=metric, gpu=spec)
        if derived is not None:
            updates[metric] = derived
    if not updates:
        return spec
    return spec.model_copy(update=updates)


def gpu_metric_value(metric: str, gpu: GpuSpec) -> float | None:
    derived = _derived_tensor_metric(metric=metric, gpu=gpu)
    if derived is not None:
        return derived
    value = getattr(gpu, metric)
    if value:
        return float(value)
    return None


def _derived_tensor_metric(*, metric: str, gpu: GpuSpec) -> float | None:
    if metric not in {
        "processing_power_fp16_gflops",
        "processing_power_bf16_gflops",
        "processing_power_fp8_gflops",
        "processing_power_int8_gops",
    }:
        return None
    if gpu.vendor.casefold() != "nvidia":
        return None

    fp32 = gpu.processing_power_fp32_gflops or 0.0
    if fp32 <= 0:
        return None

    current = getattr(gpu, metric)
    if current and current > fp32 * 1.05:
        return None

    tensor_multiplier = _nvidia_tensor_multiplier(gpu)
    if tensor_multiplier is None:
        return None

    if metric in {"processing_power_fp16_gflops", "processing_power_bf16_gflops"}:
        return fp32 * tensor_multiplier
    if metric == "processing_power_fp8_gflops":
        if not _has_native_fp8_support(gpu):
            return None
        return fp32 * tensor_multiplier * 2
    if metric == "processing_power_int8_gops":
        return fp32 * tensor_multiplier * 4
    return None


def _nvidia_tensor_multiplier(gpu: GpuSpec) -> float | None:
    capability = _cuda_compute_capability(gpu)
    if capability is not None:
        if capability >= 9.0:
            return 16.0
        if capability >= 8.0:
            return 4.0

    name = gpu.canonical_name.casefold()
    if any(token in name for token in ("h100", "h200", "h800", "a100", "a30")):
        return 16.0
    if any(token in name for token in ("rtx", "a10", "a40", "l4", "l40")):
        return 4.0
    return None


def _has_native_fp8_support(gpu: GpuSpec) -> bool:
    capability = _cuda_compute_capability(gpu)
    if capability is not None:
        return capability >= 8.9
    name = gpu.canonical_name.casefold()
    return any(token in name for token in ("h100", "h200", "h800", "l4", "l40", "ada"))


def _cuda_compute_capability(gpu: GpuSpec) -> float | None:
    raw = (gpu.cuda_compute_capability or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None
