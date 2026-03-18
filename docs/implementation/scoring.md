# Scoring

This document explains how `canirunai` estimates whether a hardware setup can run a model and how it produces a verdict and numeric score.

## Overview

The scoring layer consumes stored specs and explicit user RAM input. It does not benchmark the live machine.

Inputs:

- one or more CPUs from the local CPU catalog
- one or more GPUs from the local GPU catalog
- explicit system RAM from the user
- one model from the local model catalog

Output:

- a `ScoreReport` containing verdict, score, placement estimate, context estimate, throughput estimate, and wide diagnostics

The scoring system is heuristic. It is meant to be directionally believable, not benchmark-exact.

## What The Engine Is Trying To Answer

The estimator answers two questions:

1. can the model load on at least one selected GPU?
2. if it can, how comfortable and how fast does that setup look?

A model can fit while still being too constrained to be useful. The verdict logic reflects that distinction.

## Core Intermediate Values

### 1. Weight Size

The engine estimates model weight size in this order:

1. for some low-bit runtime formats, prefer a derived runtime size based on parameter count and bit width
2. otherwise use `weights.total_size_bytes` when present
3. otherwise derive from `num_parameters * bits_per_parameter / 8`

Important current details:

- `mxfp4`, `nvfp4`, `fp4`, and other `*4bit` variants prefer the derived runtime estimate over repository storage size
- this matters for models such as `gpt-oss`, where raw repo storage can overstate actual runtime footprint

### 2. Effective Parameter Count

Some later estimates use an "effective inference parameter count" rather than always using full `num_parameters`.

Current special case:

- `gpt_oss` uses a hardcoded active-parameter fallback for known repos such as `openai/gpt-oss-20b` and `openai/gpt-oss-120b`

That affects both KV fallback and compute-limited throughput.

### 3. KV Cache Bytes Per Token

If architecture hints are present, KV bytes per token are estimated from:

- number of layers
- hidden size
- attention head counts
- KV head counts
- configured KV element width

The simplified formula is:

```text
kv_bytes_per_token ≈ 2 * num_layers * hidden_size * kv_head_ratio * bytes_per_element
```

If architecture data is missing or incomplete, the engine does not drop straight to zero. It uses a parameter-based fallback:

```text
kv_bytes_per_token ≈ effective_parameters / 16384
```

That fallback is intentionally rough, but it prevents obvious false negatives when the catalog lacks full architecture metadata.

### 4. Runtime Overhead

The engine reserves a fixed VRAM fraction for runtime overhead:

```text
runtime_overhead_bytes = available_vram_bytes * overhead_ratio
```

This is meant to cover runtime buffers, allocator overhead, fragmentation, and similar serving costs.

### 5. Max Supported Context

For a single GPU, the VRAM-limited context is:

```text
max_context_tokens =
  floor((available_vram_bytes - weights_bytes - runtime_overhead_bytes) / kv_bytes_per_token)
```

If `weights + overhead` already exceed VRAM, that GPU is treated as unloadable.

If KV bytes per token cannot be estimated:

- use `declared_context_tokens` when present
- otherwise fall back to `too_heavy_context_tokens`

### 6. Safe Context

The engine does not treat max context as safely usable. It derives:

```text
safe_context_tokens = min(
  declared_context_tokens_or_max,
  floor(max_context_tokens * safe_context_ratio)
)
```

Where `declared_context_tokens_or_max` means:

- `declared_context_tokens` if present
- otherwise `max_context_tokens`

## Multi-GPU Interpretation

The current implementation models replicated serving, not model sharding.

That means:

- each replica must fit on one GPU by itself
- VRAM is not summed across GPUs
- `replica_count` is the number of individually loadable GPUs
- throughput can scale with replica count
- tensor parallelism and pipeline parallelism are not modeled

Important current detail:

- context and VRAM headroom are computed against the smallest loadable GPU among the selected GPUs
- throughput scaling can be capped by CPU thread budget

So a two-GPU run may keep the same context and headroom as a one-GPU run while only throughput changes.

## Throughput Estimation

Decode throughput is estimated from two upper bounds and the smaller bound wins.

### 1. Bandwidth-Limited Throughput

```text
tps_bw = (memory_bandwidth_bytes_per_sec * eff_bw) / bytes_per_token_work
```

Where:

- `memory_bandwidth_bytes_per_sec` comes from the GPU spec
- `bytes_per_token_work` is approximated as `weights_bytes * stream_reuse_factor`

This models decode as a mostly weight-streaming problem.

### 2. Compute-Limited Throughput

```text
tps_flops = (gpu_compute_per_sec * eff_flops) / flops_per_token_work
```

With:

```text
flops_per_token_work ≈ 2 * effective_parameters
```

The important current behavior is how `gpu_compute_per_sec` is chosen.

The scorer does not always use FP32. It chooses a preferred GPU metric based on the model variant:

- 4-bit style variants prefer `fp8`, then `int8`, then `bf16`, then `fp16`, then `fp32`
- FP8-style variants prefer `fp8`, then `int8`, then `bf16`, then `fp16`, then `fp32`
- INT8 or `q5` / `q8` style variants prefer `int8`, then `fp8`, then `bf16`, then `fp16`, then `fp32`
- BF16 prefers `bf16`, then `fp16`, then `fp32`
- FP16 prefers `fp16`, then `bf16`, then `fp32`
- anything else falls back to `fp32`

### 3. Low-Precision GPU Metric Normalization

Modern NVIDIA cards often have incomplete or flat low-precision metrics in source data.

The scorer therefore uses normalized GPU metric lookup:

- if a low-precision metric is already meaningfully higher than FP32, use it
- otherwise, some NVIDIA cards derive conservative low-precision tensor-style metrics from FP32, CUDA capability, and product family

This is still heuristic, but it is better than treating every modern NVIDIA GPU as FP32-only.

### 4. Total Decode Throughput Across Replicas

Once single-GPU decode TPS is estimated, the engine multiplies by replica count and then applies a CPU-thread cap:

```text
total_decode_tps = single_gpu_tps * replica_count * cpu_cap_ratio
```

Where:

```text
cpu_cap_ratio = min(1.0, total_threads / (replica_count * cpu_threads_per_replica))
```

So adding more GPUs does not guarantee higher throughput if CPU threads are the limiting factor.

### 5. Prefill Throughput

Prefill throughput is still a simple multiplier on decode throughput:

```text
prefill_tps = decode_tps * prefill_multiplier
```

## Memory And Host RAM Estimates

The scorer also estimates:

- weight VRAM
- runtime overhead VRAM
- KV cache GiB per 1k tokens
- total VRAM at safe context
- VRAM headroom
- required host RAM
- host RAM headroom

Host RAM required is computed as:

```text
host_ram_required_gb = max(8.0, weights_gb * host_ram_weight_fraction + 4.0)
```

This is a serving heuristic, not a measured resident-memory model.

## Verdict Logic

The verdict is chosen before the numeric score is clamped.

### `IMPOSSIBLE`

Returned when:

- no selected GPU can load the model at all, or
- `safe_context_tokens <= 0`

This is the true no-fit bucket.

### `TOO HEAVY`

Returned when the setup is technically loadable but still too constrained for practical use, for example:

- `safe_context_tokens < min_context_tokens`, or
- `decode_tokens_per_sec < min_decode_tps`

This is the current "barely fits / not worth it" bucket.

### `RUNS GREAT`

The engine first checks whether the run is clearly strong:

- `safe_context_tokens >= max(too_heavy_context_tokens, floor(great_context_tokens * safe_context_ratio))`
- `decode_tokens_per_sec >= great_decode_tps`

If that is true:

- return `RUNS GREAT` immediately when resources are not tight
- also return `RUNS GREAT` for some tight-resource cases when:
  - host RAM headroom is non-negative
  - absolute VRAM headroom is at least `2.0 GB`
  - VRAM headroom ratio is at least `max(tight_fit_headroom_ratio / 2, 0.05)`

Otherwise that strong run degrades to `RUNS WELL`.

### `TIGHT FIT` And `RUNS WELL`

Outside the two hard buckets above:

- resources are considered tight when VRAM headroom ratio is below `tight_fit_headroom_ratio` or host RAM headroom is negative
- if resources are tight but context and throughput are still comfortably above the mid-tier thresholds, the verdict becomes `RUNS WELL`
- otherwise tight-resource runs become `TIGHT FIT`
- non-tight runs default to `RUNS WELL`

This is why some low-headroom runs can still be labeled `RUNS WELL` or `RUNS GREAT` if their practical behavior is strong enough.

## Numeric Score

After verdict selection, the engine computes a raw score from:

- context ratio
- speed ratio
- VRAM headroom ratio
- host RAM ratio

Current weighting:

```text
score_raw =
  context_ratio  * 0.40 +
  speed_ratio    * 0.35 +
  headroom_ratio * 0.15 +
  ram_ratio      * 0.10
```

Important current details:

- `context_ratio` is normalized against declared context when available, otherwise against the computed max context
- `speed_ratio` is normalized against `good_decode_tps`, not `great_decode_tps`
- `headroom_ratio` saturates at 25 percent VRAM headroom
- negative host RAM headroom pulls down `ram_ratio`

The raw score is then scaled to `0..100` and clamped into the verdict band:

- `IMPOSSIBLE`: `0..15`
- `TOO HEAVY`: `16..39`
- `TIGHT FIT`: `40..59`
- `RUNS WELL`: `60..84`
- `RUNS GREAT`: `85..100`

## Output Interpretation

The returned `ScoreReport` includes:

- `placement_estimate`
- `context_estimate`
- `throughput_estimate`
- `wide.memory_estimate`
- `wide.latency_estimate`
- `wide.bottlenecks`
- `wide.confidence`

The human-oriented CLI output does not print every wide field, but the JSON form contains the whole structure.

## Current Limitations

- tensor-parallel and pipeline-parallel sharding are not modeled
- throughput remains heuristic and backend-agnostic
- low-precision NVIDIA metric normalization is still partly heuristic
- the engine does not inspect the real machine, driver stack, runtime backend, or measured performance

So the scorer should be read as a practical estimator, not as a benchmark replacement.
