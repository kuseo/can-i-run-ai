from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from canirunai.sdk import CanIRunAI


class SdkFlowTest(unittest.TestCase):
    def test_update_list_get_check_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.toml"
            data_dir = Path(tmp_dir) / "data"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    [sdk]
                    data_dir = "{data_dir}"
                    raw_cache_dir = "{data_dir / 'raw_cache'}"
                    prefer_live_requests = false
                    offline_seed_fallback = true
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            sdk = CanIRunAI(config_path=config_path)
            cpu_catalog = sdk.update_cpu()
            gpu_catalog = sdk.update_gpu()
            model_catalog = sdk.update_model()

            self.assertGreaterEqual(len(cpu_catalog.items), 3)
            self.assertGreaterEqual(len(gpu_catalog.items), 4)
            self.assertGreaterEqual(len(model_catalog.items), 3)

            cpu = sdk.get_spec("cpu", "ryzen 9 7950x")
            gpu = sdk.get_spec("gpu", "rtx 4090")
            model = sdk.get_spec("model", "Qwen/Qwen2.5-7B-Instruct")
            self.assertEqual(cpu.canonical_name, "AMD Ryzen 9 7950X")
            self.assertEqual(gpu.canonical_name, "NVIDIA GeForce RTX 4090")
            self.assertEqual(model.canonical_name, "Qwen/Qwen2.5-7B-Instruct@bf16")

            report = sdk.check(
                cpu_names=["AMD Ryzen 9 7950X"],
                gpu_names=["NVIDIA GeForce RTX 4090"],
                memory_gb=64,
                model_name="Qwen/Qwen2.5-7B-Instruct@bf16",
            )
            self.assertIn(report.verdict, {"RUNS WELL", "RUNS GREAT", "TIGHT FIT"})
            self.assertGreater(report.context_estimate.safe_context_tokens, 0)
