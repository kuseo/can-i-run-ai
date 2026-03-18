# CLI

This document explains the current canirunai CLI command structure and how each command behaves.

## Overview

The CLI is a thin wrapper around the SDK. It does not implement scoring or collection logic by itself. Instead, it:

1. loads configuration,
2. creates a `CanIRunAI` SDK instance,
3. calls the matching SDK method,
4. renders the result to the terminal.

The root command can be invoked in either form:

```bash
uv run canirunai --help
uv run python -m canirunai --help
```

## Command Tree

The current command tree is:

```text
canirunai
  update
    cpu
    gpu
    model [--hfname REPO_ID]
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

- the SDK always loads the built-in default config first,
- if `--config` is provided, the custom file is deep-merged on top,
- the merged config is validated before command execution.

If the file path does not exist, Click rejects the command before the SDK starts.

## `update`

The `update` group refreshes the local spec catalogs under `data/specs`.

These commands write catalog JSON files and do not print the catalog contents. They only print a short summary such as:

```text
updated cpu catalog with 3 items
```

### `update cpu`

```bash
uv run canirunai update cpu
```

Behavior:

- calls the CPU collector,
- gets CPU spec records,
- merges them into `data/specs/cpu.json`,
- prints how many items exist in the resulting catalog.

Current implementation note:

- by default this uses the bundled seed CPU catalog,
- if `sdk.prefer_live_requests = true`, it can fetch raw Wikipedia HTML first,
- it still falls back to bundled seed specs because the HTML-to-spec parser is not yet wired.

### `update gpu`

```bash
uv run canirunai update gpu
```

Behavior:

- calls the GPU collector,
- gets GPU spec records,
- merges them into `data/specs/gpu.json`,
- prints the resulting catalog size.

Current implementation note:

- by default this uses the bundled seed GPU catalog,
- with live requests enabled it can fetch raw Wikipedia HTML,
- it still falls back to bundled seed specs for the normalized output.

### `update model`

```bash
uv run canirunai update model
uv run canirunai update model --hfname deepseek-ai/DeepSeek-R1
```

Behavior:

- calls the model collector,
- gets model spec records,
- merges them into `data/specs/model.json`,
- prints the resulting catalog size.

`--hfname` is currently the only resource-specific update argument. It is meant for a single Hugging Face repo id.

Current implementation note:

- without `--hfname`, the command uses the bundled seed model catalog,
- with `--hfname` and `sdk.prefer_live_requests = true`, the CLI can attempt a live Hugging Face API fetch,
- if the live path fails, it falls back to the seed model catalog,
- if `--hfname` is provided but the repo does not exist in the seed catalog and live fetch is unavailable, the command fails.

## `list`

The `list` group prints catalog entries that have already been stored locally.

It does not trigger scoring. It only reads the catalog JSON files.

### `list cpu`

```bash
uv run canirunai list cpu
uv run canirunai list cpu --output wide
uv run canirunai list cpu --output json
```

Output modes:

- default: one canonical CPU name per line,
- `wide`: compact summary rows,
- `json`: raw catalog item JSON array.

### `list gpu`

```bash
uv run canirunai list gpu
uv run canirunai list gpu --output wide
uv run canirunai list gpu --output json
```

Output modes:

- default: one canonical GPU name per line,
- `wide`: compact summary rows,
- `json`: raw catalog item JSON array.

### `list model`

```bash
uv run canirunai list model
uv run canirunai list model --output wide
uv run canirunai list model --output json
```

Output modes:

- default: one canonical model name per line,
- `wide`: compact summary rows,
- `json`: raw catalog item JSON array.

## `get`

The `get` group prints a single catalog item.

It performs name lookup against the local catalogs and can resolve canonical names and some aliases.

### `get cpu`

```bash
uv run canirunai get cpu "AMD Ryzen 9 7950X"
uv run canirunai get cpu "ryzen 9 7950x"
uv run canirunai get cpu "AMD Ryzen 9 7950X" --output json
```

Behavior:

- loads the CPU catalog,
- finds one matching CPU record,
- prints a human-readable view or JSON.

### `get gpu`

```bash
uv run canirunai get gpu "NVIDIA GeForce RTX 4090"
uv run canirunai get gpu "rtx 4090"
uv run canirunai get gpu "NVIDIA GeForce RTX 4090" --output json
```

Behavior:

- loads the GPU catalog,
- resolves the name or alias,
- prints a single GPU record.

### `get model`

```bash
uv run canirunai get model "Qwen/Qwen2.5-7B-Instruct@bf16"
uv run canirunai get model "Qwen/Qwen2.5-7B-Instruct"
uv run canirunai get model "Qwen/Qwen2.5-7B-Instruct@bf16" --output json
```

Behavior:

- loads the model catalog,
- matches by canonical name, repo id, or alias,
- prints one model record.

Current implementation note:

- `get` only supports `--output json` as an explicit output mode,
- the default output is a simple line-oriented detail view.

## `check`

`check` is the scoring command. It evaluates a hardware configuration against one model and returns a verdict plus score details.

Example:

```bash
uv run canirunai check \
  --cpu "AMD Ryzen 9 7950X" \
  --gpu "NVIDIA GeForce RTX 4090" \
  --memory 64 \
  --model "Qwen/Qwen2.5-7B-Instruct@bf16"
```

### Required Options

- `--cpu NAME`
  May be repeated for multi-CPU input.
- `--gpu NAME`
  May be repeated for multi-GPU input.
- `--memory GB`
  Required float value for system RAM.
- `--model NAME`
  Required model name.

### Optional Output Mode

```bash
uv run canirunai check ... --output wide
uv run canirunai check ... --output json
```

Output modes:

- default: concise verdict, score, context estimate, and decode TPS,
- `wide`: adds memory and bottleneck details,
- `json`: prints the raw `ScoreReport` object.

## Name Resolution Rules

Most resource lookups are normalized before matching. This means the CLI is lenient about:

- letter case,
- spaces,
- punctuation,
- simple alias forms.

Examples:

- `rtx 4090` can match `NVIDIA GeForce RTX 4090`,
- `ryzen 9 7950x` can match `AMD Ryzen 9 7950X`.

For models, the CLI can also resolve by repo id in some cases, such as:

- `Qwen/Qwen2.5-7B-Instruct`
- `deepseek-ai/DeepSeek-R1`

## Output Philosophy

The CLI supports two broad output styles.

### Human-Oriented Output

The default output and `wide` output are designed for terminal use.

- default output is short and task-focused,
- `wide` output includes more diagnostic context without dumping the full JSON structure.

### Machine-Oriented Output

`--output json` returns raw structured JSON suitable for scripts and automation.

This is useful when:

- integrating with another tool,
- storing scoring results,
- debugging catalog contents,
- comparing output across versions.

## Typical Workflows

### Initialize Local Catalogs

```bash
uv run canirunai update cpu
uv run canirunai update gpu
uv run canirunai update model
```

### Inspect Available Resources

```bash
uv run canirunai list cpu --output wide
uv run canirunai list gpu --output wide
uv run canirunai list model --output wide
```

### Inspect One Resource

```bash
uv run canirunai get gpu "NVIDIA GeForce RTX 4090" --output json
```

### Evaluate a Deployment Candidate

```bash
uv run canirunai check \
  --cpu "AMD Ryzen 9 7950X" \
  --gpu "NVIDIA GeForce RTX 4090" \
  --memory 64 \
  --model "Qwen/Qwen2.5-7B-Instruct@bf16" \
  --output wide
```

## Current Limitations

The CLI surface is stable enough for the current MVP, but some behavior is intentionally incomplete.

- CPU and GPU update commands do not yet produce live structured specs from Wikipedia HTML.
- Full Hugging Face catalog discovery is not implemented yet.
- `get` currently only advertises `--output json`, not `--output wide`.
- Error formatting is mostly the default Click or Python exception behavior.
- No shell completion, progress bars, or batch export commands exist yet.

## Future Directions

Likely CLI improvements include:

- richer live update options,
- better error messages,
- separate `--output wide` support for `get`,
- batch scoring from files,
- better machine-oriented exit codes,
- progress reporting during collection,
- explicit commands for cache inspection and replay.
