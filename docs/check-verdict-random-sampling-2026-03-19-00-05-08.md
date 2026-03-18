# Random Sampling Review Of `check` Verdicts

Date: 2026-03-19 00:05:08 KST
Git commit: `33b9479db359613116398fcda2bebbd5732f390d` (with local uncommitted changes)

## Scope

This note records a second manual review of roughly 20 randomly sampled `check` runs using:

- NVIDIA RTX / A / L / H series GPUs from the current local GPU catalog
- models in the current local model catalog with roughly `14B` to `120B` parameters
- a very large host memory setting (`--memory 512`) so that host RAM does not dominate the result
- a very large CPU (`AMD 9995WX`) so that CPU threads do not dominate the result

This pass was run after applying two scorer changes:

1. verdict policy was relaxed so that strong runs with low headroom are no longer forced into `TIGHT FIT`
2. NVIDIA low-precision compute fallback was added when catalog values are flat or obviously incomplete

The goal was the same as the previous report:

1. compare the current code's verdict
2. compare that result against a subjective, operator-style verdict based on typical single-GPU local inference expectations

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

Random sampling was generated with the same seed as the earlier report: `20260318`.

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
| 1 | NVIDIA RTX A5000 | `openai/gpt-oss-20b@mxfp4` | `RUNS WELL` | `RUNS WELL` | `safe_context=50104`, `decode=64.26 tps`, `headroom=1.81 GB`. Now aligned. |
| 2 | NVIDIA GeForce RTX 4090 | `Qwen/Qwen3-32B-GGUF@q4_k_m` | `TIGHT FIT` | `TIGHT FIT` | `safe_context=3114`, `decode=55.38 tps`. Now aligned. |
| 3 | NVIDIA A40 GPU accelerator (PCIe card) | `Qwen/Qwen2-57B-A14B-Instruct-GGUF@q4_k_m` | `TIGHT FIT` | `TIGHT FIT` | `safe_context=4539`, `decode=21.82 tps`. Still reasonable. |
| 4 | NVIDIA A30 GPU accelerator (PCIe card) | `Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4@gptq-4bit` | `RUNS WELL` | `RUNS GREAT` | `safe_context=15390`, `decode=113.72 tps`. Improved by one full verdict level. |
| 5 | NVIDIA L40 GPU accelerator | `Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4@gptq-4bit` | `RUNS WELL` | `RUNS WELL` | `safe_context=13191`, `decode=47.47 tps`, `headroom=4.34 GB`. Now aligned. |
| 6 | NVIDIA GeForce RTX 3060 | `Qwen/Qwen2-57B-A14B-Instruct-GGUF@q4_k_m` | `IMPOSSIBLE` | `IMPOSSIBLE` | Still a clear VRAM miss-fit. |
| 7 | NVIDIA L4 GPU accelerator | `Qwen/Qwen2-57B-A14B-Instruct-GGUF@q4_k_m` | `IMPOSSIBLE` | `IMPOSSIBLE` | Still a clear VRAM miss-fit. |
| 8 | NVIDIA RTX 6000 Ada Generation | `Qwen/Qwen2.5-14B@bf16` | `RUNS WELL` | `RUNS GREAT` | `safe_context=16839`, `decode=29.23 tps`. Better than before, still slightly conservative. |
| 9 | NVIDIA RTX 5000 Ada Generation | `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8@fp8` | `TOO HEAVY` | `TIGHT FIT` | `safe_context=192`, `decode=16.62 tps`. Improvement from `IMPOSSIBLE`, but still a bit harsh. |
| 10 | NVIDIA RTX A6000 | `Qwen/Qwen2.5-32B@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | `weights_vram_gb=61.03` on `48 GB` VRAM. Correct. |
| 11 | NVIDIA RTX A6000 | `mistralai/Devstral-Small-2507_gguf@q4_k_m` | `RUNS GREAT` | `RUNS GREAT` | Strong alignment remains. |
| 12 | NVIDIA RTX A6000 | `Qwen/Qwen2-57B-A14B-Instruct-GPTQ-Int4@gptq-4bit` | `TIGHT FIT` | `TIGHT FIT` | Borderline but plausible. |
| 13 | NVIDIA RTX A5000 | `Qwen/Qwen3-Next-80B-A3B-Instruct@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | Still correct. |
| 14 | NVIDIA GeForce RTX 3060 | `mistralai/Devstral-Small-2507_gguf@q4_k_m` | `TOO HEAVY` | `TOO HEAVY` | `safe_context=39`, `decode=27.49 tps`. Now aligned. |
| 15 | NVIDIA L4 GPU accelerator | `Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4@gptq-4bit` | `RUNS WELL` | `RUNS WELL` | `safe_context=15390`, `decode=36.56 tps`. Now aligned. |
| 16 | NVIDIA A10 GPU accelerator (PCIe card) | `Qwen/Qwen3-Next-80B-A3B-Instruct@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | Still correct. |
| 17 | NVIDIA RTX A6000 | `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8@fp8` | `RUNS WELL` | `RUNS WELL` | `safe_context=7401`, `decode=22.16 tps`. Now aligned. |
| 18 | NVIDIA RTX A5000 | `Qwen/Qwen2.5-32B@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | Still correct. |
| 19 | NVIDIA GeForce RTX 5090 | `Qwen/Qwen3-Coder-Next@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | Still correct. |
| 20 | NVIDIA L40 GPU accelerator | `Qwen/Qwen3-14B-AWQ@awq-4bit` | `RUNS GREAT` | `RUNS GREAT` | Strong alignment remains. |

## Summary

### Match Rate

- exact match: `17 / 20`
- different by one verdict level: `3 / 20`
- different by two verdict levels: `0 / 20`

Compared with the previous pass:

- exact match improved from `11 / 20` to `17 / 20`
- two-level mismatches dropped from `3` to `0`

### Cases That Still Look Slightly Off

- Case 4: `A30 24 GB + Qwen2.5-14B GPTQ Int4`
  - current: `RUNS WELL`
  - subjective: `RUNS GREAT`
- Case 8: `RTX 6000 Ada 48 GB + Qwen2.5-14B bf16`
  - current: `RUNS WELL`
  - subjective: `RUNS GREAT`
- Case 9: `RTX 5000 Ada 32 GB + Qwen3-Coder-30B FP8`
  - current: `TOO HEAVY`
  - subjective: `TIGHT FIT`

None of these remaining gaps look catastrophic. All three are one-step disagreements.

## What Improved

### 1. Verdict policy is now much closer to operator expectations

The biggest improvement came from changing verdict ordering and softening the old `TIGHT FIT` gate:

- [verdict.py](/home/kuseo/toy/can-i-run-ai/src/canirunai/scoring/verdict.py)

The current logic now:

- reserves `IMPOSSIBLE` for true no-fit cases
- uses `TOO HEAVY` for loadable-but-tiny-context cases
- allows strong low-headroom runs to land in `RUNS WELL`

This change directly fixed the most obvious mismatches from the first report:

- case 1: `A5000 + gpt-oss-20b`
  - `TIGHT FIT -> RUNS WELL`
- case 4: `A30 + 14B GPTQ Int4`
  - `TIGHT FIT -> RUNS WELL`
- case 5: `L40 + 32B GPTQ Int4`
  - `TIGHT FIT -> RUNS WELL`
- case 14: `RTX 3060 + Devstral Small q4_k_m`
  - `IMPOSSIBLE -> TOO HEAVY`
- case 15: `L4 + 14B GPTQ Int4`
  - `TIGHT FIT -> RUNS WELL`
- case 17: `RTX A6000 + 30B FP8`
  - `TIGHT FIT -> RUNS WELL`

### 2. The harsh "tiny context = impossible" behavior is gone

The previous report flagged that the scorer was collapsing "true no-fit" and "technically fits but barely usable" too aggressively.

That gap is now better reflected in the outputs:

- case 9: `RTX 5000 Ada + 30B FP8`
  - `IMPOSSIBLE -> TOO HEAVY`
- case 14: `RTX 3060 + Devstral Small q4_k_m`
  - `IMPOSSIBLE -> TOO HEAVY`

This is a meaningful improvement even though these are still not "good" runs.

### 3. Low-precision NVIDIA fallback is now present, but did not dominate this sample set

The scorer now derives low-precision tensor-style throughput for NVIDIA tensor-core GPUs when catalog values are flat or suspicious:

- [llm_estimator.py](/home/kuseo/toy/can-i-run-ai/src/canirunai/scoring/llm_estimator.py)

However, in this exact 20-sample run, most disputed cases were still dominated by:

- VRAM headroom
- weight size
- memory bandwidth

not by compute throughput.

So the low-precision fallback is still a useful change, but it was not the main reason the sample-level verdicts improved. The verdict policy change mattered much more in this specific review pass.

## What Still Looks Wrong

### 1. Some strong `RUNS GREAT` candidates are still capped at `RUNS WELL`

Cases 4 and 8 still feel a little conservative:

- case 4: `A30 + 14B GPTQ Int4`
  - `15390` safe tokens
  - `113.72 tps`
- case 8: `RTX 6000 Ada + 14B bf16`
  - `16839` safe tokens
  - `29.23 tps`

The scorer is now much closer, but it still treats these as merely "well" rather than clearly great.

This is mostly a policy question now, not a catastrophic estimator bug.

### 2. RTX / workstation low-precision catalog quality is still not fully repaired

The fallback logic helps, but the underlying catalog still contains flat-looking low-precision values for some RTX / workstation parts.

Examples that remain suspicious:

- [gpu.json](/home/kuseo/toy/can-i-run-ai/data/specs/gpu.json#L34415)
  - `NVIDIA RTX 5000 Ada Generation`
  - `processing_power_fp16_gflops = 65280.0`
  - same as FP32
- [gpu.json](/home/kuseo/toy/can-i-run-ai/data/specs/gpu.json#L34487)
  - `NVIDIA RTX 6000 Ada Generation`
  - `processing_power_fp16_gflops = 91060.0`
  - same as FP32
- [gpu.json](/home/kuseo/toy/can-i-run-ai/data/specs/gpu.json#L34823)
  - `NVIDIA RTX A5000`
  - `processing_power_fp16_gflops = 27770.0`
  - same as FP32

That means the runtime behavior is improved, but the source catalog is still weaker than it should be.

## What Should Be Changed Next

### 1. Improve the underlying GPU catalog, not only scorer fallback

The next step should be to improve live parsing or post-processing so that more RTX / Ada / RTX A cards carry realistic low-precision tensor metrics directly in the catalog.

That would make the scorer less heuristic and easier to reason about.

### 2. Revisit the `RUNS WELL` vs `RUNS GREAT` policy boundary

The remaining disagreements are mostly "good versus great" disagreements.

If the project wants `RUNS GREAT` to mean "fast and comfortable even if headroom is only modest", then the top-end boundary should be loosened a little more.

If the project wants `RUNS GREAT` to mean "fast, comfortable, and clearly roomy", then the current output is already defensible.

### 3. Consider surfacing "tiny context fit" more explicitly

The current five-way vocabulary is much better than before, but a run like case 9 still compresses several ideas into one label:

- it fits
- it is not truly impossible
- it still feels borderline for practical use

If the vocabulary must remain unchanged, the current `TOO HEAVY` result is acceptable. If richer semantics are wanted later, a dedicated "barely fits" or "limited context" presentation would help.

## Bottom Line

This second pass is materially better than the first one.

- obvious no-fit cases still come out as `IMPOSSIBLE`
- previously over-pessimistic quantized runs are now much closer to human expectations
- the remaining disagreements are small, policy-shaped disagreements, not severe misclassifications

In short:

- the verdict-policy fix had clear practical impact
- the NVIDIA low-precision fallback is in place, but this sample set was mostly not compute-bound enough to showcase it strongly
- the next high-value work is catalog quality for RTX / Ada / RTX A low-precision metrics, plus a final pass on the `RUNS WELL` vs `RUNS GREAT` boundary
