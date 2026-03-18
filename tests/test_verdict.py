from __future__ import annotations

import unittest

from canirunai.config.loader import ScoringConfig
from canirunai.scoring.verdict import determine_verdict


class VerdictPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ScoringConfig()

    def test_strong_loadable_setup_with_low_headroom_is_runs_well(self) -> None:
        verdict = determine_verdict(
            single_gpu_loadable=True,
            safe_context_tokens=15_390,
            decode_tokens_per_sec=113.72,
            vram_headroom_ratio=0.095,
            host_ram_headroom_gb=128.0,
            config=self.config,
        )

        self.assertEqual(verdict, "RUNS WELL")

    def test_loadable_but_tiny_context_is_too_heavy_not_impossible(self) -> None:
        verdict = determine_verdict(
            single_gpu_loadable=True,
            safe_context_tokens=192,
            decode_tokens_per_sec=16.62,
            vram_headroom_ratio=0.002,
            host_ram_headroom_gb=128.0,
            config=self.config,
        )

        self.assertEqual(verdict, "TOO HEAVY")

    def test_large_context_and_speed_with_headroom_is_runs_great(self) -> None:
        verdict = determine_verdict(
            single_gpu_loadable=True,
            safe_context_tokens=20_000,
            decode_tokens_per_sec=50.0,
            vram_headroom_ratio=0.15,
            host_ram_headroom_gb=128.0,
            config=self.config,
        )

        self.assertEqual(verdict, "RUNS GREAT")
