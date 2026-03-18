# `check` QA Report

Date: 2026-03-18

This report records QA results for the `uv run canirunai check` command against the current catalog files in `data/specs/`.

Only `check` was tested in this pass. As requested, `get`, `update`, and `list` were excluded.

## Scope

- Validate normal `check` execution with current CPU, GPU, and model catalogs
- Validate `default`, `wide`, and `json` output modes
- Validate multiple `--cpu` and `--gpu` options
- Validate alias resolution for CPU and GPU names
- Validate current behavior when a Hugging Face repo id is passed instead of a model canonical variant name
- Validate basic CLI error handling for missing required options and unknown resource names

## Environment

- Working tree catalog sources:
  - `data/specs/cpu.json`
  - `data/specs/gpu.json`
  - `data/specs/model.json`
- In the Codex sandbox environment, `UV_CACHE_DIR=/tmp/uv-cache` was set when running `uv` commands because the default cache path was read-only.

## Summary

- Total scenarios executed: 11
- Passed: 10
- Issues found: 1

## Passed Scenarios

### 1. Default output format

Command:

```bash
uv run canirunai check \
  --cpu "Intel Celeron G6900" \
  --gpu "AMD FirePro W5100" \
  --memory 64 \
  --model "Qwen/Qwen2-0.5B-Instruct-GGUF@q4_k_m"
```

Observed result:

- `verdict: RUNS GREAT`
- `score: 94`
- `context_estimate: safe_context_tokens=27852, max_supported_context_tokens=32768`
- `decode_tokens_per_sec: 87.44`

### 2. Wide output format

Command:

```bash
uv run canirunai check \
  --cpu "Intel Celeron G6900" \
  --gpu "AMD FirePro W5100" \
  --memory 64 \
  --model "Qwen/Qwen2-0.5B-Instruct-GGUF@q4_k_m" \
  --output wide
```

Observed result:

- `verdict: RUNS GREAT`
- `score: 94`
- `context: safe=27852 max=32768`
- `throughput: decode=87.44 tps prefill=2098.65 tps`
- `memory: weights=0.23 GB total_at_safe=0.55 GB headroom=3.45 GB`
- `bottlenecks: gpu_bandwidth, cpu_threads`

### 3. `RUNS WELL` verdict

Command:

```bash
uv run canirunai check \
  --cpu "Intel Celeron G6900" \
  --gpu "AMD FirePro W5100" \
  --memory 64 \
  --model "Qwen/Qwen2-1.5B-Instruct-GGUF@q4_k_m" \
  --output json
```

Observed result:

- `verdict: RUNS WELL`
- `score: 84`
- `decode_tokens_per_sec: 27.98`

### 4. `TIGHT FIT` verdict

Command:

```bash
uv run canirunai check \
  --cpu "Intel Celeron G6900" \
  --gpu "AMD FirePro W5100" \
  --memory 64 \
  --model "Qwen/Qwen2.5-7B-Instruct-GGUF@q4_k_m" \
  --output json
```

Observed result:

- `verdict: TIGHT FIT`
- `score: 56`
- `decode_tokens_per_sec: 5.67`
- `vram_headroom_gb: 0.13`

### 5. `IMPOSSIBLE` verdict

Command:

```bash
uv run canirunai check \
  --cpu "Intel Celeron G6900" \
  --gpu "AMD FirePro W5100" \
  --memory 64 \
  --model "Qwen/Qwen2.5-14B-Instruct-GGUF@q4_k_m" \
  --output json
```

Observed result:

- `verdict: IMPOSSIBLE`
- `score: 10`
- `safe_context_tokens: 0`
- `single_gpu_loadable: false`

### 6. `TOO HEAVY` verdict

Command:

```bash
uv run canirunai check \
  --cpu "Intel Celeron G6900" \
  --gpu "NVIDIA GeForce RTX 3060" \
  --memory 32 \
  --model "Qwen/Qwen2-0.5B-Instruct-GGUF@q4_k_m" \
  --output json
```

Observed result:

- `verdict: TOO HEAVY`
- `score: 39`
- `safe_context_tokens: 27852`
- `decode_tokens_per_sec: 1.08`

Note:

- This command is working as implemented against the current catalog.
- However, the current RTX 3060 spec entry looks suspicious and should be revalidated. See Findings.

### 7. Alias resolution and HF repo id resolution

Command:

```bash
uv run canirunai check \
  --cpu "PRO 7730U" \
  --gpu "GeForce RTX 4090" \
  --memory 64 \
  --model "Qwen/Qwen2.5-7B-Instruct-GGUF" \
  --output json
```

Observed result:

- CPU input resolved to `AMD PRO 7730U`
- GPU input resolved to `NVIDIA GeForce RTX 4090`
- Model input resolved to `Qwen/Qwen2.5-7B-Instruct-GGUF@fp16`

Note:

- Passing a repo id without a variant currently resolves to the first matching model entry in catalog order.
- This is deterministic, but potentially ambiguous for repos that have multiple variants.

### 8. Multiple `--gpu` options

Command:

```bash
uv run canirunai check \
  --cpu "Intel Celeron G6900" \
  --gpu "AMD FirePro W5100" \
  --gpu "AMD FirePro W5100" \
  --memory 64 \
  --model "Qwen/Qwen2-0.5B-Instruct-GGUF@q4_k_m" \
  --output json
```

Observed result:

- `replica_count: 2`
- `used_gpu_canonical_names` contained two GPUs
- `decode_tokens_per_sec: 87.44`
- `secondary bottleneck: cpu_threads`

### 9. Multiple `--cpu` options

Command:

```bash
uv run canirunai check \
  --cpu "Intel Celeron G6900" \
  --cpu "Intel Celeron G6900" \
  --gpu "AMD FirePro W5100" \
  --gpu "AMD FirePro W5100" \
  --memory 64 \
  --model "Qwen/Qwen2-0.5B-Instruct-GGUF@q4_k_m" \
  --output json
```

Observed result:

- `replica_count: 2`
- `decode_tokens_per_sec` increased from `87.44` to `174.89`

### 10. Missing required option

Command:

```bash
uv run canirunai check \
  --cpu "Intel Celeron G6900" \
  --gpu "AMD FirePro W5100" \
  --model "Qwen/Qwen2-0.5B-Instruct-GGUF@q4_k_m"
```

Observed result:

- Exit code `2`
- Click usage/help message shown
- `Error: Missing option '--memory'.`

## Findings

### 1. Unknown resource names leak Python traceback

Severity: Medium

Reproduced commands:

```bash
uv run canirunai check \
  --cpu "NOPE CPU" \
  --gpu "AMD FirePro W5100" \
  --memory 64 \
  --model "Qwen/Qwen2-0.5B-Instruct-GGUF@q4_k_m"
```

```bash
uv run canirunai check \
  --cpu "Intel Celeron G6900" \
  --gpu "AMD FirePro W5100" \
  --memory 64 \
  --model "NOPE MODEL"
```

Observed result:

- Exit code `1`
- Final error line is `KeyError: 'Unknown CPU: NOPE CPU'` or `KeyError: 'Unknown model: NOPE MODEL'`
- Full traceback is printed

Cause:

- [`check` in `cli/main.py`](/home/kuseo/toy/can-i-run-ai/src/canirunai/cli/main.py#L113) calls SDK methods directly without converting lookup failures into `click.ClickException`
- [`CpuLoader.get()`](/home/kuseo/toy/can-i-run-ai/src/canirunai/loaders/cpu_loader.py#L19) and [`ModelLoader.get()`](/home/kuseo/toy/can-i-run-ai/src/canirunai/loaders/model_loader.py#L19) raise raw `KeyError`

Expected improvement:

- Invalid names should exit cleanly with a short CLI error message, without traceback

## Catalog Quality Follow-up

### RTX 3060 throughput input looks underparsed

The current catalog entry for [`NVIDIA GeForce RTX 3060`](/home/kuseo/toy/can-i-run-ai/data/specs/gpu.json#L27173) contains:

- `memory_size_gib: 12.0`
- `memory_bandwidth_gbs: 360.0`
- `processing_power_fp32_gflops: 9.46`

This value is low enough that `check` classifies a very small quantized model as `TOO HEAVY`.

This is not a `check` command crash, but it is a likely spec parsing/data-quality issue that can materially affect scoring outcomes.

## Recommended Next Steps

1. Wrap loader lookup failures in `click.ClickException` inside `check`
2. Add regression tests for invalid `--cpu`, `--gpu`, and `--model` inputs
3. Revalidate low `processing_power_fp32_gflops` values in GPU catalog, starting with RTX 3060-class entries
