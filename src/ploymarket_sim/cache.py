from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from time import time
from typing import Any


@dataclass(frozen=True)
class CachePolicy:
    enabled: bool
    directory: str
    ttl_seconds: int
    stale_if_error: bool


@dataclass(frozen=True)
class CacheEntry:
    url: str
    fetched_at: float
    payload: Any

    @property
    def age_seconds(self) -> float:
        return time() - self.fetched_at


@dataclass(frozen=True)
class CacheStats:
    enabled: bool
    directory: str
    file_count: int
    total_bytes: int


class JsonCache:
    def __init__(self, policy: CachePolicy):
        self.policy = policy

    def get_fresh(self, url: str) -> Any | None:
        entry = self._read(url)
        if entry is None:
            return None
        if entry.age_seconds <= self.policy.ttl_seconds:
            return entry.payload
        return None

    def get_stale(self, url: str) -> Any | None:
        entry = self._read(url)
        return entry.payload if entry else None

    def set(self, url: str, payload: Any) -> None:
        if not self.policy.enabled:
            return
        path = self._path_for_url(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"url": url, "fetched_at": time(), "payload": payload}
        path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")

    def stats(self) -> CacheStats:
        directory = Path(self.policy.directory)
        files = list(directory.glob("*.json")) if directory.exists() else []
        return CacheStats(
            enabled=self.policy.enabled,
            directory=self.policy.directory,
            file_count=len(files),
            total_bytes=sum(path.stat().st_size for path in files),
        )

    def _read(self, url: str) -> CacheEntry | None:
        if not self.policy.enabled:
            return None
        path = self._path_for_url(url)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return CacheEntry(str(raw["url"]), float(raw["fetched_at"]), raw["payload"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _path_for_url(self, url: str) -> Path:
        digest = sha256(url.encode("utf-8")).hexdigest()
        return Path(self.policy.directory) / f"{digest}.json"
