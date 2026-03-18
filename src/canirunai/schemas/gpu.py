from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import BaseSpec, CatalogBase, StrictModel


class ApiSupport(StrictModel):
    vulkan: str | None = None
    direct3d: str | None = None
    opengl: str | None = None


class GpuSpec(BaseSpec):
    kind: Literal["gpu"] = "gpu"
    vendor: str
    product_line: str | None = None
    architecture: str | None = None
    codename: str | None = None
    process_nm: float | None = None
    bus_interface: str | None = None
    memory_size_gib: float | None = None
    memory_bus_width_bit: int | None = None
    memory_bandwidth_gbs: float | None = None
    tdp_w: float | None = None
    api_support: ApiSupport | None = None
    cuda_compute_capability: str | None = None
    processing_power_fp32_gflops: float | None = None


class GpuCatalog(CatalogBase):
    items: list[GpuSpec] = Field(default_factory=list)
