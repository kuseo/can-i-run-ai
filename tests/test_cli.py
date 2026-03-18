from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from click.testing import CliRunner

from canirunai.cli.main import cli


class CliFlowTest(unittest.TestCase):
    def test_update_and_check_commands(self) -> None:
        runner = CliRunner()
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

            result = runner.invoke(cli, ["--config", str(config_path), "update", "cpu"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("updated cpu catalog", result.output)

            runner.invoke(cli, ["--config", str(config_path), "update", "gpu"])
            runner.invoke(cli, ["--config", str(config_path), "update", "model"])

            check = runner.invoke(
                cli,
                [
                    "--config",
                    str(config_path),
                    "check",
                    "--cpu",
                    "AMD Ryzen 9 7950X",
                    "--gpu",
                    "NVIDIA GeForce RTX 4090",
                    "--memory",
                    "64",
                    "--model",
                    "Qwen/Qwen2.5-7B-Instruct@bf16",
                ],
            )
            self.assertEqual(check.exit_code, 0)
            self.assertIn("verdict:", check.output)
