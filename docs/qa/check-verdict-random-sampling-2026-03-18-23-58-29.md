# Random Sampling Review Of `check` Verdicts

Date: 2026-03-18 23:58:29 KST
Git commit: `33b9479db359613116398fcda2bebbd5732f390d`

## Scope

This note records a manual review of roughly 20 randomly sampled `check` runs using:

- NVIDIA RTX / A / L / H series GPUs from the current local GPU catalog
- models in the current local model catalog with roughly `14B` to `120B` parameters
- a very large host memory setting (`--memory 512`) so that host RAM does not dominate the result
- a very large CPU (`AMD 9995WX`) so that CPU threads do not dominate the result

The goal was not to verify mathematical correctness of the current scorer. The goal was to compare:

1. the current code's verdict
2. a subjective, operator-style verdict based on typical single-GPU local inference expectations

No code changes were made as part of this review. This file is documentation only.

## Command Form

Because direct `uv run canirunai` invocations hit sandbox cache restrictions in this environment, I used the equivalent module form below for all runs:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m canirunai check \
  --cpu "AMD 9995WX" \
  --gpu "<gpu>" \
  --memory 512 \
  --model "<model>" \
  --output json
```

Random sampling was generated with seed `20260318`.

## Subjective Verdict Heuristic

The subjective verdicts below are intentionally informal.

- `IMPOSSIBLE`: on a single GPU, the model does not realistically fit, or only "fits" in a nearly unusable sense
- `TOO HEAVY`: it may technically start, but the usable context / comfort level is poor enough that most users would not consider it a good single-GPU run
- `TIGHT FIT`: it runs, but the setup is clearly close to the limit
- `RUNS WELL`: it runs comfortably for typical local use
- `RUNS GREAT`: it runs comfortably and fast enough that the result feels clearly strong, not merely acceptable

## Sampled Runs

| # | GPU | Model | Current Verdict | Subjective Verdict | Key Observations |
| --- | --- | --- | --- | --- | --- |
| 1 | NVIDIA RTX A5000 | `openai/gpt-oss-20b@mxfp4` | `TIGHT FIT` | `RUNS WELL` | `safe_context=50104`, `decode=64.26 tps`, `headroom=1.81 GB`. Feels conservative. |
| 2 | NVIDIA GeForce RTX 4090 | `Qwen/Qwen3-32B-GGUF@q4_k_m` | `TOO HEAVY` | `TIGHT FIT` | `safe_context=3114`, `decode=55.38 tps`. This looks runnable but clearly tight, not "too heavy". |
| 3 | NVIDIA A40 GPU accelerator (PCIe card) | `Qwen/Qwen2-57B-A14B-Instruct-GGUF@q4_k_m` | `TIGHT FIT` | `TIGHT FIT` | `safe_context=4539`, `decode=21.82 tps`. Result feels reasonable. |
| 4 | NVIDIA A30 GPU accelerator (PCIe card) | `Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4@gptq-4bit` | `TIGHT FIT` | `RUNS GREAT` | `safe_context=15390`, `decode=113.72 tps`. Current verdict is much too pessimistic. |
| 5 | NVIDIA L40 GPU accelerator | `Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4@gptq-4bit` | `TIGHT FIT` | `RUNS WELL` | `safe_context=13191`, `decode=47.47 tps`, `headroom=4.34 GB`. Feels stronger than `TIGHT FIT`. |
| 6 | NVIDIA GeForce RTX 3060 | `Qwen/Qwen2-57B-A14B-Instruct-GGUF@q4_k_m` | `IMPOSSIBLE` | `IMPOSSIBLE` | Weight estimate alone already overruns VRAM by a wide margin. |
| 7 | NVIDIA L4 GPU accelerator | `Qwen/Qwen2-57B-A14B-Instruct-GGUF@q4_k_m` | `IMPOSSIBLE` | `IMPOSSIBLE` | Same basic story as case 6. |
| 8 | NVIDIA RTX 6000 Ada Generation | `Qwen/Qwen2.5-14B@bf16` | `TIGHT FIT` | `RUNS GREAT` | `48 GB` Ada workstation card running `14B bf16` should feel easy. Current result is notably pessimistic. |
| 9 | NVIDIA RTX 5000 Ada Generation | `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8@fp8` | `IMPOSSIBLE` | `TIGHT FIT` | Current scorer says `safe_context=192`, which is harsh. Subjectively this looks like "barely okay" rather than flat impossible. |
| 10 | NVIDIA RTX A6000 | `Qwen/Qwen2.5-32B@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | `weights_vram_gb=61.03` on a `48 GB` card. This is a clear miss-fit. |
| 11 | NVIDIA RTX A6000 | `mistralai/Devstral-Small-2507_gguf@q4_k_m` | `RUNS GREAT` | `RUNS GREAT` | `safe_context=21049`, `decode=58.64 tps`. Looks aligned. |
| 12 | NVIDIA RTX A6000 | `Qwen/Qwen2-57B-A14B-Instruct-GPTQ-Int4@gptq-4bit` | `TIGHT FIT` | `TIGHT FIT` | `safe_context=4535`, `decode=24.07 tps`. Borderline but plausible. |
| 13 | NVIDIA RTX A5000 | `Qwen/Qwen3-Next-80B-A3B-Instruct@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | `weights_vram_gb=151.5`. The result is correct. |
| 14 | NVIDIA GeForce RTX 3060 | `mistralai/Devstral-Small-2507_gguf@q4_k_m` | `IMPOSSIBLE` | `TOO HEAVY` | `safe_context=39`, `decode=27.49 tps`, `headroom=0.01 GB`. Technically almost loadable, but practically awful. |
| 15 | NVIDIA L4 GPU accelerator | `Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4@gptq-4bit` | `TIGHT FIT` | `RUNS WELL` | `safe_context=15390`, `decode=36.56 tps`. Feels better than the current label. |
| 16 | NVIDIA A10 GPU accelerator (PCIe card) | `Qwen/Qwen3-Next-80B-A3B-Instruct@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | Obvious VRAM miss-fit. |
| 17 | NVIDIA RTX A6000 | `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8@fp8` | `TIGHT FIT` | `RUNS WELL` | `safe_context=7401`, `decode=22.16 tps`. Reasonably usable in practice. |
| 18 | NVIDIA RTX A5000 | `Qwen/Qwen2.5-32B@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | `61 GB` weights on `24 GB` VRAM. Correct. |
| 19 | NVIDIA GeForce RTX 5090 | `Qwen/Qwen3-Coder-Next@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | `148.42 GB` weights on `32 GB` VRAM. Correct. |
| 20 | NVIDIA L40 GPU accelerator | `Qwen/Qwen3-14B-AWQ@awq-4bit` | `RUNS GREAT` | `RUNS GREAT` | `safe_context=37749`, `decode=105.31 tps`. Looks aligned. |

## Summary

### Match Rate

- exact match: `11 / 20`
- different by one verdict level: `6 / 20`
- different by two verdict levels: `3 / 20`

### Cases That Look Most Suspicious

- Case 4: `A30 24 GB + Qwen2.5-14B GPTQ Int4`
  - current: `TIGHT FIT`
  - subjective: `RUNS GREAT`
- Case 8: `RTX 6000 Ada 48 GB + Qwen2.5-14B bf16`
  - current: `TIGHT FIT`
  - subjective: `RUNS GREAT`
- Case 9: `RTX 5000 Ada 32 GB + Qwen3-Coder-30B FP8`
  - current: `IMPOSSIBLE`
  - subjective: `TIGHT FIT`

These were the clearest "this feels too pessimistic" outputs.

## What Looks Wrong

### 1. The `TIGHT FIT` gate is too aggressive

The current verdict logic marks any otherwise-loadable setup as `TIGHT FIT` whenever VRAM headroom falls below `10%`:

- [verdict.py](/home/kuseo/toy/can-i-run-ai/src/canirunai/scoring/verdict.py#L20)

This is the biggest reason why many very usable runs still collapse to `TIGHT FIT`.

Examples:

- case 4: `A30 + 14B GPTQ Int4`
  - `15390` safe tokens
  - `113.72 tps`
  - still only `TIGHT FIT`
- case 15: `L4 + 14B GPTQ Int4`
  - `15390` safe tokens
  - `36.56 tps`
  - still only `TIGHT FIT`
- case 5: `L40 + 32B GPTQ Int4`
  - `13191` safe tokens
  - `47.47 tps`
  - still only `TIGHT FIT`

In all three, the headroom number is small, but the overall user experience would not usually be described as merely "tight".

### 2. RTX / workstation Ada low-precision compute looks under-modeled

Some current catalog entries show no meaningful uplift from FP32 to FP16/BF16 on GPUs that, in practice, should benefit heavily from tensor-core-style low-precision inference.

Examples from the current catalog:

- [gpu.json](/home/kuseo/toy/can-i-run-ai/data/specs/gpu.json#L34415)
  - `NVIDIA RTX 5000 Ada Generation`
  - `processing_power_fp32_gflops = 65280.0`
  - `processing_power_fp16_gflops = 65280.0`
- [gpu.json](/home/kuseo/toy/can-i-run-ai/data/specs/gpu.json#L34487)
  - `NVIDIA RTX 6000 Ada Generation`
  - `processing_power_fp32_gflops = 91060.0`
  - `processing_power_fp16_gflops = 91060.0`
- [gpu.json](/home/kuseo/toy/can-i-run-ai/data/specs/gpu.json#L34823)
  - `NVIDIA RTX A5000`
  - `processing_power_fp32_gflops = 27770.0`
  - `processing_power_fp16_gflops = 27770.0`

By contrast, some accelerator entries do show large low-precision uplift:

- [gpu.json](/home/kuseo/toy/can-i-run-ai/data/specs/gpu.json#L17409)
  - `NVIDIA A30 GPU accelerator (PCIe card)`
  - `fp32 = 10320.0`
  - `fp16 = 165100.0`
- [gpu.json](/home/kuseo/toy/can-i-run-ai/data/specs/gpu.json#L28663)
  - `NVIDIA L4 GPU accelerator`
  - `fp32 = 30300.0`
  - `fp16 = 121000.0`
- [gpu.json](/home/kuseo/toy/can-i-run-ai/data/specs/gpu.json#L28685)
  - `NVIDIA L40 GPU accelerator`
  - `fp32 = 90520.0`
  - `fp16 = 362100.0`

This inconsistency strongly suggests that the catalog is still missing or under-extracting low-precision tensor-style metrics for some RTX / workstation parts.

That directly affects cases like:

- case 8: `RTX 6000 Ada + 14B bf16`
- case 9: `RTX 5000 Ada + 30B fp8`

### 3. The `IMPOSSIBLE` cutoff for very small safe context is policy-heavy

Current logic says:

- if `safe_context_tokens < 2048`, return `IMPOSSIBLE`
- if `safe_context_tokens < 4096`, return `TOO HEAVY`

Reference:

- [verdict.py](/home/kuseo/toy/can-i-run-ai/src/canirunai/scoring/verdict.py#L16)

This makes the verdict language much harsher than the physical fit result.

Examples:

- case 9: `RTX 5000 Ada + 30B fp8`
  - current safe context: `192`
  - current verdict: `IMPOSSIBLE`
  - subjective reading: it is much closer to "extremely tight and probably not worth it" than to "flat impossible"
- case 14: `RTX 3060 + Devstral Small q4_k_m`
  - current safe context: `39`
  - current verdict: `IMPOSSIBLE`
  - subjective reading: "technically starts, practically bad"

The current label collapses "cannot load at all" and "can only run at toy context" into the same bucket too early.

## What Should Be Changed First

### 1. Rework verdict ordering before changing the estimator again

First priority should be verdict policy, not raw throughput math.

The current decision tree should not force `TIGHT FIT` before checking whether context and throughput are already clearly strong.

The simplest direction:

- keep `IMPOSSIBLE` for true no-fit cases
- keep `TOO HEAVY` for very small context or very low speed
- only use `TIGHT FIT` when both:
  - headroom is tight
  - and context / speed are not already clearly comfortable

### 2. Improve low-precision GPU catalog quality for RTX / Ada / RTX A family

The next priority should be GPU spec quality, especially for:

- RTX Ada workstation
- RTX A-series
- GeForce RTX where tensor / TOPS style columns are present but not yet reflected as strong FP16 / BF16 / FP8 capability

Without this, the scorer will keep undervaluing many practical low-precision inference setups.

### 3. Consider splitting "barely loads" from "impossible"

The current verdict vocabulary is missing a category between:

- true no-fit
- technically fit but unusable for real work

If the current five verdicts must remain, `TOO HEAVY` should probably absorb more of those "toy context but technically fit" cases.

## Bottom Line

The current scorer is directionally sane on obvious no-fit cases. It correctly rejects many large `bf16` setups on `24 GB` to `48 GB` cards.

The main weakness is not catastrophic false positives. The main weakness is pessimism on genuinely usable low-precision runs, especially when:

- the GPU is tensor-core capable but the catalog lacks strong low-precision metrics
- the setup has very good context and TPS but low VRAM headroom
- the setup technically fits but only at small context, which is currently labeled too harshly

In short:

- obvious `IMPOSSIBLE` cases are mostly fine
- usable quantized runs are often graded too conservatively
- the next fixes should focus on verdict policy and GPU low-precision spec quality, not only on more compute math
