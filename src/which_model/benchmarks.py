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
from datetime import UTC, date, datetime
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


@dataclass
class Override:
    """A curated answer: scores plus the citation that justifies them."""

    scores: dict[str, float] = field(default_factory=dict)
    as_of: date | None = None
    citation: str | None = None


def _as_override(value: Override | dict[str, float]) -> Override:
    """Accept both a plain score dict (tests, callers) and an Override."""
    return value if isinstance(value, Override) else Override(scores=dict(value))


def load_seed(path: Path = SEED_PATH) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    return {
        name: {k: float(v) for k, v in entry.get("scores", entry).items() if isinstance(v, (int, float))}
        for name, entry in payload.get("models", {}).items()
    }


def load_overrides(directory: Path = OVERRIDES_DIR) -> dict[str, Override]:
    if not directory.exists():
        return {}
    overrides: dict[str, Override] = {}
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text())
        name = payload.get("model_name") or path.stem
        scores = payload.get("scores", payload)
        overrides[name] = Override(
            scores={k: float(v) for k, v in scores.items() if isinstance(v, (int, float))},
            as_of=_parse_date(payload.get("as_of")),
            citation=_as_text(payload.get("source")),
        )
    return overrides


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _as_text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def load_aliases(path: Path = ALIASES_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def index_aa(entries: list[AAEntry]) -> dict[str, AAEntry]:
    return {_norm_slug(entry.slug): entry for entry in entries if entry.slug}


def _short_slug(slug: str) -> str:
    """Drop a ``creator/`` prefix from an Artificial Analysis slug."""
    return slug.rsplit("/", 1)[-1]


def _norm_slug(slug: str) -> str:
    """Canonicalise a slug for matching.

    Artificial Analysis writes version numbers with dashes (``v4-1``) while
    the Go docs and models.dev keep the dot (``v4.1``). Comparing on a
    dash-only form lets ``deepseek-v4.1-flash`` match ``deepseek-v4-1-flash``
    instead of silently missing every dotted model.
    """
    return slug.replace(".", "-")


def _aa_indexes(aa_entries: list[AAEntry]) -> tuple[dict[str, AAEntry], dict[str, list[AAEntry]]]:
    """Full-slug and short-slug lookup tables, both canonicalised."""
    aa_index = index_aa(aa_entries)
    short_index: dict[str, list[AAEntry]] = {}
    for entry in aa_entries:
        if entry.slug:
            short_index.setdefault(_norm_slug(_short_slug(entry.slug)), []).append(entry)
    return aa_index, short_index


def resolve(
    catalog: Catalog,
    aa_entries: list[AAEntry],
    *,
    seed: dict[str, dict[str, float]] | None = None,
    overrides: dict[str, Override | dict[str, float]] | None = None,
    aliases: dict[str, str] | None = None,
) -> Resolution:
    seed = seed or {}
    curated = {name: _as_override(value) for name, value in (overrides or {}).items()}
    aliases = aliases or {}
    today = datetime.now(UTC).date()
    aa_index, short_index = _aa_indexes(aa_entries)

    resolution = Resolution(aa_available=bool(aa_entries))

    for record in catalog.models:
        merged: dict[str, float] = {}
        contributors: list[str] = []
        override = curated.get(record.name)

        if record.name in seed:
            merged.update(seed[record.name])
            contributors.append("seed")

        match = _match_aa(record.name, record.model_id, aa_index, short_index, aliases)
        if match is not None:
            merged.update(match.scores)
            contributors.append("artificial_analysis")
            resolution.aa_matched += 1

        if override is not None:
            merged.update(override.scores)
            contributors.append("override")

        # Prefer the date the answer was read over the date of this run.
        as_of = (override.as_of if override is not None else None) or today

        if not merged:
            if override is not None:
                # The agent investigated and found nothing citable. Record it
                # so the model is not requested forever, but keep the scores
                # empty: nothing is invented.
                resolution.records[record.name] = BenchmarkRecord(
                    model_name=record.name,
                    scores={},
                    source="not_found",
                    as_of=as_of,
                    confidence="override",
                )
                continue
            resolution.unresolved.append(record.name)
            continue

        source = "mixed" if len(contributors) > 1 else contributors[0]
        resolution.records[record.name] = BenchmarkRecord(
            model_name=record.name,
            scores=merged,
            source=source,
            matched_slug=match.slug if match else None,
            as_of=as_of,
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
    if alias and _norm_slug(alias) in aa_index:
        return aa_index[_norm_slug(alias)]

    candidates = [_norm_slug(slugify(name))]
    if model_id:
        candidates.append(_norm_slug(model_id))
    for candidate in candidates:
        if candidate in aa_index:
            return aa_index[candidate]

    for candidate in candidates:
        hits = short_index.get(candidate)
        if hits and len(hits) == 1:
            return hits[0]
    return None


# Overrides and Artificial Analysis round to one decimal; anything beyond half
# a point is a real disagreement, not a rounding artefact.
VERIFY_TOLERANCE = 0.6


@dataclass
class Contradiction:
    """A curated answer that disagrees with Artificial Analysis."""

    model_name: str
    key: str
    override: float | None
    aa: float | None
    reason: str  # "value" | "not_found"
    aa_scores: dict[str, float] = field(default_factory=dict)


def check_overrides(
    catalog: Catalog,
    aa_entries: list[AAEntry],
    *,
    overrides: dict[str, Override | dict[str, float]] | None = None,
    aliases: dict[str, str] | None = None,
) -> list[Contradiction]:
    """Cross-check curated overrides against Artificial Analysis.

    Because overrides outrank every automatic source, a wrong override is
    worse than no override: it hides the correct value. This flags the two
    harmful cases only, so it stays quiet on genuinely missing data:

    * a scored key that contradicts AA (``reason="value"``);
    * a ``not_found`` answer for a model AA does score (``reason="not_found"``).

    A model absent from AA, or a key AA does not publish, is not a
    contradiction: there is nothing to disagree with.
    """
    curated = {name: _as_override(value) for name, value in (overrides or {}).items()}
    aliases = aliases or {}
    aa_index, short_index = _aa_indexes(aa_entries)

    problems: list[Contradiction] = []
    for record in catalog.models:
        override = curated.get(record.name)
        if override is None:
            continue
        match = _match_aa(record.name, record.model_id, aa_index, short_index, aliases)
        if match is None:
            continue

        if not override.scores:
            if match.scores:
                problems.append(
                    Contradiction(
                        model_name=record.name,
                        key="*",
                        override=None,
                        aa=None,
                        reason="not_found",
                        aa_scores=dict(match.scores),
                    )
                )
            continue

        for key, value in sorted(override.scores.items()):
            actual = match.scores.get(key)
            if actual is not None and abs(value - actual) > VERIFY_TOLERANCE:
                problems.append(
                    Contradiction(
                        model_name=record.name,
                        key=key,
                        override=value,
                        aa=actual,
                        reason="value",
                    )
                )
    return problems
