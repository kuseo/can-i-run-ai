from __future__ import annotations

import unittest

from canirunai.collectors.seed_catalog import cpu_seed_specs, gpu_seed_specs, model_seed_specs
from canirunai.config.loader import ScoringConfig
from canirunai.scoring.engine import ScoringEngine


class ScoringEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ScoringEngine(ScoringConfig())
        self.cpu = cpu_seed_specs()[0]
        self.gpu_4090 = gpu_seed_specs()[0]
        self.qwen_bf16 = model_seed_specs()[0]
        self.deepseek_r1 = model_seed_specs()[2]

    def test_impossible_when_weights_do_not_fit(self) -> None:
        report = self.engine.score(
            cpus=[self.cpu],
            gpus=[self.gpu_4090],
            memory_gb=64,
            model=self.deepseek_r1,
        )
        self.assertEqual(report.verdict, "IMPOSSIBLE")
        self.assertEqual(report.context_estimate.max_supported_context_tokens, 0)

    def test_supported_model_has_non_zero_throughput(self) -> None:
        report = self.engine.score(
            cpus=[self.cpu],
            gpus=[self.gpu_4090],
            memory_gb=64,
            model=self.qwen_bf16,
        )
        self.assertGreater(report.throughput_estimate.decode_tokens_per_sec, 0)
        self.assertGreater(report.context_estimate.safe_context_tokens, 0)
