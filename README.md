# canirunai

`canirunai` is a Python SDK and CLI that estimates whether a given CPU/GPU/RAM setup can host and serve a target LLM.

This project was inspired by [canirun.ai](https://canirun.ai), and its ideation and SDK design were developed with ChatGPT Deep Research. For the original design reference, see [this shared ChatGPT Deep Research link](https://chatgpt.com/share/69ba3c57-25e8-8004-ac86-8a29d7d18340).

## Quick Start

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

By default, the SDK ships with an offline-capable seed catalog so `update/list/get/check` work without live network parsing. Set `sdk.prefer_live_requests = true` in a custom config to enable live source fetch attempts.

## For More Information

- [CLI](docs/cli.md)
- [Configuration](docs/configuration.md)
- [Spec Collection](docs/spec-collection.md)
- [Scoring](docs/scoring.md)
