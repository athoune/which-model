"""Cached HTTP fetcher behaviour."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from which_model.fetch import Fetcher


def _write(url: str, cache_dir: Path, meta: dict, body: str) -> None:
    fetcher = Fetcher(cache_dir, ttl=timedelta(hours=1))
    meta_path, body_path = fetcher._paths(url)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta))
    body_path.write_text(body)


def test_cache_round_trip(tmp_path: Path) -> None:
    fetcher = Fetcher(tmp_path, ttl=timedelta(hours=1))
    url = "https://example.com/data"
    fetcher._write_cache(url, "payload", datetime(2026, 9, 25, tzinfo=UTC))

    cached = fetcher._read_cache(url)

    assert cached is not None
    assert cached.text == "payload"
    assert cached.sha256 == "239f59ed55e737c77147cf55ad0c1b030b6d7ee748a7426952f9b852d5a935e5"


def test_corrupt_meta_json_is_treated_as_miss(tmp_path: Path) -> None:
    url = "https://example.com/data"
    fetcher = Fetcher(tmp_path, ttl=timedelta(hours=1))
    meta_path, body_path = fetcher._paths(url)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text("{not valid json")
    body_path.write_text("payload")

    assert fetcher._read_cache(url) is None


def test_missing_meta_fields_are_treated_as_miss(tmp_path: Path) -> None:
    url = "https://example.com/data"
    _write(
        url,
        tmp_path,
        meta={"url": url, "fetched_at": datetime(2026, 9, 25, tzinfo=UTC).isoformat()},
        body="payload",
    )

    fetcher = Fetcher(tmp_path, ttl=timedelta(hours=1))
    assert fetcher._read_cache(url) is None


def test_invalid_fetched_at_is_treated_as_miss(tmp_path: Path) -> None:
    url = "https://example.com/data"
    _write(
        url,
        tmp_path,
        meta={"url": url, "fetched_at": "not-a-date", "sha256": "abc"},
        body="payload",
    )

    fetcher = Fetcher(tmp_path, ttl=timedelta(hours=1))
    assert fetcher._read_cache(url) is None


@pytest.mark.parametrize(
    "meta,description",
    [
        ({"url": "x", "fetched_at": "2026-09-25T00:00:00+00:00"}, "missing sha256"),
        ({"url": "x", "sha256": "abc"}, "missing fetched_at"),
    ],
)
def test_incomplete_meta_is_treated_as_miss(meta: dict, description: str, tmp_path: Path) -> None:
    url = "https://example.com/data"
    _write(url, tmp_path, meta=meta, body="payload")

    fetcher = Fetcher(tmp_path, ttl=timedelta(hours=1))
    assert fetcher._read_cache(url) is None, description
