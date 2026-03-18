from __future__ import annotations

import json
from typing import Any

from loguru import logger

from ..config.loader import AppConfig
from ..schemas.base import RawReference
from ..schemas.model import ArchitectureHint, InferenceInfo, ModelSpec, PopularityInfo, VariantSpec, WeightFile, WeightsInfo
from ..store.raw_cache import RawCache
from .base import CollectionResult
from .huggingface_client import HuggingFaceClient
from .seed_catalog import model_seed_specs


class ModelHuggingFaceCollector:
    def __init__(self, config: AppConfig, raw_cache: RawCache) -> None:
        self.config = config
        self.raw_cache = raw_cache
        self.client = HuggingFaceClient(config.huggingface)

    def collect(self, *, hf_repo_id: str | None = None) -> CollectionResult:
        if self.config.sdk.prefer_live_requests and hf_repo_id:
            try:
                payload = self.client.model_info(hf_repo_id)
                spec = self._spec_from_payload(payload)
                self.raw_cache.write_text("huggingface/model", hf_repo_id, json.dumps(payload, indent=2), suffix=".json")
                return CollectionResult(items=[spec], notes=f"live Hugging Face update for {hf_repo_id}")
            except Exception as exc:
                logger.warning("Model live collection failed for {}: {}", hf_repo_id, exc)

        items = model_seed_specs(hf_repo_id)
        note = "offline seed fallback"
        if hf_repo_id and not items:
            raise KeyError(f"Seed catalog does not contain model {hf_repo_id}")
        return CollectionResult(items=items, notes=note)

    def _spec_from_payload(self, payload: dict[str, Any]) -> ModelSpec:
        config = payload.get("config") or {}
        siblings = payload.get("siblings") or []
        weight_files = [
            WeightFile(path=item["rfilename"], size_bytes=int(item["size"]))
            for item in siblings
            if item.get("rfilename") and item.get("size") is not None
        ]
        total_size_bytes = sum(item.size_bytes for item in weight_files) or None
        card_data = payload.get("cardData") or payload.get("card_data") or {}
        variant = VariantSpec(
            precision=_infer_precision(payload),
            quantization=_infer_quantization(payload),
            format=_infer_format(weight_files),
        )
        arch = ArchitectureHint(
            model_type=config.get("model_type"),
            num_layers=config.get("num_hidden_layers") or config.get("n_layer"),
            hidden_size=config.get("hidden_size") or config.get("n_embd"),
            num_attention_heads=config.get("num_attention_heads") or config.get("n_head"),
            num_kv_heads=config.get("num_key_value_heads"),
            vocab_size=config.get("vocab_size"),
        )
        status = None
        if payload.get("inference") is not None:
            status = "warm"
        aliases = [payload["id"]] if payload.get("id") else []
        return ModelSpec(
            canonical_name=_build_canonical_name(payload["id"], variant),
            aliases=aliases,
            source_url=f"{self.config.huggingface.endpoint}/{payload['id']}",
            source_sha=payload.get("sha"),
            raw_ref=RawReference(cache_key=f"data/raw_cache/huggingface/model/{payload['id']}.json"),
            hf_repo_id=payload["id"],
            variant=variant,
            task=payload.get("pipeline_tag") or self.config.huggingface.pipeline_tag,
            license_id=card_data.get("license"),
            inference=InferenceInfo(provider_required=True, status=status),
            declared_context_tokens=_infer_declared_context(config, card_data),
            architecture_hint=arch,
            num_parameters=_infer_num_parameters(payload, card_data),
            weights=WeightsInfo(total_size_bytes=total_size_bytes, files=weight_files),
            popularity=PopularityInfo(
                downloads_30d=payload.get("downloads"),
                likes=payload.get("likes"),
            ),
        )


def _infer_precision(payload: dict[str, Any]) -> str | None:
    tags = [tag.lower() for tag in payload.get("tags", [])]
    for candidate in ("bf16", "fp16", "fp32", "int8"):
        if candidate in tags:
            return candidate
    return None


def _infer_quantization(payload: dict[str, Any]) -> str | None:
    tags = [tag.lower() for tag in payload.get("tags", [])]
    for tag in tags:
        if tag.startswith("gptq") or tag.startswith("awq") or tag.startswith("gguf") or tag.startswith("q"):
            return tag
    return None


def _infer_format(weight_files: list[WeightFile]) -> str | None:
    for candidate in ("gguf", "safetensors", "bin"):
        if any(file.path.endswith(f".{candidate}") for file in weight_files):
            return candidate
    return None


def _infer_declared_context(config: dict[str, Any], card_data: dict[str, Any]) -> int | None:
    for key in ("max_position_embeddings", "n_positions", "seq_length"):
        value = config.get(key)
        if isinstance(value, int):
            return value
    for key in ("context_length", "max_position_embeddings"):
        value = card_data.get(key)
        if isinstance(value, int):
            return value
    return None


def _infer_num_parameters(payload: dict[str, Any], card_data: dict[str, Any]) -> int | None:
    candidates = [
        payload.get("num_parameters"),
        card_data.get("num_parameters"),
        (payload.get("config") or {}).get("num_parameters"),
    ]
    for value in candidates:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            parsed = _parse_hf_parameter_string(value)
            if parsed is not None:
                return parsed
    return None


def _parse_hf_parameter_string(value: str) -> int | None:
    cleaned = value.strip().lower().replace(",", "")
    if cleaned.endswith("b"):
        try:
            return int(float(cleaned[:-1]) * 1_000_000_000)
        except ValueError:
            return None
    if cleaned.endswith("m"):
        try:
            return int(float(cleaned[:-1]) * 1_000_000)
        except ValueError:
            return None
    if cleaned.isdigit():
        return int(cleaned)
    return None


def _build_canonical_name(repo_id: str, variant: VariantSpec) -> str:
    suffix = variant.quantization or variant.precision or variant.format or "unknown"
    return f"{repo_id}@{suffix}"
