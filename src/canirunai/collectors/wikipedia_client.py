from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from loguru import logger

from ..config.loader import WikipediaConfig


@dataclass(slots=True)
class WikipediaPageSnapshot:
    page_url: str
    revision_id: int | None
    html: str


class WikipediaClient:
    def __init__(self, config: WikipediaConfig, *, verbose: bool = False) -> None:
        self.config = config
        self.verbose = verbose

    def fetch_page_snapshot(self, page_url: str) -> WikipediaPageSnapshot:
        title = urlsplit(page_url).path.rsplit("/", 1)[-1]
        revision_payload = self._request(
            {
                "action": "query",
                "prop": "revisions",
                "rvprop": "ids",
                "titles": title,
                "format": "json",
            }
        )
        pages = revision_payload["query"]["pages"]
        page = next(iter(pages.values()))
        revisions = page.get("revisions", [])
        revision_id = revisions[0]["revid"] if revisions else None
        parse_payload = self._request(
            {
                "action": "parse",
                "page": title,
                "prop": "text",
                "format": "json",
            }
        )
        html = parse_payload["parse"]["text"]["*"]
        return WikipediaPageSnapshot(page_url=page_url, revision_id=revision_id, html=html)

    def _request(self, params: dict[str, str]) -> dict:
        url = "https://en.wikipedia.org/w/api.php?" + urlencode(params)
        if self.verbose:
            logger.info("Fetching URL {}", url)
        request = Request(url, headers={"User-Agent": self.config.user_agent})
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        time.sleep(self.config.request_delay_sec)
        return payload
