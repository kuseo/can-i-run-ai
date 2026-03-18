from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from canirunai.collectors.huggingface_client import HuggingFaceClient
from canirunai.collectors.wikipedia_client import WikipediaClient
from canirunai.config.loader import HuggingFaceConfig, SourcePageConfig, WikipediaConfig


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class ClientVerboseLoggingTest(unittest.TestCase):
    def test_wikipedia_client_logs_request_url_when_verbose(self) -> None:
        config = WikipediaConfig(
            user_agent="canirunai-test",
            request_delay_sec=0.0,
            cpu_intel=SourcePageConfig(page_url="https://example.com/intel"),
            cpu_amd_ryzen=SourcePageConfig(page_url="https://example.com/amd"),
            gpu_nvidia=SourcePageConfig(page_url="https://example.com/nvidia"),
            gpu_amd=SourcePageConfig(page_url="https://example.com/gpu-amd"),
        )
        client = WikipediaClient(config, verbose=True)

        with (
            patch("canirunai.collectors.wikipedia_client.urlopen", return_value=_FakeResponse({"ok": True})),
            patch("canirunai.collectors.wikipedia_client.time.sleep"),
            patch("canirunai.collectors.wikipedia_client.logger.info") as info,
        ):
            payload = client._request({"action": "parse", "page": "List_of_Intel_processors", "format": "json"})

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(info.call_args.args[0], "Fetching URL {}")
        self.assertIn("https://en.wikipedia.org/w/api.php?action=parse&page=List_of_Intel_processors&format=json", info.call_args.args[1])

    def test_huggingface_client_logs_request_url_when_verbose(self) -> None:
        config = HuggingFaceConfig(
            endpoint="https://huggingface.co",
            request_delay_sec=0.0,
            teams=["Qwen"],
        )
        client = HuggingFaceClient(config, verbose=True)

        with (
            patch(
                "canirunai.collectors.huggingface_client.urlopen",
                return_value=_FakeResponse({"id": "Qwen/Qwen2.5-7B-Instruct"}),
            ),
            patch("canirunai.collectors.huggingface_client.time.sleep"),
            patch("canirunai.collectors.huggingface_client.logger.info") as info,
        ):
            payload = client.model_info("Qwen/Qwen2.5-7B-Instruct")

        self.assertEqual(payload["id"], "Qwen/Qwen2.5-7B-Instruct")
        self.assertEqual(info.call_args.args[0], "Fetching URL {}")
        self.assertEqual(info.call_args.args[1], "https://huggingface.co/api/models/Qwen/Qwen2.5-7B-Instruct")
