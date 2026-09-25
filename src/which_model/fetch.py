"""Cached HTTP fetching.

Refreshing must be cheap and safe to run often, so every response is cached
on disk with a TTL and a content hash. When the network is unavailable we
fall back to the (possibly stale) cache instead of failing: a stale
dashboard beats no dashboard.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

DEFAULT_USER_AGENT = "which-model/0.1 (+https://github.com/; coding model comparison)"


@dataclass
class Fetched:
    url: str
    text: str
    fetched_at: datetime
    sha256: str
    from_cache: bool
    stale: bool = False


def _key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


class Fetcher:
    def __init__(
        self,
        cache_dir: Path,
        ttl: timedelta = timedelta(hours=12),
        timeout: float = 30.0,
    ) -> None:
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.timeout = timeout
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _paths(self, url: str) -> tuple[Path, Path]:
        key = _key(url)
        return self.cache_dir / f"{key}.json", self.cache_dir / f"{key}.body"

    def _read_cache(self, url: str) -> Fetched | None:
        meta_path, body_path = self._paths(url)
        if not (meta_path.exists() and body_path.exists()):
            return None
        try:
            meta = json.loads(meta_path.read_text())
            return Fetched(
                url=url,
                text=body_path.read_text(),
                fetched_at=datetime.fromisoformat(meta["fetched_at"]),
                sha256=meta["sha256"],
                from_cache=True,
            )
        except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
            return None

    def _write_cache(self, url: str, text: str, fetched_at: datetime) -> None:
        meta_path, body_path = self._paths(url)
        body_path.write_text(text)
        meta = {
            "url": url,
            "fetched_at": fetched_at.isoformat(),
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
        meta_path.write_text(json.dumps(meta))

    def get(self, url: str, *, force: bool = False, headers: dict[str, str] | None = None) -> Fetched:
        cached = self._read_cache(url)
        if cached is not None and not force:
            age = datetime.now(UTC) - cached.fetched_at
            if age <= self.ttl:
                return cached

        request_headers = {"User-Agent": DEFAULT_USER_AGENT}
        if headers:
            request_headers.update(headers)
        try:
            response = httpx.get(
                url,
                timeout=self.timeout,
                follow_redirects=True,
                headers=request_headers,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            if cached is not None:
                cached.stale = True
                return cached
            raise

        fetched_at = datetime.now(UTC)
        self._write_cache(url, response.text, fetched_at)
        return Fetched(
            url=url,
            text=response.text,
            fetched_at=fetched_at,
            sha256=hashlib.sha256(response.text.encode()).hexdigest(),
            from_cache=False,
        )


def sleep(seconds: float) -> None:  # pragma: no cover - convenience for scripts
    time.sleep(seconds)
