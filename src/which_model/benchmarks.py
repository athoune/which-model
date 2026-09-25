"""Resolve benchmark scores for catalog models.

Precedence, per score key, highest first:

1. ``data/overrides/<model>.json`` — human/agent curated, always wins;
2. Artificial Analysis free tier — when an API key is configured;
3. ``data/benchmarks.seed.json`` — versioned fallback so the app is useful
   offline and on a fresh clone.

Anything left unresolved is *reported as unresolved*. No score is ever
inferred from a similar-sounding model: that is exactly the kind of silent
fabrication this project exists to avoid.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .catalog import slugify
from .schemas import BenchmarkRecord, Catalog
from .sources.artificial_analysis import AAEntry

SEED_PATH = Path("data/benchmarks.seed.json")
OVERRIDES_DIR = Path("data/overrides")
ALIASES_PATH = Path("data/aliases.json")


@dataclass
class Resolution:
    records: dict[str, BenchmarkRecord] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)
    aa_matched: int = 0
    aa_available: bool = False


def load_seed(path: Path = SEED_PATH) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    return {
        name: {k: float(v) for k, v in entry.get("scores", entry).items() if isinstance(v, (int, float))}
        for name, entry in payload.get("models", {}).items()
    }


def load_overrides(directory: Path = OVERRIDES_DIR) -> dict[str, dict[str, float]]:
    if not directory.exists():
        return {}
    overrides: dict[str, dict[str, float]] = {}
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text())
        name = payload.get("model_name") or path.stem
        scores = payload.get("scores", payload)
        overrides[name] = {k: float(v) for k, v in scores.items() if isinstance(v, (int, float))}
    return overrides


def load_aliases(path: Path = ALIASES_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def index_aa(entries: list[AAEntry]) -> dict[str, AAEntry]:
    return {entry.slug: entry for entry in entries if entry.slug}


def _short_slug(slug: str) -> str:
    """Drop a ``creator/`` prefix from an Artificial Analysis slug."""
    return slug.rsplit("/", 1)[-1]


def resolve(
    catalog: Catalog,
    aa_entries: list[AAEntry],
    *,
    seed: dict[str, dict[str, float]] | None = None,
    overrides: dict[str, dict[str, float]] | None = None,
    aliases: dict[str, str] | None = None,
) -> Resolution:
    seed = seed or {}
    overrides = overrides or {}
    aliases = aliases or {}
    aa_index = index_aa(aa_entries)
    short_index: dict[str, list[AAEntry]] = {}
    for entry in aa_entries:
        if entry.slug:
            short_index.setdefault(_short_slug(entry.slug), []).append(entry)

    resolution = Resolution(aa_available=bool(aa_entries))

    for record in catalog.models:
        merged: dict[str, float] = {}
        contributors: list[str] = []

        if record.name in seed:
            merged.update(seed[record.name])
            contributors.append("seed")

        match = _match_aa(record.name, record.model_id, aa_index, short_index, aliases)
        if match is not None:
            merged.update(match.scores)
            contributors.append("artificial_analysis")
            resolution.aa_matched += 1

        if record.name in overrides:
            merged.update(overrides[record.name])
            contributors.append("override")

        if not merged:
            resolution.unresolved.append(record.name)
            continue

        source = "mixed" if len(contributors) > 1 else contributors[0]
        resolution.records[record.name] = BenchmarkRecord(
            model_name=record.name,
            scores=merged,
            source=source,
            matched_slug=match.slug if match else None,
            as_of=datetime.now(UTC).date(),
            confidence="override" if "override" in contributors else "auto",
        )

    return resolution


def _match_aa(
    name: str,
    model_id: str | None,
    aa_index: dict[str, AAEntry],
    short_index: dict[str, list[AAEntry]],
    aliases: dict[str, str],
) -> AAEntry | None:
    """Deterministic match only: alias, exact id, then unambiguous short slug.

    Deliberately no substring matching. ``GLM-5.3`` must not silently inherit
    ``GLM-5.3-Flash`` scores; that is what the alias file and the agent queue
    are for.
    """
    alias = aliases.get(name)
    if alias and alias in aa_index:
        return aa_index[alias]

    candidates = [slugify(name)]
    if model_id:
        candidates.append(model_id)
    for candidate in candidates:
        if candidate in aa_index:
            return aa_index[candidate]

    for candidate in candidates:
        hits = short_index.get(candidate)
        if hits and len(hits) == 1:
            return hits[0]
    return None
