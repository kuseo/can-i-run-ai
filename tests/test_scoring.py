from __future__ import annotations

import unittest

from canirunai.collectors.seed_catalog import cpu_seed_specs, gpu_seed_specs, model_seed_specs
from canirunai.config.loader import ScoringConfig
from canirunai.gpu_compute import normalize_gpu_compute_metrics
from canirunai.scoring.engine import ScoringEngine
from canirunai.schemas.base import RawReference
from canirunai.schemas.cpu import CpuSpec
from canirunai.schemas.gpu import GpuSpec
from canirunai.schemas.model import ArchitectureHint, ModelSpec, VariantSpec, WeightsInfo


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

    def test_missing_architecture_details_fall_back_to_parameter_based_context_estimate(self) -> None:
        cpu = CpuSpec(
            canonical_name="Intel Core i7 9700E",
            aliases=[],
            vendor="intel",
            cores=8,
            threads=8,
            source_url="https://example.com/cpu",
            raw_ref=RawReference(cache_key="cpu"),
        )
        gpu = GpuSpec(
            canonical_name="NVIDIA H100 GPU accelerator (PCIe card)",
            aliases=[],
            vendor="nvidia",
            memory_size_gib=80.0,
            memory_bandwidth_gbs=2039.0,
            processing_power_fp32_gflops=51_200.0,
            processing_power_fp16_gflops=756_400.0,
            processing_power_bf16_gflops=756_400.0,
            source_url="https://example.com/gpu",
            raw_ref=RawReference(cache_key="gpu"),
        )
        model = ModelSpec(
            canonical_name="openai/gpt-oss-20b@mxfp4",
            aliases=[],
            source_url="https://example.com/model",
            raw_ref=RawReference(cache_key="model"),
            hf_repo_id="openai/gpt-oss-20b",
            variant=VariantSpec(precision="bf16", quantization="mxfp4", format="safetensors"),
            task="text-generation",
            architecture_hint=ArchitectureHint(model_type="gpt_oss"),
            num_parameters=21_511_953_984,
            weights=WeightsInfo(total_size_bytes=41_382_448_021),
        )

        report = self.engine.score(
            cpus=[cpu],
            gpus=[gpu],
            memory_gb=256,
            model=model,
        )

        self.assertNotEqual(report.verdict, "IMPOSSIBLE")
        self.assertGreaterEqual(report.context_estimate.safe_context_tokens, self.engine.config.min_context_tokens)

    def test_gpt_oss_mxfp4_uses_runtime_weight_estimate_and_active_parameters(self) -> None:
        cpu = CpuSpec(
            canonical_name="Intel Core i7 9700E",
            aliases=[],
            vendor="intel",
            cores=8,
            threads=8,
            source_url="https://example.com/cpu",
            raw_ref=RawReference(cache_key="cpu"),
        )
        gpu = GpuSpec(
            canonical_name="NVIDIA H100 GPU accelerator (PCIe card)",
            aliases=[],
            vendor="nvidia",
            memory_size_gib=80.0,
            memory_bandwidth_gbs=2039.0,
            processing_power_fp32_gflops=51_200.0,
            processing_power_fp16_gflops=756_400.0,
            processing_power_bf16_gflops=756_400.0,
            source_url="https://example.com/gpu",
            raw_ref=RawReference(cache_key="gpu"),
        )
        model = ModelSpec(
            canonical_name="openai/gpt-oss-120b@mxfp4",
            aliases=[],
            source_url="https://example.com/model",
            raw_ref=RawReference(cache_key="model"),
            hf_repo_id="openai/gpt-oss-120b",
            variant=VariantSpec(precision="bf16", quantization="mxfp4", format="safetensors"),
            task="text-generation",
            architecture_hint=ArchitectureHint(model_type="gpt_oss"),
            num_parameters=120_412_337_472,
            weights=WeightsInfo(total_size_bytes=195_851_052_807),
        )

        report = self.engine.score(
            cpus=[cpu],
            gpus=[gpu],
            memory_gb=128,
            model=model,
        )

        self.assertNotEqual(report.verdict, "IMPOSSIBLE")
        self.assertLess(report.wide.memory_estimate.weights_vram_gb, 80.0)
        self.assertGreater(report.context_estimate.safe_context_tokens, 2048)
        self.assertGreater(report.throughput_estimate.decode_tokens_per_sec, 0)

    def test_low_precision_models_prefer_low_precision_gpu_compute(self) -> None:
        gpu = GpuSpec(
            canonical_name="NVIDIA H100 GPU accelerator (PCIe card)",
            aliases=[],
            vendor="nvidia",
            memory_size_gib=80.0,
            memory_bandwidth_gbs=2039.0,
            processing_power_fp32_gflops=51_200.0,
            processing_power_fp16_gflops=756_400.0,
            processing_power_bf16_gflops=756_400.0,
            source_url="https://example.com/gpu",
            raw_ref=RawReference(cache_key="gpu"),
        )
        model = ModelSpec(
            canonical_name="openai/gpt-oss-20b@mxfp4",
            aliases=[],
            source_url="https://example.com/model",
            raw_ref=RawReference(cache_key="model"),
            hf_repo_id="openai/gpt-oss-20b",
            variant=VariantSpec(precision="bf16", quantization="mxfp4", format="safetensors"),
            task="text-generation",
            architecture_hint=ArchitectureHint(model_type="gpt_oss"),
            num_parameters=21_511_953_984,
            weights=WeightsInfo(total_size_bytes=41_382_448_021),
        )

        decode_tps = self.engine.estimator.single_gpu_decode_tps(model=model, gpu=gpu)
        report = self.engine.score(cpus=[self.cpu], gpus=[gpu], memory_gb=256, model=model)

        self.assertGreater(decode_tps, self.engine.config.great_decode_tps)
        self.assertEqual(report.verdict, "RUNS GREAT")

    def test_nvidia_tensor_core_fallback_derives_low_precision_metric_when_catalog_is_flat(self) -> None:
        gpu = GpuSpec(
            canonical_name="NVIDIA RTX 6000 Ada Generation",
            aliases=[],
            vendor="nvidia",
            memory_size_gib=48.0,
            memory_bandwidth_gbs=960.0,
            cuda_compute_capability="8.9",
            processing_power_fp32_gflops=91_060.0,
            processing_power_fp16_gflops=91_060.0,
            processing_power_bf16_gflops=91_060.0,
            source_url="https://example.com/gpu",
            raw_ref=RawReference(cache_key="gpu"),
        )
        model = ModelSpec(
            canonical_name="Qwen/Qwen2.5-14B@bf16",
            aliases=[],
            source_url="https://example.com/model",
            raw_ref=RawReference(cache_key="model"),
            hf_repo_id="Qwen/Qwen2.5-14B",
            variant=VariantSpec(precision="bf16", format="safetensors"),
            task="text-generation",
            architecture_hint=ArchitectureHint(model_type="qwen2"),
            num_parameters=14_770_033_664,
            weights=WeightsInfo(total_size_bytes=29_540_067_328),
        )

        compute_gflops = self.engine.estimator._gpu_compute_gflops_for_model(model=model, gpu=gpu)

        self.assertEqual(compute_gflops, 364_240.0)

    def test_normalize_gpu_compute_metrics_upgrades_flat_catalog_values(self) -> None:
        gpu = GpuSpec(
            canonical_name="NVIDIA RTX A5000",
            aliases=[],
            vendor="nvidia",
            memory_size_gib=24.0,
            memory_bandwidth_gbs=768.0,
            cuda_compute_capability="8.6",
            processing_power_fp32_gflops=27_770.0,
            processing_power_fp16_gflops=27_770.0,
            processing_power_bf16_gflops=27_770.0,
            source_url="https://example.com/gpu",
            raw_ref=RawReference(cache_key="gpu"),
        )

        normalized = normalize_gpu_compute_metrics(gpu)

        self.assertEqual(normalized.processing_power_fp16_gflops, 111_080.0)
        self.assertEqual(normalized.processing_power_bf16_gflops, 111_080.0)
