# Vibe Coding Improvement Scenarios

## Purpose

This note summarizes the user-driven "vibe coding" scenarios that shaped `canirunai` after the initial SDK implementation.

The goal is not to provide a full changelog. The goal is to show how practical prompts, complaints, and sanity checks from a human operator pushed the project toward better real-world behavior.

In this project, "vibe coding" mostly meant this loop:

1. a user tried a realistic `canirunai check` or `update` scenario
2. the result felt wrong or incomplete
3. the implementation was adjusted to better match practical operator expectations
4. the change was validated with tests, QA commands, or sampling reviews

## Baseline

The first SDK version already had:

- `update`, `list`, `get`, and `check` commands
- JSON-backed CPU / GPU / model catalogs
- live collection scaffolding
- a heuristic scorer for loadability, context, throughput, and verdicts

The major follow-up work did not come from a single design rewrite. It came from repeated concrete prompts about:

- live parsing quality
- Hugging Face variant quality
- GPU low-precision metrics
- verdict harshness
- whether the output matched how people actually talk about "this GPU can run that model"

## Main Scenarios

### 1. "Live update should be real, not just seed fallback"

The first major request was to start implementing true live `update` behavior instead of mostly relying on offline seed data.

That led to:

- deterministic Wikipedia table parsing for CPU / GPU specs
- live Hugging Face model collection
- raw source caching and structured parsing flow

This set the foundation for later performance work, because poor source data produces poor scoring no matter how good the scorer is.

Related docs:

- [Spec Collection](/home/kuseo/toy/can-i-run-ai/docs/implementation/spec-collection.md)

### 2. "Use rule-based parsing first, only use LLM parsing on failure"

The next strong user instruction was that parsing should not default to an LLM if a normal parser is realistic.

That pushed the implementation toward:

- HTML table parsing with `rowspan` / `colspan` support
- header-based table selection
- field extraction with deterministic rules
- explicit documentation that LLM parsing is fallback-only

This mattered for performance work because deterministic parsing made the catalog more stable and debuggable.

### 3. "Hugging Face variants like `@unknown` are not good enough"

Once live collection existed, the next complaint was not about the CLI surface. It was about the usefulness of the collected model specs.

That drove improvements such as:

- inferring precision from `safetensors` metadata
- reading quantization from `config.quantization_config`
- deriving runtime weight size for low-bit variants
- splitting GGUF repositories into multiple concrete variants such as `@q4_k_m`

This was a practical performance improvement, because scorer quality depends heavily on accurate model format and quantization information.

### 4. "Wikipedia parsing still misses or over-includes tables"

After live collection started working, the next user-driven scenario was parser quality tuning.

Typical complaints were:

- some tables were over-selected
- some rows were clearly not real products
- some metric cells were parsed incorrectly

That led to:

- stricter Wikipedia table selection
- better row filtering
- better unit-aware parsing for memory, bandwidth, and compute
- improved name normalization

This improved the underlying GPU catalog, which later reduced scoring noise.

### 5. "Run QA against real `check` commands, not just unit tests"

The next important scenario was a request to run many `check` commands against the updated local catalogs and record whether the outputs looked right.

That shifted the project from "the code runs" to "the answers look believable."

Related doc:

- [QA Check Report](/home/kuseo/toy/can-i-run-ai/docs/qa/qa-check-report.md)

One immediate effect of that QA style was that catalog problems became much easier to spot than they would have been from code inspection alone.

### 6. "H100 should not say `IMPOSSIBLE` for `gpt-oss-20b`"

This was one of the clearest vibe-coding moments in the project.

A user ran a realistic command with:

- `NVIDIA H100 GPU accelerator (PCIe card)`
- `openai/gpt-oss-20b@mxfp4`

and pointed out that `IMPOSSIBLE` was obviously wrong.

That led to scorer fixes for:

- `gpt-oss` active-parameter behavior
- MXFP4 runtime weight handling
- KV cache fallback when full architecture metadata is missing

This was not a purely theoretical improvement. It corrected a concrete mismatch between scorer output and common operator expectations for an H100-class GPU.

### 7. "Single precision is not enough for modern LLM GPU scoring"

After the H100 discussion, the next realization was that using only one generic GPU compute field was too weak for modern inference scoring.

The user explicitly pushed toward a better direction: use low-precision compute information rather than treating everything as FP32-like.

That led to:

- adding low-precision GPU fields such as FP16 / BF16 / FP8 / INT8
- making the scorer choose different compute metrics depending on the model variant
- separating the current schema meaning from raw Wikipedia column names

This did not make the scorer perfect, but it was a major step toward matching how real inference hardware is used.

### 8. "RTX / Ada workstation cards still feel under-modeled"

Once low-precision fields existed, the next problem was not the presence of those fields. It was their quality.

Some RTX / Ada cards still had flat-looking low-precision values that were effectively no better than FP32 in the catalog.

That led to:

- heuristic NVIDIA low-precision uplift logic
- architecture-aware normalization
- moving that normalization into shared loader-side logic
- rewriting the local GPU catalog through the normalized path

This was a classic vibe-coding improvement: a user did not ask for a new abstraction. The user noticed that the answers still felt wrong, especially on modern workstation GPUs, and the implementation was pushed closer to real hardware intuition.

### 9. "Verdicts are too harsh even when the run is obviously usable"

Another repeated pattern was that users cared about the label as much as the raw numbers.

Examples:

- runs with strong context and high decode throughput were still marked `TIGHT FIT`
- tiny-context but technically loadable runs were being collapsed into `IMPOSSIBLE`

That led to several verdict-policy changes:

- reserve `IMPOSSIBLE` for true no-fit cases
- use `TOO HEAVY` for "technically loadable but poor practical value"
- allow some strong low-headroom runs to rise to `RUNS WELL` or `RUNS GREAT`

This was important because the project is partly a communication tool. A mathematically consistent score is still bad if the headline verdict feels obviously misleading.

### 10. "Use random sampling to compare machine verdicts with human operator intuition"

The final major performance-tuning scenario was not a single bug report. It was the move to repeated random sampling reviews.

That process looked like this:

1. sample around 20 realistic GPU / model combinations
2. run `check`
3. assign a subjective verdict by human judgment
4. compare the scorer's answer with the subjective answer
5. patch the biggest sources of mismatch
6. repeat

This was important because many scoring issues were not visible in single golden-path tests.

The outcome improved materially across the three review passes:

- first review: exact match `11 / 20`
- second review: exact match `17 / 20`
- third review: exact match `18 / 20`

This is probably the clearest example of the project's vibe-coding improvement loop.

Related docs:

- [Scoring](/home/kuseo/toy/can-i-run-ai/docs/implementation/scoring.md)
- [Random Sampling Review 1](/home/kuseo/toy/can-i-run-ai/docs/qa/check-verdict-random-sampling-2026-03-18-23-58-29.md)
- [Random Sampling Review 2](/home/kuseo/toy/can-i-run-ai/docs/qa/check-verdict-random-sampling-2026-03-19-00-05-08.md)
- [Random Sampling Review 3](/home/kuseo/toy/can-i-run-ai/docs/qa/check-verdict-random-sampling-2026-03-19-00-17-03.md)

## What This Process Improved

The user-driven scenarios above improved three things more than anything else:

### 1. Catalog quality

The project moved from seed-heavy placeholders toward:

- live CPU / GPU / model collection
- better variant resolution
- better low-precision GPU data

### 2. Scoring realism

The scorer became less likely to make obviously wrong calls for:

- H100 + `gpt-oss`
- quantized 14B to 32B class runs
- RTX / Ada workstation inference
- borderline "barely fits" cases

### 3. Verdict communication

The verdict labels now better reflect how an operator would usually describe a setup:

- true no-fit
- technically loadable but not worth it
- borderline but usable
- comfortable
- clearly strong

## What This Process Did Not Try To Do

These vibe-coding iterations were pragmatic. They did not try to turn `canirunai` into:

- a hardware benchmark suite
- a backend-specific throughput simulator
- a full distributed inference planner

The project remained focused on practical single-node estimation and user-facing verdict quality.

## Bottom Line

The post-initial implementation phase of `canirunai` was shaped less by one master plan and more by repeated operator-style prompts:

- "this update should really fetch live data"
- "this parser should be deterministic"
- "this H100 result is obviously wrong"
- "this RTX Ada result still feels too pessimistic"
- "this run is not impossible, it is just too heavy"

That is the core vibe-coding story of the project so far.

Realistic commands, skeptical feedback, and repeated judgment against actual hardware intuition pushed the SDK from a functional prototype toward a more believable estimator.
