# Configuration

The built-in default config lives at [`../src/canirunai/config/default_config.toml`](../src/canirunai/config/default_config.toml). At runtime, canirunai loads that file first and then deep-merges a user-supplied config file on top of it.

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
teams = ["Qwen", "deepseek-ai", "mistralai"]

[scoring]
overhead_ratio = 0.10
safe_context_ratio = 0.80
```

## Config Structure

- `[sdk]`
  Core SDK behavior.
- `data_dir`
  Path where generated catalogs are written, such as `data/specs/cpu.json`.
- `raw_cache_dir`
  Path where fetched raw HTML or API payloads are cached.
- `log_level`
  Loguru log level.
- `prefer_live_requests`
  If `true`, collectors try live requests to Wikipedia or Hugging Face before falling back. CPU and GPU updates then use the deterministic live table parser, and model updates use live Hugging Face API collection.
- `offline_seed_fallback`
  Controls whether collectors may fall back to bundled seed data when live collection fails. If `false`, live update errors are surfaced instead of silently using seed catalogs.

- `[openai_parser]`
  Settings for the Structured Outputs fallback parser integration.
- `api_key`
  Supports `ENV:VARIABLE_NAME` syntax. `ENV:OPENAI_API_KEY` means "read from the `OPENAI_API_KEY` environment variable".
- `base_url`
  OpenAI-compatible API base URL.
- `model`
  Model name intended for fallback structured parsing.
- `max_retries`, `timeout_sec`
  Retry and timeout controls for fallback parser requests.

- `[wikipedia]`
  Settings for Wikipedia collection.
- `user_agent`
  User-Agent sent to MediaWiki endpoints.
- `request_delay_sec`
  Delay between requests.
- `[wikipedia.cpu_intel]`, `[wikipedia.cpu_amd_ryzen]`, `[wikipedia.gpu_nvidia]`, `[wikipedia.gpu_amd]`
  Per-source page URLs for CPU and GPU catalogs.

- `[huggingface]`
  Settings for Hugging Face model collection.
- `endpoint`
  Hub base URL.
- `request_delay_sec`
  Delay between Hub API requests.
- `max_models_total`, `max_models_per_team`
  Collection limits.
- `pipeline_tag`
  Default task filter, currently `text-generation`.
- `license_id`
  Default license filter.
- `inference_provider`
  Provider filter for inference-capable models.
- `num_parameters`
  Parameter-range filter string.
- `teams`
  Organization allowlist used when a future full catalog sync is enabled.

- `[scoring]`
  Heuristics for the hardware-to-model fit estimator.
- `overhead_ratio`
  Runtime VRAM overhead fraction reserved beyond model weights and KV cache.
- `safe_context_ratio`
  Ratio used to derive `safe_context_tokens` from the theoretical max context.
- `min_context_tokens`, `too_heavy_context_tokens`
  Hard-gate thresholds for `IMPOSSIBLE` and `TOO HEAVY`.
- `tight_fit_headroom_ratio`
  Minimum VRAM headroom ratio before the result is labeled `TIGHT FIT`.
- `min_decode_tps`, `good_decode_tps`, `great_decode_tps`
  Decode throughput thresholds used by the verdict and score model.
- `great_context_tokens`
  Context threshold for `RUNS GREAT`.
- `eff_bw`, `eff_flops`, `stream_reuse_factor`
  Throughput approximation coefficients.
- `prefill_multiplier`
  Prefill estimate multiplier derived from decode throughput.
- `default_kv_element_bits`
  KV cache element width used for estimation.
- `host_ram_weight_fraction`
  Host RAM requirement heuristic based on model weight size.
- `cpu_threads_per_replica`
  CPU thread budget assumed per replica.

## How Overrides Work

- Any missing field in your custom config keeps the value from `default_config.toml`.
- Nested sections are merged recursively. Overriding `[scoring] safe_context_ratio` does not erase the rest of `[scoring]`.
- `ENV:...` strings are resolved after merging. This is why `api_key = "ENV:OPENAI_API_KEY"` works in both the default file and custom files.
- A wrong key or wrong type fails validation during startup because the config is validated with Pydantic.

## Parser Policy

The intended parser policy is deterministic first and LLM second.

- Live CPU and GPU updates first try the rule-based Wikipedia table parser.
- Live model updates first try deterministic Hugging Face API normalization.
- The `openai_parser` settings exist for fallback behavior only. An LLM parser should run only if the deterministic parser fails to produce schema-valid structured data.
