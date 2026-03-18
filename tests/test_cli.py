from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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

    def test_update_verbose_flag_is_forwarded_to_sdk(self) -> None:
        runner = CliRunner()
        fake_sdk = Mock()
        fake_sdk.update_cpu.return_value = SimpleNamespace(items=[object(), object()])

        with patch("canirunai.cli.main._sdk", return_value=fake_sdk):
            result = runner.invoke(cli, ["update", "cpu", "--verbose"])

        self.assertEqual(result.exit_code, 0)
        fake_sdk.update_cpu.assert_called_once_with(verbose=True)
        self.assertIn("updated cpu catalog with 2 items", result.output)
