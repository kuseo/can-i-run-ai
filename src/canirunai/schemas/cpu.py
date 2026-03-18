from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import BaseSpec, CatalogBase


class CpuSpec(BaseSpec):
    kind: Literal["cpu"] = "cpu"
    vendor: str
    family: str | None = None
    model: str | None = None
    cores: int | None = None
    threads: int | None = None
    base_clock_ghz: float | None = None
    boost_clock_ghz: float | None = None
    l3_cache_mb: float | None = None
    tdp_w: float | None = None
    codename: str | None = None
    socket: str | None = None
    release: str | None = None


class CpuCatalog(CatalogBase):
    items: list[CpuSpec] = Field(default_factory=list)
