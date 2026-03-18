from __future__ import annotations

import json
from typing import Any

from ..schemas.base import BaseSpec
from ..schemas.cpu import CpuSpec
from ..schemas.gpu import GpuSpec
from ..schemas.model import ModelSpec
from ..schemas.score import ScoreReport


def render_catalog_list(items: list[BaseSpec], *, output: str) -> str:
    if output == "json":
        return _json(items)
    if output == "wide":
        return "\n".join(_wide_row(item) for item in items)
    return "\n".join(item.canonical_name for item in items)


def render_spec(item: BaseSpec, *, output: str) -> str:
    if output == "json":
        return _json(item)
    lines = [item.canonical_name, f"kind: {item.kind}", f"source_url: {item.source_url}"]
    for key, value in item.model_dump(exclude_none=True).items():
        if key in {"canonical_name", "kind", "source_url"}:
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def render_score_report(report: ScoreReport, *, output: str) -> str:
    if output == "json":
        return _json(report)
    if output == "wide":
        return "\n".join(
            [
                f"verdict: {report.verdict}",
                f"score: {report.score}",
                f"context: safe={report.context_estimate.safe_context_tokens} max={report.context_estimate.max_supported_context_tokens}",
                (
                    "throughput: "
                    f"decode={report.throughput_estimate.decode_tokens_per_sec} tps "
                    f"prefill={report.throughput_estimate.prefill_tokens_per_sec} tps"
                ),
                (
                    "memory: "
                    f"weights={report.wide.memory_estimate.weights_vram_gb} GB "
                    f"total_at_safe={report.wide.memory_estimate.total_vram_gb_at_safe_context} GB "
                    f"headroom={report.wide.memory_estimate.vram_headroom_gb} GB"
                ),
                (
                    "bottlenecks: "
                    f"{report.wide.bottlenecks.primary}, {report.wide.bottlenecks.secondary}"
                ),
            ]
        )
    return "\n".join(
        [
            f"verdict: {report.verdict}",
            f"score: {report.score}",
            (
                "context_estimate: "
                f"safe_context_tokens={report.context_estimate.safe_context_tokens}, "
                f"max_supported_context_tokens={report.context_estimate.max_supported_context_tokens}"
            ),
            f"decode_tokens_per_sec: {report.throughput_estimate.decode_tokens_per_sec}",
        ]
    )


def _wide_row(item: BaseSpec) -> str:
    if isinstance(item, CpuSpec):
        return f"{item.canonical_name} | {item.cores or '?'}C/{item.threads or '?'}T | {item.boost_clock_ghz or '?'} GHz boost"
    if isinstance(item, GpuSpec):
        return f"{item.canonical_name} | {item.memory_size_gib or '?'} GiB | {item.memory_bandwidth_gbs or '?'} GB/s"
    if isinstance(item, ModelSpec):
        variant = item.variant.quantization or item.variant.precision or item.variant.format or "unknown"
        return f"{item.canonical_name} | {item.num_parameters or '?'} params | {item.declared_context_tokens or '?'} ctx | {variant}"
    return item.canonical_name


def _json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json", exclude_none=True)
    else:
        payload = [item.model_dump(mode="json", exclude_none=True) for item in value]
    return json.dumps(payload, indent=2, ensure_ascii=False)
