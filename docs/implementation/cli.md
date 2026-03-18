# CLI

This document describes the current `canirunai` CLI surface and how the commands map to the SDK.

## Overview

The CLI is a thin wrapper around [`CanIRunAI`](/home/kuseo/toy/can-i-run-ai/src/canirunai/sdk.py).

It does four things:

1. load and validate config
2. construct the SDK
3. call the matching SDK method
4. render the returned catalog item or score report

The CLI can be invoked in either form:

```bash
uv run canirunai --help
uv run python -m canirunai --help
```

## Command Tree

```text
canirunai
  [--config FILE]
  update
    cpu [--verbose]
    gpu [--verbose]
    model [--hfname REPO_ID] [--verbose]
  list
    cpu [--output wide|json]
    gpu [--output wide|json]
    model [--output wide|json]
  get
    cpu NAME [--output json]
    gpu NAME [--output json]
    model NAME [--output json]
  check
    --cpu NAME...
    --gpu NAME...
    --memory GB
    --model NAME
    [--output wide|json]
```

## Global Options

### `--config FILE`

The root command accepts an optional config file:

```bash
uv run canirunai --config ./config.toml list model
```

Behavior:

- the SDK always loads the built-in `default_config.toml` first
- if `--config` is provided, the custom file is deep-merged on top
- the merged config is validated before command execution

If the file does not exist, Click rejects the command before the SDK starts.

## `update`

The `update` group refreshes the local catalogs under `data/specs`.

Each command writes JSON files and prints a short summary such as:

```text
updated gpu catalog with 1666 items
```

With the current built-in config, update commands:

- try live collection first because `sdk.prefer_live_requests = true`
- fall back to bundled seed data if live collection fails because `sdk.offline_seed_fallback = true`

### `--verbose`

All `update` subcommands accept `--verbose`.

```bash
uv run canirunai update gpu --verbose
```

Current behavior:

- the underlying clients log each requested URL with Loguru `INFO`
- this applies to Wikipedia MediaWiki API requests and Hugging Face API requests

### `update cpu`

```bash
uv run canirunai update cpu
uv run canirunai update cpu --verbose
```

Behavior:

- fetches Intel and AMD CPU source pages when live requests are enabled
- stores raw HTML snapshots in `raw_cache`
- parses CPU tables into `CpuSpec` items
- merges the result into `data/specs/cpu.json`

If live collection fails and seed fallback is enabled, the CPU seed catalog is merged instead.

### `update gpu`

```bash
uv run canirunai update gpu
uv run canirunai update gpu --verbose
```

Behavior:

- fetches NVIDIA and AMD GPU source pages when live requests are enabled
- stores raw HTML snapshots in `raw_cache`
- parses GPU tables into `GpuSpec` items
- normalizes low-precision NVIDIA compute fields during collection and load
- merges the result into `data/specs/gpu.json`

If live collection fails and seed fallback is enabled, the GPU seed catalog is merged instead.

### `update model`

```bash
uv run canirunai update model
uv run canirunai update model --hfname deepseek-ai/DeepSeek-R1
uv run canirunai update model --verbose
```

Behavior:

- without `--hfname`, performs a bulk live Hugging Face sync from the configured teams list when live requests are enabled
- with `--hfname`, performs a single-repo live Hugging Face fetch
- stores raw JSON payloads in `raw_cache`
- normalizes repo metadata into one or more `ModelSpec` variants
- merges the result into `data/specs/model.json`

Current live bulk sync is limited by:

- `huggingface.teams`
- `huggingface.max_models_total`
- `huggingface.max_models_per_team`

and currently applies post-normalization filtering for:

- `huggingface.pipeline_tag`
- `huggingface.license_id`

## `list`

The `list` group prints catalog entries already stored locally. It does not trigger live collection or scoring.

### `list cpu`

```bash
uv run canirunai list cpu
uv run canirunai list cpu --output wide
uv run canirunai list cpu --output json
```

Output modes:

- default: one canonical CPU name per line
- `wide`: `name | cores/threads | boost clock`
- `json`: raw catalog JSON array

### `list gpu`

```bash
uv run canirunai list gpu
uv run canirunai list gpu --output wide
uv run canirunai list gpu --output json
```

Output modes:

- default: one canonical GPU name per line
- `wide`: `name | memory size | memory bandwidth`
- `json`: raw catalog JSON array

### `list model`

```bash
uv run canirunai list model
uv run canirunai list model --output wide
uv run canirunai list model --output json
```

Output modes:

- default: one canonical model name per line
- `wide`: `name | parameters | context | variant`
- `json`: raw catalog JSON array

## `get`

The `get` group prints one catalog item from local storage.

### `get cpu`

```bash
uv run canirunai get cpu "AMD Ryzen 9 7950X"
uv run canirunai get cpu "AMD Ryzen 9 7950X" --output json
```

### `get gpu`

```bash
uv run canirunai get gpu "NVIDIA GeForce RTX 4090"
uv run canirunai get gpu "NVIDIA GeForce RTX 4090" --output json
```

### `get model`

```bash
uv run canirunai get model "Qwen/Qwen2.5-7B-Instruct@bf16"
uv run canirunai get model "Qwen/Qwen2.5-7B-Instruct"
uv run canirunai get model "Qwen/Qwen2.5-7B-Instruct@bf16" --output json
```

Current behavior:

- `get` only exposes `--output json` as an explicit output mode
- the default output is a line-oriented detail view
- model lookup matches canonical name, Hugging Face repo id, or aliases
- if a repo id maps to multiple stored variants, repo-id lookup returns the first matching item in catalog order, so canonical names are the stable way to select a specific variant

## `check`

`check` scores one model against one or more CPUs, one or more GPUs, and explicit system RAM.

Example:

```bash
uv run canirunai check \
  --cpu "AMD Ryzen 9 7950X" \
  --gpu "NVIDIA GeForce RTX 4090" \
  --memory 64 \
  --model "Qwen/Qwen2.5-7B-Instruct@bf16"
```

Required options:

- `--cpu NAME`
  May be repeated for multi-CPU input.
- `--gpu NAME`
  May be repeated for multi-GPU input.
- `--memory GB`
  Required float value for system RAM.
- `--model NAME`
  Required model name.

Optional output modes:

```bash
uv run canirunai check ... --output wide
uv run canirunai check ... --output json
```

Output modes:

- default: verdict, score, context estimate, and decode TPS
- `wide`: adds prefill TPS, memory, and bottleneck summary lines
- `json`: prints the raw `ScoreReport`

## Name Resolution Rules

Resource lookup is normalized before matching. The CLI is lenient about:

- letter case
- spaces
- punctuation
- simple alias forms

Examples:

- `rtx 4090` can match `NVIDIA GeForce RTX 4090`
- `ryzen 9 7950x` can match `AMD Ryzen 9 7950X`

For models, repo-id lookup also works:

- `Qwen/Qwen2.5-7B-Instruct`
- `deepseek-ai/DeepSeek-R1`

Use canonical variant names when you need a stable exact match:

- `Qwen/Qwen2.5-7B-Instruct@bf16`
- `openai/gpt-oss-20b@mxfp4`

## Current Limitations

- live CPU and GPU parsing is still heuristic and may miss or over-include some Wikipedia rows
- bulk Hugging Face sync is constrained by the configured team allowlist and collection caps
- `get` does not support `--output wide`
- error formatting is still mostly default Click or uncaught Python exception behavior
- `check` models replicated serving only; it does not estimate tensor-parallel or pipeline-parallel sharding

## Future Directions

Likely CLI improvements include:

- better error messages for unknown names
- progress reporting during live collection
- batch scoring from files
- richer export modes
- explicit cache inspection commands
