"""The deterministic refresh pipeline.

``refresh`` is the only step that talks to the network, and it calls no LLM.
Everything downstream reads its output, so the expensive part is cached and
the cheap part can be re-run as often as you like.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from . import agent, benchmarks
from . import catalog as catalog_mod
from .fetch import Fetcher
from .schemas import AgentRequest, BenchmarkRecord, Catalog, GoDocs
from .sources import artificial_analysis as aa_mod
from .sources import models_dev, zen

DOCS_URL = "https://raw.githubusercontent.com/anomalyco/opencode/dev/packages/web/src/content/docs/go.mdx"

CATALOG_PATH = Path("data/catalog.json")
BENCHMARKS_PATH = Path("data/benchmarks.json")
META_PATH = Path("data/meta.json")
SNAPSHOT_DIR = Path("data/snapshot")


@dataclass
class Snapshot:
    catalog: Catalog
    benchmarks: dict[str, BenchmarkRecord]
    requests: list[AgentRequest]
    warnings: list[str] = field(default_factory=list)
    aa_available: bool = False


def refresh(
    base_dir: Path = Path("."),
    *,
    force: bool = False,
    ttl: timedelta = timedelta(hours=12),
    now: datetime | None = None,
) -> Snapshot:
    now = now or datetime.now(UTC)
    warnings: list[str] = []
    fetcher = Fetcher(base_dir / "data" / "cache", ttl=ttl)

    docs_fetch = fetcher.get(DOCS_URL, force=force)
    dev_fetch = fetcher.get(models_dev.URL, force=force)
    zen_fetch = fetcher.get(zen.URL, force=force)
    for fetched in (docs_fetch, dev_fetch, zen_fetch):
        if fetched.stale:
            warnings.append(f"using stale cache for {fetched.url}")

    docs = _parse_docs(docs_fetch.text, docs_fetch.sha256)
    dev_models = models_dev.load(dev_fetch.text)
    served = zen.load(zen_fetch.text)

    cat = catalog_mod.build_catalog(
        docs,
        dev_models,
        served,
        refs={
            "docs_url": DOCS_URL,
            "docs_sha256": docs_fetch.sha256,
            "models_dev_sha256": dev_fetch.sha256,
            "zen_sha256": zen_fetch.sha256,
            "built_at": now.isoformat(),
        },
    )

    aa_entries, aa_available = _load_aa(fetcher, force=force, warnings=warnings)
    resolution = benchmarks.resolve(
        cat,
        aa_entries,
        seed=benchmarks.load_seed(base_dir / benchmarks.SEED_PATH),
        overrides=benchmarks.load_overrides(base_dir / benchmarks.OVERRIDES_DIR),
        aliases=benchmarks.load_aliases(base_dir / benchmarks.ALIASES_PATH),
    )

    requests = agent.build_requests(cat, resolution.records)
    agent.write_requests(requests, base_dir / agent.REQUEST_DIR)

    snapshot = Snapshot(
        catalog=cat,
        benchmarks=resolution.records,
        requests=requests,
        warnings=warnings,
        aa_available=aa_available,
    )
    _write(base_dir, snapshot, now)
    return snapshot


def _parse_docs(text: str, sha256: str) -> GoDocs:
    from .docs import parse_go_docs

    return parse_go_docs(text, source_url=DOCS_URL, source_ref=sha256)


def _load_aa(fetcher: Fetcher, *, force: bool, warnings: list[str]) -> tuple[list, bool]:
    api_key = os.environ.get(aa_mod.API_KEY_ENV)
    if not api_key:
        return [], False
    entries: list = []
    try:
        page = 1
        while page <= 20:
            fetched = fetcher.get(
                aa_mod.page_url(page),
                force=force,
                headers={"x-api-key": api_key},
            )
            entries.extend(aa_mod.parse(fetched.text))
            if not aa_mod.has_more(fetched.text):
                break
            page += 1
    except (httpx.HTTPError, json.JSONDecodeError) as error:
        warnings.append(f"Artificial Analysis fetch failed: {error}")
        return [], False
    return entries, True


def _write(base_dir: Path, snapshot: Snapshot, now: datetime) -> None:
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "catalog.json").write_text(snapshot.catalog.model_dump_json(indent=2))
    (data_dir / "benchmarks.json").write_text(
        json.dumps({name: rec.model_dump(mode="json") for name, rec in snapshot.benchmarks.items()}, indent=2)
    )
    (data_dir / "meta.json").write_text(
        json.dumps(
            {
                "built_at": now.isoformat(),
                "warnings": snapshot.warnings,
                "aa_available": snapshot.aa_available,
                "resolved": len(snapshot.benchmarks),
                "pending": len(snapshot.requests),
            },
            indent=2,
        )
    )

    day_dir = base_dir / SNAPSHOT_DIR / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / "catalog.json").write_text(snapshot.catalog.model_dump_json(indent=2))
    (day_dir / "benchmarks.json").write_text(
        json.dumps({name: rec.model_dump(mode="json") for name, rec in snapshot.benchmarks.items()}, indent=2)
    )


def load_catalog(base_dir: Path = Path(".")) -> Catalog | None:
    path = base_dir / CATALOG_PATH
    if not path.exists():
        return None
    return Catalog.model_validate_json(path.read_text())


def load_benchmarks(base_dir: Path = Path(".")) -> dict[str, BenchmarkRecord]:
    path = base_dir / BENCHMARKS_PATH
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {name: BenchmarkRecord.model_validate(entry) for name, entry in raw.items()}


def load_aa_entries(
    base_dir: Path = Path("."),
    *,
    force: bool = False,
    ttl: timedelta = timedelta(hours=12),
) -> tuple[list, bool, list[str]]:
    """Fetch Artificial Analysis entries (through the cache) for auditing."""
    fetcher = Fetcher(base_dir / "data" / "cache", ttl=ttl)
    warnings: list[str] = []
    entries, available = _load_aa(fetcher, force=force, warnings=warnings)
    return entries, available, warnings
