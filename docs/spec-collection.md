# Spec Collection

This document explains how canirunai collects, normalizes, and stores CPU, GPU, and model specs.

## Overview

The collection layer exists to turn unstable external sources into stable internal catalogs. The SDK wants structured JSON that can be used later by `list`, `get`, and `check` without depending on live network calls at scoring time.

The collection flow is:

1. Choose a source for a resource type such as CPU, GPU, or model.
2. Fetch raw source data when live requests are enabled.
3. Preserve the raw source payload in `raw_cache`.
4. Try a deterministic rule-based parser first.
5. Only if that parser fails to produce a valid structured result, allow an LLM parser fallback.
6. Convert the final parsed data into typed Pydantic spec objects.
7. Merge the new specs into the persistent JSON catalogs under `data/specs`.

The persistent catalogs are the canonical runtime data source for the rest of the SDK.

## Collection Goals

- Keep a stable internal schema even when external pages vary in format.
- Preserve source provenance such as `source_url`, collection time, revision id, or repo sha.
- Support incremental updates instead of rebuilding everything from scratch every time.
- Separate raw-source acquisition from normalization and scoring.
- Prefer deterministic parsing whenever possible.
- Use an LLM parser only as a fallback when rule-based parsing fails.
- Allow future live crawlers and LLM parsers without changing the downstream SDK interface.

## Current MVP Behavior

The current implementation is still offline-capable, but live collection is now partially operational.

- CPU and GPU updates still use bundled seed catalogs by default because `sdk.prefer_live_requests` defaults to `false`.
- When live requests are enabled, CPU and GPU updates fetch Wikipedia HTML, parse tables with a deterministic HTML table parser, and write live specs into the local catalogs.
- Model updates support both a single-repo live path and a bulk live catalog path through Hugging Face.
- If live collection fails and `sdk.offline_seed_fallback = true`, the collectors fall back to the bundled seed catalogs.
- If live collection fails and `sdk.offline_seed_fallback = false`, the update command fails instead of silently switching to seed data.
- The seed catalogs allow `update`, `list`, `get`, and `check` to work in environments without network access.

This means the architecture is split the right way and now has a working live path, but the parsing heuristics are still evolving.

## Resource Types

### CPU Specs

CPU specs are intended to come from Wikipedia source pages for Intel and AMD Ryzen processors.

Typical CPU fields include:

- `canonical_name`
- `vendor`
- `family`
- `model`
- `cores`
- `threads`
- `base_clock_ghz`
- `boost_clock_ghz`
- `l3_cache_mb`
- `tdp_w`
- `codename`
- `socket`
- `release`
- `source_url`
- `source_revision_id`

Current behavior:

- by default, `update cpu` writes the bundled CPU seed list into `data/specs/cpu.json`,
- with `sdk.prefer_live_requests = true`, it fetches live Wikipedia pages and extracts CPU specs with the rule-based table parser.

### GPU Specs

GPU specs are intended to come from Wikipedia source pages for NVIDIA and AMD GPUs.

Typical GPU fields include:

- `canonical_name`
- `vendor`
- `product_line`
- `architecture`
- `codename`
- `process_nm`
- `bus_interface`
- `memory_size_gib`
- `memory_bus_width_bit`
- `memory_bandwidth_gbs`
- `tdp_w`
- `api_support`
- `cuda_compute_capability`
- `processing_power_fp32_gflops`
- `source_url`
- `source_revision_id`

Current behavior:

- by default, `update gpu` writes the bundled GPU seed list into `data/specs/gpu.json`,
- with `sdk.prefer_live_requests = true`, it fetches live Wikipedia pages and extracts GPU specs with the rule-based table parser.

### Model Specs

Model specs are intended to come from Hugging Face model metadata and file manifests.

Typical model fields include:

- `canonical_name`
- `hf_repo_id`
- `variant`
- `task`
- `license_id`
- `inference`
- `declared_context_tokens`
- `architecture_hint`
- `num_parameters`
- `weights`
- `popularity`
- `source_url`
- `source_sha`

Current behavior:

- `update model` without `--hfname` uses the bundled seed model catalog by default,
- with `sdk.prefer_live_requests = true`, `update model --hfname <repo>` performs a live single-repo Hugging Face fetch,
- with `sdk.prefer_live_requests = true`, `update model` can also build a bulk live catalog from the configured Hugging Face teams list,
- the live path maps Hugging Face payloads into `ModelSpec`, infers precision or quantization when possible, and records raw payloads in cache.

## Source Acquisition

### Wikipedia

The intended Wikipedia approach is:

1. Use the MediaWiki API to fetch page revisions and parsed HTML.
2. Record revision ids so catalog entries can be traced to a concrete source version.
3. Cache the raw HTML locally.
4. Parse the HTML into normalized CPU or GPU spec records with a deterministic HTML table parser.
5. If deterministic parsing cannot recover valid structured rows, use an LLM parser only as a fallback.

This separation matters because Wikipedia tables are not stable across sections, generations, or vendors.

In the current code, enabling live requests causes the collectors to:

- fetch the target Wikipedia page HTML,
- store it under `raw_cache`,
- parse the HTML with a rule-based table parser,
- convert matching rows into `CpuSpec` or `GpuSpec`,
- fall back to seed data only if live collection fails and seed fallback is allowed.

The intended long-term rule is still deterministic parser first, LLM parser only on failure.

### Hugging Face

The intended Hugging Face approach is:

1. Use the Hub API for model discovery and model detail lookup.
2. Extract repo metadata, config, model card data, and sibling file lists.
3. Infer normalized fields like precision, format, quantization, parameter count, and context length.
4. Store the resulting `ModelSpec` entries in the local catalog.
5. Use an LLM parser only as a fallback for cases that cannot be normalized deterministically.

The current implementation already supports both single-repo and limited bulk live updates. It reads fields such as:

- repo id
- config values
- tags
- file list
- downloads
- likes
- sha

It then derives a `canonical_name` in the form `repo_id@variant`.

As with Wikipedia collection, the parsing policy is deterministic first and LLM fallback only when rules fail.

## Raw Cache

Raw source payloads are stored separately from normalized catalogs.

The purpose of `raw_cache` is:

- reproducibility,
- debugging,
- parser iteration,
- future replay-based regression tests.

Examples of raw-cache usage:

- store Wikipedia HTML snapshots,
- store Hugging Face model JSON payloads,
- keep a durable reference from a spec item back to the raw input.

Each spec can include a `raw_ref.cache_key` that points back to the cached source artifact.

## Normalization Principles

Collection is not just fetch-and-save. The raw data is normalized into stable internal records.

The preferred normalization order is:

1. deterministic field extraction,
2. schema validation,
3. LLM fallback only if deterministic parsing fails or the source shape is not recoverable with rules.

Important normalization rules include:

- every item has a `canonical_name`,
- every item is typed as `cpu`, `gpu`, or `model`,
- source provenance fields are preserved,
- optional fields remain optional rather than forcing fake defaults,
- aliases can be stored for lookup convenience,
- model variants are treated as separate entities.

For models, normalization also includes heuristic inference:

- infer precision from tags,
- infer quantization from tags,
- infer file format from file extensions,
- infer context length from config or card data,
- infer parameter count from integer fields or human-readable strings.

## Canonical Names and Merging

The catalog merge process is name-based.

When new items are written:

- the collector returns normalized spec objects,
- the store loads the existing catalog,
- items are merged by a normalized lookup key derived from `canonical_name`,
- the merged result is sorted and saved back atomically.

The lookup key removes case and punctuation differences so small formatting changes do not create duplicate entries.

This makes updates incremental:

- existing entries are replaced if the canonical key matches,
- new entries are added,
- unrelated entries remain untouched.

## Persistent Catalogs

The current catalog files are:

- `data/specs/cpu.json`
- `data/specs/gpu.json`
- `data/specs/model.json`

These files are the runtime data source for:

- `canirunai list ...`
- `canirunai get ...`
- `canirunai check ...`

Once a catalog exists locally, scoring no longer depends on live source availability.

## Why Collection Is Decoupled From Scoring

Collection and scoring solve different problems.

- Collection answers: "What are the hardware and model specs?"
- Scoring answers: "Given those specs, how well will this setup run the model?"

Keeping them separate avoids mixing unstable source parsing with deterministic estimation logic.

This design also makes it practical to:

- update catalogs on one machine,
- copy catalogs elsewhere,
- run checks repeatedly without repeated network access,
- improve collectors independently from the scoring engine.

## Future Extensions

The current structure is designed to support later upgrades without breaking the SDK interface.

Likely future extensions include:

- refinement of the current Wikipedia HTML-to-schema parser,
- OpenAI Structured Outputs based fallback parsing for difficult source layouts,
- wider Hugging Face catalog sync,
- additional variant extraction rules for GGUF, GPTQ, AWQ, and similar formats,
- revision-aware incremental updates,
- replay tests driven by cached raw payloads.
