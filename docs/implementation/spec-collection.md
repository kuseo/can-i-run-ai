# Spec Collection

This document explains how `canirunai` collects, normalizes, and stores CPU, GPU, and model specs.

## Overview

The collection layer turns unstable external sources into stable local catalogs used by `list`, `get`, and `check`.

The current collection flow is:

1. choose a resource type: CPU, GPU, or model
2. try live collection if `sdk.prefer_live_requests = true`
3. cache raw source payloads under `raw_cache`
4. parse or normalize the payload with deterministic code
5. validate the result as typed Pydantic specs
6. merge the new specs into `data/specs/*.json`
7. if live collection fails and `sdk.offline_seed_fallback = true`, fall back to bundled seed data

Important current reality:

- the codebase contains an OpenAI structured parser interface
- the collectors do not call it yet
- so the current live path is deterministic parsing only, not deterministic parsing plus live LLM fallback

## Current Runtime Behavior

With the built-in config in this repository:

- `sdk.prefer_live_requests = true`
- `sdk.offline_seed_fallback = true`

So `update cpu`, `update gpu`, and `update model` all try live collection first by default and fall back to bundled seed data only if the live path fails.

The architecture is still offline-capable because:

- the seed catalogs remain available
- all scoring uses local JSON catalogs rather than live network calls

## Resource Types

### CPU Specs

CPU specs come from Intel and AMD Wikipedia pages.

Typical fields include:

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

- live CPU updates fetch page revision info and parsed HTML through the MediaWiki API
- raw HTML is cached under `raw_cache`
- a rule-based table parser converts matching rows into `CpuSpec`
- if live CPU collection fails and seed fallback is enabled, bundled CPU seed data is used instead

### GPU Specs

GPU specs come from NVIDIA and AMD Wikipedia pages.

Typical fields include:

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
- `processing_power_fp16_gflops`
- `processing_power_bf16_gflops`
- `processing_power_fp8_gflops`
- `processing_power_int8_gops`
- `source_url`
- `source_revision_id`

Current behavior:

- live GPU updates fetch page revision info and parsed HTML through the MediaWiki API
- raw HTML is cached under `raw_cache`
- a rule-based table parser converts matching rows into `GpuSpec`
- NVIDIA low-precision compute fields are normalized during collection and also again during load
- if live GPU collection fails and seed fallback is enabled, bundled GPU seed data is used instead

That low-precision normalization is important because some source tables do not provide strong FP16 / BF16 / FP8 / INT8 metrics consistently for modern NVIDIA GPUs.

### Model Specs

Model specs come from Hugging Face API metadata and file manifests.

Typical fields include:

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

- `update model --hfname <repo>` performs a single-repo live Hugging Face fetch when live requests are enabled
- `update model` without `--hfname` performs a bulk live sync from the configured team list when live requests are enabled
- a single repo may normalize into multiple `ModelSpec` entries when multiple variants can be inferred
- raw JSON payloads are cached under `raw_cache`
- if live model collection fails and seed fallback is enabled, bundled model seed data is used instead

## Source Acquisition

### Wikipedia

The current Wikipedia path is:

1. use the MediaWiki API to fetch revision ids
2. use the MediaWiki API `parse` endpoint to fetch rendered HTML
3. cache the HTML locally
4. parse tables with deterministic HTML-table logic
5. map matching rows to `CpuSpec` or `GpuSpec`

This path is intentionally deterministic so parser problems can be debugged and replayed from cached HTML.

### Hugging Face

The current Hugging Face path is:

1. use `GET /api/models` for bulk discovery
2. use `GET /api/models/<repo>` for detailed repo payloads
3. extract config, tags, siblings, popularity, card data, and sha
4. infer precision, quantization, format, context length, and parameter count when possible
5. build one or more `ModelSpec` variants

Bulk live sync is currently constrained by:

- configured team names
- per-team model caps
- a total model cap

The current collector actively uses:

- `pipeline_tag`
- `license_id`
- `teams`

The config fields `inference_provider` and `num_parameters` exist but are not yet enforced by the current live collector.

## Raw Cache

Raw payloads are stored separately from normalized catalogs.

Current examples include:

- Wikipedia CPU HTML snapshots
- Wikipedia GPU HTML snapshots
- Hugging Face model JSON payloads

The raw cache is useful for:

- reproducibility
- debugging parser failures
- replay-based parser iteration
- comparing old and new normalization logic against the same source payload

Specs may include `raw_ref.cache_key` so a normalized item can be traced back to the cached raw input.

## Normalization Principles

Collection is not just fetch-and-save. Raw data is normalized into stable internal records.

Important normalization rules include:

- every item gets a `canonical_name`
- every item is validated as `cpu`, `gpu`, or `model`
- provenance fields such as source URL and revision / sha are preserved
- optional fields stay optional rather than being forced to fake defaults
- aliases may be stored for lookup convenience
- model variants are treated as separate entities

Additional current normalization behavior:

- model variants can be split by precision, quantization, or GGUF filename patterns
- some NVIDIA low-precision GPU metrics are derived heuristically when source data is flat or incomplete
- GPU metric normalization is applied both at collection time and loader time

## Canonical Names And Merging

Updates are incremental.

When new items are written:

1. the collector returns normalized spec objects
2. the store loads the existing catalog
3. items are merged by a normalized lookup key derived from `canonical_name`
4. the merged result is sorted and written atomically

This means:

- matching canonical names replace older entries
- new items are added
- unrelated entries remain untouched

## Persistent Catalogs

The current runtime catalogs are:

- `data/specs/cpu.json`
- `data/specs/gpu.json`
- `data/specs/model.json`

These files are the data source for:

- `canirunai list ...`
- `canirunai get ...`
- `canirunai check ...`

Once those catalogs exist locally, scoring does not depend on network access.

## LLM Fallback Status

The intended long-term parser policy is still:

1. deterministic parser first
2. LLM fallback only when deterministic parsing cannot recover a valid structured result

But the current implementation is earlier than that policy:

- deterministic live parsing is implemented
- seed fallback is implemented
- the OpenAI structured parser hook exists
- live collectors do not invoke that parser yet

So if deterministic live parsing fails today, the code either falls back to bundled seed data or raises an error. It does not yet automatically make a live OpenAI parsing call.

## Why Collection Is Decoupled From Scoring

Collection answers:

- "What are the hardware and model specs?"

Scoring answers:

- "Given those specs, how well will this setup run the model?"

Keeping them separate makes it possible to:

- update catalogs on one machine
- reuse those catalogs elsewhere
- run repeated checks without repeated network access
- improve collectors without changing the scoring interface

## Future Extensions

Likely next collection improvements include:

- further refinement of Wikipedia table matching
- stronger live GPU low-precision metric extraction
- broader Hugging Face filtering
- eventually wiring the OpenAI structured parser into the real fallback path
- replay tests driven by cached raw payloads
