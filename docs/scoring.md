# Scoring

This document explains how canirunai estimates whether a hardware setup can run a model and how it produces a verdict and score.

## Overview

The scoring layer consumes structured specs, not raw web pages. Its job is to take:

- one or more CPUs,
- one or more GPUs,
- user-provided system RAM,
- one model spec,

and produce a `ScoreReport` with:

- `verdict`
- `score`
- `context_estimate`
- `throughput_estimate`
- `placement_estimate`
- wide diagnostic fields such as memory, latency, bottlenecks, and confidence

The scoring system is heuristic. It is not a benchmark runner and it does not detect the live machine state.

## Input Principles

The score calculation is based on catalog specs plus user input.

Important rules:

- CPU, GPU, and model details come from the stored catalogs.
- RAM is supplied explicitly by the user.
- The engine does not run the target model.
- The engine does not probe drivers, CUDA, runtime libraries, or actual measured throughput.

This is deliberate. The goal is a deterministic spec-based estimate.

## What the Engine Is Trying to Answer

The estimator answers two separate questions:

1. Can the model fit at all?
2. If it fits, how comfortably and how fast?

Those are related but not identical. A model may technically fit while still being too slow or too constrained to be practical.

## Core Intermediate Values

The implementation first derives a few key quantities.

### 1. Weight Size

The model weight size is estimated from:

- `weights.total_size_bytes` when available,
- otherwise `num_parameters * bits_per_parameter / 8`

The bit width comes from model variant hints:

- `q4*` quantization maps to 4 bits,
- `q5*` maps to 5 bits,
- `q8*` maps to 8 bits,
- `bf16` or `fp16` maps to 16 bits,
- `fp32` maps to 32 bits.

This is the base VRAM footprint before KV cache and runtime overhead.

### 2. KV Cache Bytes Per Token

The KV cache estimate uses the architecture hint:

- number of layers,
- hidden size,
- attention head counts,
- KV head counts,
- KV element width in bits.

The simplified formula is:

```text
kv_bytes_per_token ≈ 2 * num_layers * hidden_size * kv_head_ratio * bytes_per_element
```

The factor of 2 represents key and value storage.

If the model does not contain enough architecture data, the KV estimate drops to zero and the engine cannot infer a VRAM-limited context size from KV growth.

### 3. Runtime Overhead

The engine reserves a fixed fraction of VRAM for runtime overhead:

```text
runtime_overhead_bytes = available_vram_bytes * overhead_ratio
```

This represents allocator overhead, framework buffers, fragmentation, and similar runtime costs.

### 4. Max Supported Context

For one GPU, the theoretical max context is:

```text
max_context_tokens =
  floor((available_vram_bytes - weights_bytes - runtime_overhead_bytes) / kv_bytes_per_token)
```

If `weights + overhead` already exceed VRAM, the model is considered unloadable on that GPU.

### 5. Safe Context

The theoretical max context is not treated as safe operating space. The engine derives:

```text
safe_context_tokens = min(
  declared_context_tokens,
  floor(max_context_tokens * safe_context_ratio)
)
```

This adds a safety margin and respects the model's declared context ceiling when one exists.

## Multi-GPU Interpretation

The current implementation uses a replication-first interpretation.

That means:

- each replica must fit on a single GPU,
- GPUs that can independently host the model count toward `replica_count`,
- throughput can scale with replica count,
- tensor-parallel and pipeline-parallel partitioning are not modeled in the current MVP.

So the question is not "can total VRAM across GPUs add up?" It is "how many individual GPUs can each host one full replica?"

## Throughput Estimation

Throughput is estimated from spec-derived upper bounds.

### Decode Tokens Per Second

The engine estimates a single-GPU decode throughput from two possible limits.

#### Bandwidth-Limited Throughput

```text
tps_bw = (memory_bandwidth_bytes_per_sec * eff_bw) / bytes_per_token_work
```

Where:

- `memory_bandwidth_bytes_per_sec` comes from the GPU spec,
- `eff_bw` is a configurable efficiency factor,
- `bytes_per_token_work` is approximated as `weights_bytes * stream_reuse_factor`.

This models decode as a weight-streaming dominated process.

#### Compute-Limited Throughput

If FP32 throughput data exists, the engine also computes:

```text
tps_flops = (fp32_flops_per_sec * eff_flops) / flops_per_token_work
```

With:

```text
flops_per_token_work ≈ 2 * num_parameters
```

This is a rough multiply-add style estimate. The engine chooses the smaller of the bandwidth and compute limits when both exist.

### Total Throughput Across Replicas

After finding single-replica decode throughput, the engine multiplies by replica count and then caps the result by a CPU thread budget.

The CPU cap assumes that each replica needs some host-side threads for tokenization, orchestration, and request handling.

### Prefill Tokens Per Second

Prefill throughput is derived from decode throughput using a simple multiplier:

```text
prefill_tps = decode_tps * prefill_multiplier
```

This is intentionally simple and configurable.

## Host RAM Estimate

The engine also checks system RAM using a heuristic:

```text
host_ram_required_gb = max(8.0, weights_gb * host_ram_weight_fraction + 4.0)
```

This is not meant to predict exact resident memory. It is a practical lower-bound style signal that the host still needs room for model loading, runtime support, and general serving overhead.

## Verdict Logic

The verdict is not a direct label on the final numeric score. It is determined by ordered gates.

### IMPOSSIBLE

Returned when:

- no GPU can load the model, or
- `safe_context_tokens` falls below `min_context_tokens`

This is the hard fail condition.

### TOO HEAVY

Returned when the model fits in a narrow technical sense but is still impractical, for example:

- safe context is too small, or
- decode throughput is below the minimum acceptable threshold

### TIGHT FIT

Returned when the model is usable but still constrained, for example:

- VRAM headroom is too low, or
- host RAM headroom is negative

### RUNS WELL

Returned when the model fits with acceptable context, throughput, and headroom.

### RUNS GREAT

Returned when the model has strong context support and high decode throughput with comfortable headroom.

## Numeric Score

After the verdict is chosen, the engine computes a numeric score from four normalized factors:

- context ratio,
- speed ratio,
- VRAM headroom ratio,
- host RAM ratio

The weighted score is approximately:

```text
score_raw =
  context_ratio * 0.40 +
  speed_ratio   * 0.35 +
  headroom_ratio* 0.15 +
  ram_ratio     * 0.10
```

Then the result is scaled to 0 to 100 and clamped into the verdict's score band:

- `IMPOSSIBLE`: up to 15
- `TOO HEAVY`: 16 to 39
- `TIGHT FIT`: 40 to 59
- `RUNS WELL`: 60 to 84
- `RUNS GREAT`: 85 and above

This preserves a stable relationship between the qualitative verdict and the quantitative score.

## Wide Output Fields

The wide report includes extra diagnostics derived from the same intermediate values.

### Placement Estimate

Shows:

- placement mode,
- whether a single GPU can host the model,
- replica count,
- which GPUs are considered usable for serving replicas

### Memory Estimate

Shows:

- estimated weight VRAM,
- runtime overhead VRAM,
- KV cache cost per 1k tokens,
- total VRAM at the safe context,
- VRAM headroom,
- estimated host RAM requirement,
- host RAM headroom

### Latency Estimate

Provides a simplified latency view:

- first-token time per 1k prompt tokens,
- generation time for 128 output tokens

These are derived from the estimated throughput, not from measured runtime.

### Bottlenecks

The engine labels likely bottlenecks such as:

- `gpu_vram`
- `gpu_bandwidth`
- `gpu_compute`
- `system_ram`
- `cpu_threads`

These are meant to explain why the score is constrained.

### Confidence

Confidence is qualitative.

- context confidence is higher when the model architecture hint and GPU VRAM are both known,
- throughput confidence is higher when GPU bandwidth data exists.

This is a way to signal how much the result depends on complete source data.

## What the Score Does Not Model

The current scorer intentionally ignores several real-world variables.

It does not model:

- runtime-specific kernel quality,
- exact quantization implementation details,
- tensor parallel distribution,
- PCIe or NVLink topology,
- driver problems,
- CPU cache behavior beyond a simple thread cap,
- prompt-template overhead,
- tokenizer speed differences,
- actual benchmark measurements.

These omissions are acceptable for a spec-based estimator but should be understood as limitations.

## Why the Scoring Is Still Useful

Even with those simplifications, the estimator is useful because it gives consistent answers to common planning questions:

- will the model fit on this GPU at all,
- how much context is likely to be safe,
- is the setup obviously too constrained,
- is the bottleneck likely VRAM, bandwidth, or host memory,
- will adding more identical GPUs help via replication

That is enough to support early hardware screening and rough deployment planning.

## Future Directions

The current scoring structure can be extended without changing the output contract.

Likely future improvements include:

- better quantization-aware memory models,
- architecture-specific KV formulas,
- explicit tensor-parallel support,
- empirical correction factors from benchmark datasets,
- model-family specific throughput heuristics,
- confidence scoring tied to source completeness and validation coverage.
