from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from canirunai.collectors.model_huggingface import ModelHuggingFaceCollector
from canirunai.collectors.wikipedia_live_parser import parse_cpu_specs_from_snapshot, parse_gpu_specs_from_snapshot
from canirunai.config.loader import load_config
from canirunai.store.raw_cache import RawCache
from canirunai.collectors.wikipedia_client import WikipediaPageSnapshot


CPU_HTML = """
<table class="wikitable">
  <tr>
    <th rowspan="2">Processor family</th>
    <th rowspan="2">Model</th>
    <th rowspan="2">Cores ( threads )</th>
    <th colspan="2">Clock rate (GHz)</th>
    <th rowspan="2">Smart cache</th>
    <th rowspan="2">TDP (W)</th>
    <th rowspan="2">Socket</th>
    <th rowspan="2">Launch</th>
  </tr>
  <tr>
    <th>Base</th>
    <th>Turbo Boost</th>
  </tr>
  <tr>
    <th>Core i7</th>
    <td>14700K</td>
    <td>20 (28)</td>
    <td>3.4</td>
    <td>5.6</td>
    <td>33</td>
    <td>125</td>
    <td>LGA 1700</td>
    <td>2023</td>
  </tr>
</table>
"""

GPU_HTML = """
<table class="wikitable">
  <tr>
    <th rowspan="2">Model Name</th>
    <th rowspan="2">Launch Date</th>
    <th rowspan="2">Code Name</th>
    <th rowspan="2">Fab ( nm )</th>
    <th rowspan="2">Bus Interface</th>
    <th colspan="3">Memory</th>
    <th rowspan="2">Processing Power (GFLOPS) Single Precision</th>
    <th rowspan="2">TDP (Watts)</th>
  </tr>
  <tr>
    <th>Size (GB)</th>
    <th>Bus Width (bit)</th>
    <th>Bandwidth (GB/s)</th>
  </tr>
  <tr>
    <td>GeForce RTX 4090</td>
    <td>2022</td>
    <td>AD102</td>
    <td>4</td>
    <td>PCIe 4.0 x16</td>
    <td>24 GB</td>
    <td>384</td>
    <td>1008.0 GB/s</td>
    <td>82600</td>
    <td>450</td>
  </tr>
</table>
"""

GPU_COMPLEX_HTML = """
<table class="wikitable sortable">
  <tr>
    <th>Model</th>
    <th>Launch</th>
    <th>Code name</th>
    <th>Bus interface</th>
    <th>Memory / Size ( MiB )</th>
    <th>Memory / Bandwidth ( GB /s )</th>
    <th>Memory / Bus width ( bit )</th>
    <th>Processing power ( TFLOPS )</th>
    <th>TDP (Watts)</th>
  </tr>
  <tr>
    <td>Code Name (Console Model)</td>
    <td>Launch</td>
    <td>Code name</td>
    <td>Bus interface</td>
    <td>Memory size</td>
    <td>Bandwidth</td>
    <td>Bus width</td>
    <td>Processing power</td>
    <td>TDP</td>
  </tr>
  <tr>
    <td><style>.mw-parser-output .plainlist{margin:0}</style>Aerith ( Steam Deck )</td>
    <td><style>.mw-parser-output .plainlist{margin:0}</style>2024</td>
    <td>Van Gogh</td>
    <td>Integrated</td>
    <td>16384</td>
    <td>88.0</td>
    <td>128</td>
    <td>1.6</td>
    <td>15</td>
  </tr>
</table>
"""

GPU_FP32_LABELLED_HTML = """
<table class="wikitable sortable">
  <tr>
    <th>Model</th>
    <th>Launch</th>
    <th>Bus interface</th>
    <th>Memory / Size ( MiB )</th>
    <th>Memory / Bandwidth ( GB /s )</th>
    <th>Processing power ( GFLOPS )</th>
  </tr>
  <tr>
    <td>Aerith</td>
    <td>2024</td>
    <td>Integrated</td>
    <td>16384</td>
    <td>88</td>
    <td>FP32: 1024 / 1638.4 (Boost) FP16: 2048 / 3276.8</td>
  </tr>
</table>
"""

CPU_COMPLEX_HTML = """
<table class="wikitable sortable">
  <tr>
    <th>Branding and Model</th>
    <th>Cores ( threads )</th>
    <th>Clock rate ( GHz ) / Base<style>.mw-parser-output .tooltip{display:none}</style></th>
    <th>Clock rate ( GHz ) / Boost</th>
    <th>L3 cache (total)</th>
    <th>TDP</th>
    <th>Release date</th>
  </tr>
  <tr>
    <td>( PRO ) 7730U</td>
    <td>8 (16)</td>
    <td>2.0</td>
    <td>4.5</td>
    <td>16 MB</td>
    <td>15 W</td>
    <td>January 4, 2023</td>
  </tr>
</table>
"""


class WikipediaLiveParserTest(unittest.TestCase):
    def test_parse_cpu_specs_from_snapshot(self) -> None:
        snapshot = WikipediaPageSnapshot(
            page_url="https://example.com/intel",
            revision_id=123,
            html=CPU_HTML,
        )

        specs = parse_cpu_specs_from_snapshot(snapshot, vendor="intel", cache_key="raw/wiki/cpu/example.html")

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].canonical_name, "Intel Core i7 14700K")
        self.assertEqual(specs[0].cores, 20)
        self.assertEqual(specs[0].threads, 28)
        self.assertEqual(specs[0].boost_clock_ghz, 5.6)

    def test_parse_gpu_specs_from_snapshot(self) -> None:
        snapshot = WikipediaPageSnapshot(
            page_url="https://example.com/nvidia",
            revision_id=456,
            html=GPU_HTML,
        )

        specs = parse_gpu_specs_from_snapshot(snapshot, vendor="nvidia", cache_key="raw/wiki/gpu/example.html")

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].canonical_name, "NVIDIA GeForce RTX 4090")
        self.assertEqual(specs[0].memory_size_gib, 24.0)
        self.assertEqual(specs[0].memory_bandwidth_gbs, 1008.0)
        self.assertEqual(specs[0].processing_power_fp32_gflops, 82600.0)

    def test_parse_gpu_specs_filters_repeated_header_rows_and_uses_header_units(self) -> None:
        snapshot = WikipediaPageSnapshot(
            page_url="https://example.com/amd",
            revision_id=789,
            html=GPU_COMPLEX_HTML,
        )

        specs = parse_gpu_specs_from_snapshot(snapshot, vendor="amd", cache_key="raw/wiki/gpu/complex.html")

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].canonical_name, "AMD Aerith (Steam Deck)")
        self.assertEqual(specs[0].memory_size_gib, 16.0)
        self.assertEqual(specs[0].memory_bandwidth_gbs, 88.0)
        self.assertEqual(specs[0].memory_bus_width_bit, 128)
        self.assertEqual(specs[0].processing_power_fp32_gflops, 1600.0)

    def test_parse_gpu_specs_ignores_fp_labels_when_extracting_processing_power(self) -> None:
        snapshot = WikipediaPageSnapshot(
            page_url="https://example.com/amd",
            revision_id=790,
            html=GPU_FP32_LABELLED_HTML,
        )

        specs = parse_gpu_specs_from_snapshot(snapshot, vendor="amd", cache_key="raw/wiki/gpu/fp32.html")

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].processing_power_fp32_gflops, 1024.0)

    def test_parse_cpu_specs_normalizes_leading_parenthesized_branding(self) -> None:
        snapshot = WikipediaPageSnapshot(
            page_url="https://example.com/amd-cpu",
            revision_id=321,
            html=CPU_COMPLEX_HTML,
        )

        specs = parse_cpu_specs_from_snapshot(snapshot, vendor="amd", cache_key="raw/wiki/cpu/complex.html")

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].canonical_name, "AMD PRO 7730U")
        self.assertEqual(specs[0].aliases, ["PRO 7730U"])
        self.assertEqual(specs[0].boost_clock_ghz, 4.5)


class FakeHuggingFaceClient:
    def list_models(self, *, author: str | None = None, limit: int | None = None) -> list[dict]:
        if author == "Qwen":
            return [{"id": "Qwen/Qwen2.5-7B-Instruct"}]
        return []

    def model_info(self, repo_id: str) -> dict:
        return {
            "id": repo_id,
            "sha": "abc123",
            "pipeline_tag": "text-generation",
            "downloads": 10,
            "likes": 1,
            "tags": ["transformers", "safetensors", "qwen2", "text-generation", "license:apache-2.0"],
            "usedStorage": 15_231_271_888,
            "safetensors": {
                "parameters": {"BF16": 7_615_616_512},
                "total": 7_615_616_512,
            },
            "config": {"model_type": "qwen2"},
            "cardData": {
                "license": "apache-2.0",
            },
            "siblings": [
                {"rfilename": "model-00001-of-00002.safetensors"},
                {"rfilename": "model-00002-of-00002.safetensors"},
            ],
        }


class ModelLiveCollectorTest(unittest.TestCase):
    def _live_config(self, tmp_dir: str) -> object:
        config_path = Path(tmp_dir) / "config.toml"
        config_path.write_text(
            textwrap.dedent(
                """
                [sdk]
                prefer_live_requests = true
                offline_seed_fallback = false
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        return load_config(config_path)

    def test_collects_live_model_catalog_without_seed_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.toml"
            config_path.write_text(
                textwrap.dedent(
                    """
                    [sdk]
                    data_dir = "./data"
                    raw_cache_dir = "./data/raw_cache"
                    prefer_live_requests = true
                    offline_seed_fallback = false

                    [huggingface]
                    teams = ["Qwen"]
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            config = load_config(config_path)
            collector = ModelHuggingFaceCollector(config, RawCache(Path(tmp_dir) / "raw_cache"))
            collector.client = FakeHuggingFaceClient()

            result = collector.collect()

            self.assertEqual(result.notes, "live Hugging Face collection")
            self.assertEqual(len(result.items), 1)
            self.assertEqual(result.items[0].canonical_name, "Qwen/Qwen2.5-7B-Instruct@bf16")
            self.assertEqual(result.items[0].num_parameters, 7_615_616_512)
            self.assertEqual(result.items[0].weights.total_size_bytes, 15_231_271_888)

    def test_collect_single_awq_repo_with_quantization_config(self) -> None:
        class FakeAwqClient:
            def model_info(self, repo_id: str) -> dict:
                return {
                    "id": repo_id,
                    "sha": "def456",
                    "pipeline_tag": "text-generation",
                    "downloads": 20,
                    "likes": 2,
                    "tags": ["transformers", "text-generation", "awq", "license:apache-2.0"],
                    "usedStorage": 5_570_829_760,
                    "config": {
                        "model_type": "qwen2",
                        "quantization_config": {"bits": 4, "quant_method": "awq"},
                    },
                    "cardData": {
                        "license": "apache-2.0",
                        "num_parameters": "7.6B",
                    },
                    "siblings": [
                        {"rfilename": "model-00001-of-00002.safetensors"},
                        {"rfilename": "model-00002-of-00002.safetensors"},
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._live_config(tmp_dir)
            collector = ModelHuggingFaceCollector(config, RawCache(Path(tmp_dir) / "raw_cache"))
            collector.client = FakeAwqClient()

            result = collector.collect(hf_repo_id="Qwen/Qwen2.5-7B-Instruct-AWQ")

            self.assertEqual(len(result.items), 1)
            self.assertEqual(result.items[0].canonical_name, "Qwen/Qwen2.5-7B-Instruct-AWQ@awq-4bit")
            self.assertEqual(result.items[0].weights.total_size_bytes, 5_570_829_760)

    def test_collect_single_gguf_repo_expands_variants(self) -> None:
        class FakeGgufClient:
            def model_info(self, repo_id: str) -> dict:
                return {
                    "id": repo_id,
                    "sha": "ghi789",
                    "pipeline_tag": "text-generation",
                    "downloads": 30,
                    "likes": 3,
                    "tags": ["gguf", "text-generation", "license:apache-2.0"],
                    "gguf": {"total": 7_615_616_512, "context_length": 131072, "architecture": "qwen2"},
                    "cardData": {"license": "apache-2.0"},
                    "siblings": [
                        {"rfilename": "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf"},
                        {"rfilename": "qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf"},
                        {"rfilename": "qwen2.5-7b-instruct-q8_0-00001-of-00003.gguf"},
                        {"rfilename": "qwen2.5-7b-instruct-q8_0-00002-of-00003.gguf"},
                        {"rfilename": "qwen2.5-7b-instruct-q8_0-00003-of-00003.gguf"},
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._live_config(tmp_dir)
            collector = ModelHuggingFaceCollector(config, RawCache(Path(tmp_dir) / "raw_cache"))
            collector.client = FakeGgufClient()

            result = collector.collect(hf_repo_id="Qwen/Qwen2.5-7B-Instruct-GGUF")

            self.assertEqual(len(result.items), 2)
            self.assertEqual(
                [item.canonical_name for item in result.items],
                [
                    "Qwen/Qwen2.5-7B-Instruct-GGUF@q4_k_m",
                    "Qwen/Qwen2.5-7B-Instruct-GGUF@q8_0",
                ],
            )
            self.assertTrue(all(item.weights.total_size_bytes is not None for item in result.items))
