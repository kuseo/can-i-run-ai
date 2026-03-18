# Random Sampling Review Of `check` Verdicts

Date: 2026-03-19 00:17:03 KST
Git commit: `2e77e1e632f24b8bc99006a895126dc8944c0fc2` (with local uncommitted changes)

## Scope

This note records a third manual review of roughly 20 randomly sampled `check` runs using:

- NVIDIA RTX / A / L / H series GPUs from the current local GPU catalog
- models in the current local model catalog with roughly `14B` to `120B` parameters
- a very large host memory setting (`--memory 512`) so that host RAM does not dominate the result
- a very large CPU (`AMD 9995WX`) so that CPU threads do not dominate the result

This pass was run after applying the next round of scorer and catalog fixes suggested by the previous report:

1. strong low-headroom runs can now reach `RUNS GREAT` when context, throughput, and absolute VRAM headroom are already clearly strong
2. NVIDIA low-precision compute normalization moved closer to catalog reality instead of being only a scorer-time fallback
3. current local GPU catalog entries were rewritten through the loader so normalized low-precision fields are now persisted in [`gpu.json`](/home/kuseo/toy/can-i-run-ai/data/specs/gpu.json)

The goal remained the same:

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

Random sampling was generated with the same seed as the earlier two reports: `20260318`.

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
| 1 | NVIDIA RTX A5000 | `openai/gpt-oss-20b@mxfp4` | `RUNS WELL` | `RUNS WELL` | `safe_context=50104`, `decode=64.26 tps`, `headroom=1.81 GB`. Still aligned. |
| 2 | NVIDIA GeForce RTX 4090 | `Qwen/Qwen3-32B-GGUF@q4_k_m` | `TIGHT FIT` | `TIGHT FIT` | `safe_context=3114`, `decode=55.38 tps`. Still aligned. |
| 3 | NVIDIA A40 GPU accelerator (PCIe card) | `Qwen/Qwen2-57B-A14B-Instruct-GGUF@q4_k_m` | `TIGHT FIT` | `TIGHT FIT` | `safe_context=4539`, `decode=21.82 tps`. Still aligned. |
| 4 | NVIDIA A30 GPU accelerator (PCIe card) | `Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4@gptq-4bit` | `RUNS GREAT` | `RUNS GREAT` | `safe_context=15390`, `decode=113.72 tps`, `headroom=2.28 GB`. Now fully aligned. |
| 5 | NVIDIA L40 GPU accelerator | `Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4@gptq-4bit` | `RUNS WELL` | `RUNS WELL` | `safe_context=13191`, `decode=47.47 tps`, `headroom=4.34 GB`. Still aligned. |
| 6 | NVIDIA GeForce RTX 3060 | `Qwen/Qwen2-57B-A14B-Instruct-GGUF@q4_k_m` | `IMPOSSIBLE` | `IMPOSSIBLE` | Still a clear VRAM miss-fit. |
| 7 | NVIDIA L4 GPU accelerator | `Qwen/Qwen2-57B-A14B-Instruct-GGUF@q4_k_m` | `IMPOSSIBLE` | `IMPOSSIBLE` | Still a clear VRAM miss-fit. |
| 8 | NVIDIA RTX 6000 Ada Generation | `Qwen/Qwen2.5-14B@bf16` | `RUNS WELL` | `RUNS GREAT` | `safe_context=16839`, `decode=29.23 tps`, `headroom=2.5 GB`. Still slightly conservative. |
| 9 | NVIDIA RTX 5000 Ada Generation | `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8@fp8` | `TOO HEAVY` | `TIGHT FIT` | `safe_context=192`, `decode=16.62 tps`, `headroom=0.06 GB`. Borderline but no longer impossible. |
| 10 | NVIDIA RTX A6000 | `Qwen/Qwen2.5-32B@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | `weights_vram_gb=61.03` on `48 GB` VRAM. Correct. |
| 11 | NVIDIA RTX A6000 | `mistralai/Devstral-Small-2507_gguf@q4_k_m` | `RUNS GREAT` | `RUNS GREAT` | Strong alignment remains. |
| 12 | NVIDIA RTX A6000 | `Qwen/Qwen2-57B-A14B-Instruct-GPTQ-Int4@gptq-4bit` | `TIGHT FIT` | `TIGHT FIT` | Borderline but plausible. |
| 13 | NVIDIA RTX A5000 | `Qwen/Qwen3-Next-80B-A3B-Instruct@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | Still correct. |
| 14 | NVIDIA GeForce RTX 3060 | `mistralai/Devstral-Small-2507_gguf@q4_k_m` | `TOO HEAVY` | `TOO HEAVY` | `safe_context=39`, `decode=27.49 tps`. Still aligned. |
| 15 | NVIDIA L4 GPU accelerator | `Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4@gptq-4bit` | `RUNS WELL` | `RUNS WELL` | `safe_context=15390`, `decode=36.56 tps`. Still aligned. |
| 16 | NVIDIA A10 GPU accelerator (PCIe card) | `Qwen/Qwen3-Next-80B-A3B-Instruct@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | Still correct. |
| 17 | NVIDIA RTX A6000 | `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8@fp8` | `RUNS WELL` | `RUNS WELL` | `safe_context=7401`, `decode=22.16 tps`. Still aligned. |
| 18 | NVIDIA RTX A5000 | `Qwen/Qwen2.5-32B@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | Still correct. |
| 19 | NVIDIA GeForce RTX 5090 | `Qwen/Qwen3-Coder-Next@bf16` | `IMPOSSIBLE` | `IMPOSSIBLE` | Still correct. |
| 20 | NVIDIA L40 GPU accelerator | `Qwen/Qwen3-14B-AWQ@awq-4bit` | `RUNS GREAT` | `RUNS GREAT` | Strong alignment remains. |

## Summary

### Match Rate

- exact match: `18 / 20`
- different by one verdict level: `2 / 20`
- different by two verdict levels: `0 / 20`

Compared with the previous pass:

- exact match improved from `17 / 20` to `18 / 20`
- one-level mismatches dropped from `3` to `2`
- two-level mismatches remain at `0`

Compared with the original pass:

- exact match improved from `11 / 20` to `18 / 20`
- two-level mismatches dropped from `3` to `0`

### Cases That Still Look Slightly Off

- Case 8: `RTX 6000 Ada 48 GB + Qwen2.5-14B bf16`
  - current: `RUNS WELL`
  - subjective: `RUNS GREAT`
- Case 9: `RTX 5000 Ada 32 GB + Qwen3-Coder-30B FP8`
  - current: `TOO HEAVY`
  - subjective: `TIGHT FIT`

Both remaining gaps are one-step disagreements.

## What Improved

### 1. Strong low-headroom runs can now graduate to `RUNS GREAT`

The previous pass still capped some obviously strong runs at `RUNS WELL` because the headroom policy remained a little too strict.

That boundary is now softer in:

- [verdict.py](/home/kuseo/toy/can-i-run-ai/src/canirunai/scoring/verdict.py)
- [engine.py](/home/kuseo/toy/can-i-run-ai/src/canirunai/scoring/engine.py)

This directly fixed the most visible remaining disagreement from the second report:

- case 4: `A30 + 14B GPTQ Int4`
  - `RUNS WELL -> RUNS GREAT`

The new behavior is closer to operator expectations when:

- safe context is already large
- decode speed is already clearly strong
- VRAM headroom ratio is tight, but absolute headroom is still not tiny

### 2. NVIDIA low-precision uplift is now normalized closer to the catalog boundary

The previous pass improved low-precision handling mostly inside the scorer.

This pass moved that logic into a shared helper and applied it consistently through:

- [gpu_compute.py](/home/kuseo/toy/can-i-run-ai/src/canirunai/gpu_compute.py)
- [gpu_loader.py](/home/kuseo/toy/can-i-run-ai/src/canirunai/loaders/gpu_loader.py)
- [gpu_wikipedia.py](/home/kuseo/toy/can-i-run-ai/src/canirunai/collectors/gpu_wikipedia.py)
- [llm_estimator.py](/home/kuseo/toy/can-i-run-ai/src/canirunai/scoring/llm_estimator.py)

That means:

- flat RTX / Ada low-precision fields are normalized when loaded
- new GPU updates also get the same normalization path
- scorer behavior is less dependent on one late fallback branch

### 3. The current local GPU catalog has been brought closer to the new rules

After applying the normalization path, the current local catalog was re-saved through the SDK loader/store path. That means this pass did not only change runtime scoring code; it also changed the local data used by later `check` runs.

This reduces the gap between:

- "what the scorer internally assumes"
- and "what `data/specs/gpu.json` actually stores"

## What Still Looks Wrong

### 1. Some 48 GB Ada workstation runs still feel slightly conservative

Case 8 remains the clearest example:

- `RTX 6000 Ada + Qwen2.5-14B@bf16`
- `safe_context=16839`
- `decode=29.23 tps`
- current verdict: `RUNS WELL`
- subjective verdict: `RUNS GREAT`

This no longer looks like a serious estimator failure. It looks more like a final policy choice about where the project wants the `RUNS GREAT` bar to sit for strong-but-not-roomy workstation runs.

### 2. Tiny-context FP8 runs are still hard to label cleanly

Case 9 remains borderline:

- `RTX 5000 Ada + Qwen3-Coder-30B FP8`
- `safe_context=192`
- `decode=16.62 tps`
- `headroom=0.06 GB`

The current `TOO HEAVY` result is defensible. Subjectively, it still feels slightly closer to `TIGHT FIT` than to "do not bother", but this is now a semantics question much more than a raw fit bug.

## What Should Be Changed Next

### 1. Tighten Ada workstation low-precision sources at the catalog level

The normalization helper is useful, but it is still heuristic.

The next quality jump should come from storing better low-precision metrics directly in live-collected GPU specs, especially for:

- RTX 5000 Ada
- RTX 6000 Ada
- RTX A-series workstation parts

That would make results easier to explain and reduce dependence on name-based or architecture-based inference.

### 2. Decide whether `RUNS GREAT` should mean "clearly strong" or "clearly roomy"

The remaining mismatch in case 8 is mostly a policy decision now.

If `RUNS GREAT` means:

- strong context
- strong TPS
- and acceptable absolute headroom

then the current threshold can be loosened a little more.

If `RUNS GREAT` means:

- strong context
- strong TPS
- and clearly comfortable VRAM margin

then the present output is already coherent.

### 3. Keep tiny-context runs distinct from true no-fit runs

The current result set is much better than the first pass because "barely fits" no longer collapses into `IMPOSSIBLE` as often.

That distinction should be preserved in later changes. The current `TOO HEAVY` label for borderline loadable runs is not perfect, but it is materially better than treating them as true no-fit cases.

## Bottom Line

This third pass is better than the second pass, and much better than the original baseline.

- exact agreement is now `18 / 20`
- all remaining disagreements are one-step disagreements
- the biggest practical improvement came from combining a softer high-end verdict boundary with persistent NVIDIA low-precision metric normalization

In short:

- the code changes from the second report were worth applying
- the current scorer is now much closer to operator intuition on single-GPU quantized and low-precision runs
- the remaining work is mostly catalog quality and final verdict semantics, not a major modeling failure
