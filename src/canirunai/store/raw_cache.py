from __future__ import annotations

import hashlib
from pathlib import Path


class RawCache:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def write_text(self, namespace: str, name: str, content: str, suffix: str = ".txt") -> str:
        safe_name = "".join(char if char.isalnum() else "-" for char in name).strip("-") or "raw"
        digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]
        directory = self.base_dir / namespace
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{safe_name}-{digest}{suffix}"
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.base_dir.parent))
