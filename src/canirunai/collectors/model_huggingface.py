from __future__ import annotations

import json
import re
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
    def __init__(self, config: AppConfig, raw_cache: RawCache, *, verbose: bool = False) -> None:
        self.config = config
        self.raw_cache = raw_cache
        self.client = HuggingFaceClient(config.huggingface, verbose=verbose)

    def collect(self, *, hf_repo_id: str | None = None) -> CollectionResult:
        if self.config.sdk.prefer_live_requests:
            try:
                if hf_repo_id:
                    payload = self.client.model_info(hf_repo_id)
                    specs = self._specs_from_payload(payload)
                    self.raw_cache.write_text("huggingface/model", hf_repo_id, json.dumps(payload, indent=2), suffix=".json")
                    return CollectionResult(items=specs, notes=f"live Hugging Face update for {hf_repo_id}")

                items = self._collect_live_catalog()
                if items:
                    return CollectionResult(items=items, notes="live Hugging Face collection")
                raise RuntimeError("Live Hugging Face collection produced no specs.")
            except Exception as exc:
                if not self.config.sdk.offline_seed_fallback:
                    raise
                logger.warning("Model live collection failed for {}: {}", hf_repo_id or "catalog", exc)

        if self.config.sdk.offline_seed_fallback:
            items = model_seed_specs(hf_repo_id)
            if hf_repo_id and not items:
                raise KeyError(f"Seed catalog does not contain model {hf_repo_id}")
            return CollectionResult(items=items, notes="offline seed fallback")
        raise RuntimeError("Model collection failed and offline seed fallback is disabled.")

    def _collect_live_catalog(self) -> list[ModelSpec]:
        repo_ids: list[str] = []
        for team in self.config.huggingface.teams:
            for entry in self.client.list_models(author=team, limit=self.config.huggingface.max_models_per_team):
                repo_id = entry.get("id") or entry.get("modelId")
                if repo_id:
                    repo_ids.append(repo_id)

        unique_repo_ids = _dedupe_preserving_order(repo_ids)[: self.config.huggingface.max_models_total]
        specs: dict[str, ModelSpec] = {}
        for repo_id in unique_repo_ids:
            try:
                payload = self.client.model_info(repo_id)
                repo_specs = self._specs_from_payload(payload)
                repo_specs = [spec for spec in repo_specs if self._should_keep_spec(spec)]
                if not repo_specs:
                    continue
                self.raw_cache.write_text("huggingface/model", repo_id, json.dumps(payload, indent=2), suffix=".json")
                for spec in repo_specs:
                    specs[spec.canonical_name] = spec
            except Exception as exc:
                logger.warning("Skipping live Hugging Face model {}: {}", repo_id, exc)
        logger.info("Collected {} model specs from live Hugging Face catalog.", len(specs))
        return sorted(specs.values(), key=lambda item: item.canonical_name.casefold())

    def _should_keep_spec(self, spec: ModelSpec) -> bool:
        if self.config.huggingface.pipeline_tag and spec.task != self.config.huggingface.pipeline_tag:
            return False
        if self.config.huggingface.license_id and spec.license_id and spec.license_id != self.config.huggingface.license_id:
            return False
        return True

    def _specs_from_payload(self, payload: dict[str, Any]) -> list[ModelSpec]:
        config = payload.get("config") or {}
        siblings = payload.get("siblings") or []
        card_data = payload.get("cardData") or payload.get("card_data") or {}
        num_parameters = _infer_num_parameters(payload, card_data)
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
        source_url = f"{self.config.huggingface.endpoint}/{payload['id']}"
        raw_ref = RawReference(cache_key=f"data/raw_cache/huggingface/model/{payload['id']}.json")
        task = payload.get("pipeline_tag") or card_data.get("pipeline_tag") or self.config.huggingface.pipeline_tag
        license_id = _infer_license_id(payload, card_data)
        declared_context_tokens = _infer_declared_context(payload, config, card_data)
        popularity = PopularityInfo(
            downloads_30d=payload.get("downloads"),
            likes=payload.get("likes"),
        )
        group_specs = _build_variant_groups(payload, num_parameters=num_parameters)
        aliases = [payload["id"]] if payload.get("id") else []
        multi_variant_repo = len(group_specs) > 1

        specs: list[ModelSpec] = []
        for group in group_specs:
            specs.append(
                ModelSpec(
                    canonical_name=_build_canonical_name(payload["id"], group.variant),
                    aliases=[] if multi_variant_repo else aliases,
                    source_url=source_url,
                    source_sha=payload.get("sha"),
                    raw_ref=raw_ref,
                    hf_repo_id=payload["id"],
                    variant=group.variant,
                    task=task,
                    license_id=license_id,
                    inference=InferenceInfo(provider_required=True, status=status),
                    declared_context_tokens=declared_context_tokens,
                    architecture_hint=arch,
                    num_parameters=num_parameters,
                    weights=group.weights,
                    popularity=popularity,
                )
            )
        return specs


def _infer_precision(payload: dict[str, Any]) -> str | None:
    tags = [tag.lower() for tag in payload.get("tags", [])]
    parameters = (payload.get("safetensors") or {}).get("parameters") or {}
    parameter_keys = [key.lower() for key in parameters.keys()]
    repo_id = (payload.get("id") or "").lower()
    filenames = [str(item.get("rfilename", "")).lower() for item in payload.get("siblings") or []]
    for candidate in ("bf16", "fp16", "fp32", "int8"):
        if candidate in tags or candidate in parameter_keys:
            return candidate
    if "f16" in parameter_keys:
        return "fp16"
    if "f32" in parameter_keys:
        return "fp32"
    for candidate in ("bf16", "fp16", "fp32", "int8"):
        if candidate in repo_id or any(candidate in filename for filename in filenames):
            return candidate
    return None


def _infer_quantization(payload: dict[str, Any]) -> str | None:
    config = payload.get("config") or {}
    quantization_config = config.get("quantization_config") or {}
    quant_method = quantization_config.get("quant_method")
    bits = quantization_config.get("bits")
    if isinstance(quant_method, str):
        normalized_method = quant_method.lower()
        if bits:
            return f"{normalized_method}-{bits}bit"
        return normalized_method

    tags = [tag.lower() for tag in payload.get("tags", [])]
    repo_id = (payload.get("id") or "").lower()
    filenames = [str(item.get("rfilename", "")).lower() for item in payload.get("siblings") or []]
    for tag in tags:
        if tag.startswith("gptq") or tag.startswith("awq") or tag.startswith("gguf") or re.match(r"q\d", tag):
            return tag
    for source in [repo_id, *filenames]:
        match = _match_variant_token(source)
        if match and match not in {"fp16", "bf16", "fp32"}:
            return match
        if "awq" in source:
            return "awq"
        if "gptq" in source:
            return "gptq"
    return None


def _infer_format(payload: dict[str, Any], weight_files: list[WeightFile]) -> str | None:
    if payload.get("gguf") is not None:
        return "gguf"
    if payload.get("safetensors") is not None:
        return "safetensors"
    for candidate in ("gguf", "safetensors", "bin"):
        if any(file.path.endswith(f".{candidate}") for file in weight_files):
            return candidate
    return None


def _infer_declared_context(payload: dict[str, Any], config: dict[str, Any], card_data: dict[str, Any]) -> int | None:
    gguf = payload.get("gguf") or {}
    if isinstance(gguf.get("context_length"), int):
        return gguf["context_length"]
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
    safetensors = payload.get("safetensors") or {}
    if isinstance(safetensors.get("total"), int):
        return safetensors["total"]
    gguf = payload.get("gguf") or {}
    if isinstance(gguf.get("total"), int):
        return gguf["total"]
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


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


class _VariantGroup:
    def __init__(self, variant: VariantSpec, weights: WeightsInfo) -> None:
        self.variant = variant
        self.weights = weights


def _build_variant_groups(payload: dict[str, Any], *, num_parameters: int | None) -> list[_VariantGroup]:
    siblings = payload.get("siblings") or []
    sized_weight_files = [
        WeightFile(path=item["rfilename"], size_bytes=int(item["size"]))
        for item in siblings
        if item.get("rfilename") and item.get("size") is not None
    ]
    default_variant = VariantSpec(
        precision=_infer_precision(payload),
        quantization=_infer_quantization(payload),
        format=_infer_format(payload, sized_weight_files),
    )
    default_total_size = _infer_total_size_bytes(
        payload,
        num_parameters=num_parameters,
        variant=default_variant,
        sized_weight_files=sized_weight_files,
        single_variant_repo=True,
    )

    if payload.get("gguf") is None:
        return [_VariantGroup(default_variant, WeightsInfo(total_size_bytes=default_total_size, files=sized_weight_files))]

    gguf_groups = _group_gguf_files(siblings)
    if len(gguf_groups) <= 1:
        return [_VariantGroup(default_variant, WeightsInfo(total_size_bytes=default_total_size, files=sized_weight_files))]

    groups: list[_VariantGroup] = []
    for variant_name, files in sorted(gguf_groups.items(), key=lambda item: item[0]):
        variant = _variant_from_name(variant_name, format_name="gguf")
        group_total_size = _infer_total_size_bytes(
            payload,
            num_parameters=num_parameters,
            variant=variant,
            sized_weight_files=files,
            single_variant_repo=False,
        )
        groups.append(_VariantGroup(variant, WeightsInfo(total_size_bytes=group_total_size, files=files)))
    return groups


def _group_gguf_files(siblings: list[dict[str, Any]]) -> dict[str, list[WeightFile]]:
    groups: dict[str, list[WeightFile]] = {}
    for item in siblings:
        path = item.get("rfilename")
        if not path or not str(path).lower().endswith(".gguf"):
            continue
        variant_name = _match_variant_token(str(path).lower()) or "gguf"
        file_size = item.get("size")
        if file_size is None:
            groups.setdefault(variant_name, [])
            continue
        groups.setdefault(variant_name, []).append(WeightFile(path=path, size_bytes=int(file_size)))
    return groups


def _variant_from_name(variant_name: str, *, format_name: str) -> VariantSpec:
    if variant_name in {"fp16", "bf16", "fp32", "int8"}:
        return VariantSpec(precision=variant_name, format=format_name)
    if variant_name == "gguf":
        return VariantSpec(format=format_name)
    return VariantSpec(quantization=variant_name, format=format_name)


def _infer_total_size_bytes(
    payload: dict[str, Any],
    *,
    num_parameters: int | None,
    variant: VariantSpec,
    sized_weight_files: list[WeightFile],
    single_variant_repo: bool,
) -> int | None:
    if sized_weight_files:
        return sum(item.size_bytes for item in sized_weight_files)

    used_storage = payload.get("usedStorage")
    if single_variant_repo and isinstance(used_storage, int):
        return used_storage

    bits = _variant_bits(variant, payload)
    if num_parameters is not None and bits is not None:
        return int(num_parameters * bits / 8)
    return used_storage if isinstance(used_storage, int) and single_variant_repo else None


def _variant_bits(variant: VariantSpec, payload: dict[str, Any]) -> int | None:
    quantization_config = (payload.get("config") or {}).get("quantization_config") or {}
    bits = quantization_config.get("bits")
    if isinstance(bits, int):
        return bits

    quant = (variant.quantization or "").lower()
    precision = (variant.precision or "").lower()
    if match := re.match(r"q(\d+)", quant):
        return int(match.group(1))
    if precision == "int8":
        return 8
    if precision in {"bf16", "fp16"}:
        return 16
    if precision == "fp32":
        return 32
    if variant.format == "safetensors":
        parameters = (payload.get("safetensors") or {}).get("parameters") or {}
        keys = {key.lower() for key in parameters.keys()}
        if "bf16" in keys:
            return 16
        if "f16" in keys or "fp16" in keys:
            return 16
        if "f32" in keys or "fp32" in keys:
            return 32
    return None


def _infer_license_id(payload: dict[str, Any], card_data: dict[str, Any]) -> str | None:
    license_id = card_data.get("license")
    if isinstance(license_id, str) and license_id:
        return license_id
    for tag in payload.get("tags", []):
        if isinstance(tag, str) and tag.startswith("license:"):
            return tag.split(":", 1)[1]
    return None


def _match_variant_token(value: str) -> str | None:
    lower = value.lower()
    match = re.search(r"(q\d(?:_[a-z0-9]+)*|fp16|bf16|fp32|int8)", lower)
    if match is None:
        return None
    token = match.group(1)
    if token == "int8":
        return token
    return token
