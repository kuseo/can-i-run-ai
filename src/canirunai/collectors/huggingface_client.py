from __future__ import annotations

import json
import time
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ..config.loader import HuggingFaceConfig


class HuggingFaceClient:
    def __init__(self, config: HuggingFaceConfig) -> None:
        self.config = config

    def model_info(self, repo_id: str) -> dict:
        url = f"{self.config.endpoint}/api/models/{quote(repo_id, safe='/')}"
        return self._request(url)

    def list_models(self, *, author: str | None = None, limit: int | None = None) -> list[dict]:
        query = {
            "pipeline_tag": self.config.pipeline_tag,
            "limit": limit or self.config.max_models_per_team,
        }
        if author:
            query["author"] = author
        url = f"{self.config.endpoint}/api/models?{urlencode(query)}"
        payload = self._request(url)
        if not isinstance(payload, list):
            raise TypeError("Unexpected Hugging Face response payload")
        return payload

    def _request(self, url: str) -> dict | list[dict]:
        request = Request(url, headers={"User-Agent": "canirunai/0.1"})
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        time.sleep(self.config.request_delay_sec)
        return payload
