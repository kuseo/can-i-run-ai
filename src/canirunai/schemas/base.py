from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RawReference(StrictModel):
    cache_key: str


class CollectionSource(StrictModel):
    collector: str
    notes: str | None = None


class BaseSpec(StrictModel):
    kind: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    collected_at: datetime = Field(default_factory=utc_now)
    source_url: str
    source_revision_id: int | None = None
    source_sha: str | None = None
    raw_ref: RawReference | None = None


class CatalogBase(StrictModel):
    schema_version: int = 1
    generated_at: datetime = Field(default_factory=utc_now)
    source: CollectionSource
