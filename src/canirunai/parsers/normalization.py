from __future__ import annotations

import re


def clean_name(value: str) -> str:
    return " ".join(value.strip().split())


def lookup_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_name(value).casefold())
