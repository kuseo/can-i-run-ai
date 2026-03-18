from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import BaseSpec, CatalogBase, StrictModel


class VariantSpec(StrictModel):
    precision: str | None = None
    quantization: str | None = None
    format: str | None = None


class InferenceInfo(StrictModel):
    provider_required: bool = True
    status: str | None = None


class ArchitectureHint(StrictModel):
    model_type: str | None = None
    num_layers: int | None = None
    hidden_size: int | None = None
    num_attention_heads: int | None = None
    num_kv_heads: int | None = None
    vocab_size: int | None = None


class WeightFile(StrictModel):
    path: str
    size_bytes: int


class WeightsInfo(StrictModel):
    total_size_bytes: int | None = None
    files: list[WeightFile] = Field(default_factory=list)


class PopularityInfo(StrictModel):
    downloads_30d: int | None = None
    likes: int | None = None


class ModelSpec(BaseSpec):
    kind: Literal["model"] = "model"
    source: Literal["huggingface"] = "huggingface"
    hf_repo_id: str
    variant: VariantSpec = Field(default_factory=VariantSpec)
    task: str
    license_id: str | None = None
    inference: InferenceInfo | None = None
    declared_context_tokens: int | None = None
    architecture_hint: ArchitectureHint | None = None
    num_parameters: int | None = None
    weights: WeightsInfo = Field(default_factory=WeightsInfo)
    popularity: PopularityInfo | None = None


class ModelCatalog(CatalogBase):
    items: list[ModelSpec] = Field(default_factory=list)
