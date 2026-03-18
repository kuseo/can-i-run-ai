# canirunai

`canirunai` is a Python SDK and CLI that estimates whether a given CPU/GPU/RAM setup can host and serve a target LLM.

This project was inspired by [canirun.ai](https://canirun.ai), and its ideation and SDK design were developed with ChatGPT Deep Research. For the original design reference, see [this shared ChatGPT Deep Research link](https://chatgpt.com/share/69ba3c57-25e8-8004-ac86-8a29d7d18340).

## Quick Start

### CLI

```bash
uv sync
uv run canirunai update cpu
uv run canirunai update gpu
uv run canirunai update model
uv run canirunai check \
  --cpu "AMD Ryzen 9 7950X" \
  --gpu "NVIDIA GeForce RTX 4090" \
  --memory 64 \
  --model "Qwen/Qwen2.5-7B-Instruct@bf16" \
  --output wide
```

Example `check` output from the current local catalog:

```text
verdict: RUNS WELL
score: 82
context: safe=15501 max=18237
throughput: decode=59.56 tps prefill=1429.48 tps
memory: weights=14.19 GB total_at_safe=22.82 GB headroom=1.18 GB
bottlenecks: gpu_bandwidth, gpu_compute
```

The same command with `--output json`:

```bash
uv run canirunai check \
  --cpu "AMD Ryzen 9 7950X" \
  --gpu "NVIDIA GeForce RTX 4090" \
  --memory 64 \
  --model "Qwen/Qwen2.5-7B-Instruct@bf16" \
  --output json
```

Example JSON output:

```json
{
  "schema_version": 1,
  "verdict": "RUNS WELL",
  "score": 82,
  "inputs": {
    "cpu": [
      "AMD Ryzen 9 7950X"
    ],
    "gpu": [
      "NVIDIA GeForce RTX 4090"
    ],
    "memory_gb": 64.0,
    "model": "Qwen/Qwen2.5-7B-Instruct@bf16"
  },
  "placement_estimate": {
    "mode": "replicated_serving",
    "single_gpu_loadable": true,
    "replica_count": 1,
    "used_gpu_canonical_names": [
      "NVIDIA GeForce RTX 4090"
    ]
  },
  "context_estimate": {
    "max_supported_context_tokens": 18237,
    "safe_context_tokens": 15501
  },
  "throughput_estimate": {
    "decode_tokens_per_sec": 59.56,
    "prefill_tokens_per_sec": 1429.48
  },
  "wide": {
    "memory_estimate": {
      "weights_vram_gb": 14.19,
      "runtime_overhead_vram_gb": 1.92,
      "kv_cache_gb_per_1k_tokens": 0.4329,
      "total_vram_gb_at_safe_context": 22.82,
      "vram_headroom_gb": 1.18,
      "host_ram_required_gb": 8.96,
      "host_ram_headroom_gb": 55.04
    },
    "latency_estimate": {
      "first_token_ms_per_1k_prompt_tokens": 700,
      "generation_ms_per_128_output_tokens": 2149
    },
    "bottlenecks": {
      "primary": "gpu_bandwidth",
      "secondary": "gpu_compute"
    },
    "confidence": {
      "context": "high",
      "throughput": "medium"
    }
  }
}
```

### Python

`canirunai` can also be used directly from Python:

```python
from canirunai import CanIRunAI

sdk = CanIRunAI()

report = sdk.check(
    cpu_names=["AMD Ryzen 9 7950X"],
    gpu_names=["NVIDIA GeForce RTX 4090"],
    memory_gb=64,
    model_name="Qwen/Qwen2.5-7B-Instruct@bf16",
)

print(report.verdict)
print(report.score)
print(report.context_estimate.safe_context_tokens)
print(report.throughput_estimate.decode_tokens_per_sec)
```

The built-in config currently tries live collection first and falls back to bundled seed catalogs if live collection fails. Once local catalogs exist, `list`, `get`, and `check` work from those local JSON files.

Live collection is implemented with deterministic parsers for Wikipedia and Hugging Face sources. The long-term parser policy is still "rules first, LLM only on failure", but the current collectors do not yet invoke the OpenAI fallback parser automatically.

## For More Information

### Implementation

- [CLI](docs/implementation/cli.md): command tree, options, output modes, and current limitations.
- [Configuration](docs/implementation/configuration.md): built-in defaults, merge rules, and how each config section maps to the code.
- [Spec Collection](docs/implementation/spec-collection.md): live Wikipedia and Hugging Face collection flow, raw cache, normalization, and seed fallback behavior.
- [Scoring](docs/implementation/scoring.md): weight, KV cache, throughput, verdict, and score estimation rules.

### QA

- [QA Check Report](docs/qa/qa-check-report.md): targeted manual QA of `check` against the current local catalogs.
- [Random Sampling Review 1](docs/qa/check-verdict-random-sampling-2026-03-18-23-58-29.md): first subjective-versus-scorer sampling review.
- [Random Sampling Review 2](docs/qa/check-verdict-random-sampling-2026-03-19-00-05-08.md): second review after verdict and low-precision scoring fixes.
- [Random Sampling Review 3](docs/qa/check-verdict-random-sampling-2026-03-19-00-17-03.md): latest review after additional verdict and GPU metric normalization changes.

### Project Notes

- [Vibe Coding Improvement Scenarios](docs/vibe-coding-improvements.md): short narrative of the user-driven prompts that shaped the SDK after the initial implementation.

## Future Work

- Add concurrency-aware scoring for multi-user serving environments. The current scorer estimates single-node fit and replicated throughput, but it does not yet model concurrent sessions, per-user KV cache growth, batching, queueing latency, or multi-tenant contention.
