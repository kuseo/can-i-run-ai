# Configuration

The built-in default config lives at [`../../src/canirunai/config/default_config.toml`](../../src/canirunai/config/default_config.toml).

At runtime, `canirunai`:

1. loads that built-in TOML file
2. deep-merges a user config file on top if `--config` is provided
3. resolves `ENV:...` tokens
4. validates the final result with Pydantic

## Current Built-In Defaults

The built-in config currently enables live collection by default:

- `sdk.prefer_live_requests = true`
- `sdk.offline_seed_fallback = true`

So a stock `update` command tries live requests first and only falls back to seed catalogs if the live path fails.

## Usage

Use a custom config like this:

```bash
uv run canirunai --config ./config.toml update model
uv run canirunai --config ./config.toml check \
  --cpu "AMD Ryzen 9 7950X" \
  --gpu "NVIDIA GeForce RTX 4090" \
  --memory 64 \
  --model "Qwen/Qwen2.5-7B-Instruct@bf16"
```

Example `config.toml`:

```toml
[sdk]
data_dir = "./data"
raw_cache_dir = "./data/raw_cache"
prefer_live_requests = true

[openai_parser]
api_key = "ENV:OPENAI_API_KEY"

[wikipedia]
user_agent = "canirunai/0.1 (contact: you@example.com)"

[huggingface]
teams = ["Qwen", "openai", "meta-llama", "deepseek-ai", "mistralai"]

[scoring]
overhead_ratio = 0.08
safe_context_ratio = 0.85
```

## Config Structure

### `[sdk]`

Core SDK behavior.

- `data_dir`
  Directory that holds generated catalogs such as `data/specs/gpu.json`.
- `raw_cache_dir`
  Directory that holds cached raw HTML and API payloads.
- `log_level`
  Loguru log level string.
- `prefer_live_requests`
  If `true`, collectors try live Wikipedia or Hugging Face requests before falling back.
- `offline_seed_fallback`
  If `true`, collectors may fall back to bundled seed catalogs when live collection fails.

### `[openai_parser]`

Configuration for the OpenAI structured parsing hook.

- `api_key`
  Supports `ENV:VARIABLE_NAME` syntax.
- `base_url`
  OpenAI-compatible API base URL.
- `model`
  Model name intended for future fallback parsing.
- `max_retries`, `timeout_sec`
  Retry and timeout controls for that future integration.

Current implementation note:

- the parser interface exists in code, but live collectors do not call it yet
- the current collection path is deterministic parsing plus optional seed fallback, not live OpenAI fallback

### `[wikipedia]`

Settings for CPU and GPU Wikipedia collection.

- `user_agent`
  User-Agent sent to MediaWiki API requests.
- `request_delay_sec`
  Delay between requests.
- `[wikipedia.cpu_intel]`, `[wikipedia.cpu_amd_ryzen]`, `[wikipedia.gpu_nvidia]`, `[wikipedia.gpu_amd]`
  Per-source page URLs used for live collection.

### `[huggingface]`

Settings for live Hugging Face collection.

- `endpoint`
  Hub base URL.
- `request_delay_sec`
  Delay between API requests.
- `max_models_total`, `max_models_per_team`
  Caps used by bulk team-based model sync.
- `pipeline_tag`
  Used in the current `list_models` query and also as a keep/discard filter on normalized specs.
- `license_id`
  Used as a keep/discard filter on normalized specs when a license is present.
- `teams`
  Organization allowlist used by the current bulk live model sync.

Currently present but not enforced by the collector:

- `inference_provider`
- `num_parameters`

Those fields are configuration placeholders for future live filtering.

### `[scoring]`

Heuristics for the hardware-to-model fit estimator.

- `overhead_ratio`
  Runtime VRAM overhead fraction reserved beyond weights and KV cache.
- `safe_context_ratio`
  Margin applied to theoretical max context to derive `safe_context_tokens`.
- `min_context_tokens`
  Below this safe context, the verdict becomes `TOO HEAVY`.
- `too_heavy_context_tokens`
  Used in the current `RUNS GREAT` threshold calculation and other context gates.
- `tight_fit_headroom_ratio`
  VRAM headroom ratio below which resources are considered tight.
- `min_decode_tps`, `good_decode_tps`, `great_decode_tps`
  Decode throughput thresholds used by verdict and score logic.
- `great_context_tokens`
  Baseline context target for `RUNS GREAT`.
- `eff_bw`, `eff_flops`, `stream_reuse_factor`
  Throughput approximation coefficients.
- `prefill_multiplier`
  Prefill estimate multiplier applied to decode throughput.
- `default_kv_element_bits`
  KV cache element width used in estimation.
- `host_ram_weight_fraction`
  Host RAM heuristic based on model weight size.
- `cpu_threads_per_replica`
  CPU thread budget assumed per replica in replicated serving mode.

## How Overrides Work

- Any missing field in your custom file keeps the value from `default_config.toml`.
- Nested sections are merged recursively.
- `ENV:...` strings are resolved after merging.
- `ENV:NAME` resolves with `os.getenv(NAME, "")`, so a missing environment variable becomes an empty string, not `null`.
- Wrong keys or wrong types fail validation during startup.

## Parser Policy

The intended parser policy is still deterministic first and LLM second.

Current code behavior:

- live CPU and GPU updates use deterministic Wikipedia parsing only
- live model updates use deterministic Hugging Face normalization only
- if live parsing fails, collectors either fall back to seed data or raise an error depending on `sdk.offline_seed_fallback`
- the OpenAI structured parser class is present as a narrow interface, but it is not wired into the collection flow yet
