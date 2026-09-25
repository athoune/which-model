"""Parse the OpenCode Go documentation source (``go.mdx``).

We parse the raw MDX from the opencode repository rather than the rendered
HTML page: it is the same content, but stable, diffable and free of layout
noise. Every parser here is tolerant of the emphasis/HTML fragments the docs
use (``<br />``, ``<small>``, ``**bold**``, ``~~struck~~``).
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

from . import text as T
from .schemas import (
    DocsModel,
    GoDocs,
    Limit,
    Period,
    PricingRow,
    Qualifier,
    QualifierKind,
    RequestsEstimate,
    TokenProfile,
)

STRIKE = re.compile(r"~~(.+?)~~")
MODEL_QUALIFIER = re.compile(r"^(?P<name>.+?)\s*\((?P<qualifier>[^()]*)\)\s*$")
SEPARATOR = re.compile(r"^:?-{2,}:?$")
PROFILE_LINE = re.compile(
    r"^[-*]\s*(?P<names>.+?)\s*[—–-]\s*(?P<i>[\d,]+)\s+input,\s*"
    r"(?P<c>[\d,]+)\s+cached,\s*(?P<o>[\d,]+)\s+output tokens per request",
    re.MULTILINE,
)


class Table:
    def __init__(self, headers: list[str], rows: list[list[str]]) -> None:
        self.headers = headers
        self.rows = rows

    def index_of(self, *needles: str) -> int | None:
        for i, header in enumerate(self.headers):
            lowered = header.lower()
            if all(needle.lower() in lowered for needle in needles):
                return i
        return None

    def column(self, *needles: str) -> list[str] | None:
        i = self.index_of(*needles)
        return None if i is None else [row[i] for row in self.rows]


def parse_tables(body: str) -> list[Table]:
    """Extract every pipe table from the markdown body."""
    tables: list[Table] = []
    block: list[list[str]] = []
    in_separator = False

    def flush() -> None:
        nonlocal block, in_separator
        if len(block) >= 2:
            tables.append(Table(block[0], block[2:]))
        block = []
        in_separator = False

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not block:
                block.append(cells)
            elif len(block) == 1:
                if all(SEPARATOR.match(c) for c in cells):
                    block.append(cells)
                else:
                    flush()
                    block.append(cells)
            else:
                block.append(cells)
        else:
            flush()
    flush()
    return tables


def classify_qualifier(raw: str) -> Qualifier:
    lowered = raw.lower()
    if "token" in lowered:
        match = re.search(r"(\d+)\s*k", lowered)
        threshold = int(match.group(1)) * 1000 if match else None
        return Qualifier(
            raw=raw,
            kind=QualifierKind.CONTEXT,
            context_threshold=threshold,
            context_above=raw.strip().startswith(">"),
        )
    if "off-peak" in lowered or "off peak" in lowered:
        return Qualifier(raw=raw, kind=QualifierKind.PERIOD, period=Period.OFF_PEAK)
    if "peak" in lowered:
        return Qualifier(raw=raw, kind=QualifierKind.PERIOD, period=Period.PEAK)
    return Qualifier(raw=raw)


def split_model_cell(raw: str) -> tuple[str, Qualifier]:
    cleaned = T.strip_html(raw)
    match = MODEL_QUALIFIER.match(cleaned)
    if not match:
        return cleaned, Qualifier()
    return match.group("name").strip(), classify_qualifier(match.group("qualifier"))


def parse_price(raw: str) -> tuple[float | None, bool]:
    value = T.strip_html(raw)
    if value.lower() == "free":
        return 0.0, True
    return T.parse_number(value), False


def parse_limit(raw: str) -> Limit:
    body = T.strip_html(raw)
    unlimited = "unlimited" in body.lower()
    promo_match = STRIKE.search(raw)
    promo_from = T.parse_number(promo_match.group(1)) if promo_match else None
    remainder = STRIKE.sub("", body)
    amount_match = re.search(r"\$([\d.,]+)", remainder)
    amount = float(amount_match.group(1).replace(",", "")) if amount_match else None
    small = re.findall(r"<small>(.*?)</small>", raw, re.DOTALL)
    note = " · ".join(T.clean(part) for part in small) or None
    return Limit(
        amount_usd=amount,
        unlimited=unlimited,
        promo_from_usd=promo_from,
        note=note,
        promo_until=_promo_date(raw),
    )


def _promo_date(raw: str, reference: date | None = None) -> date | None:
    match = re.search(r"Ends\s+([A-Z][a-z]{2})\s+(\d{1,2})", T.strip_html(raw))
    if not match:
        return None
    reference = reference or datetime.now(UTC).date()
    try:
        parsed = datetime.strptime(
            f"{match.group(1)} {match.group(2)} {reference.year}", "%b %d %Y"
        ).replace(tzinfo=UTC).date()
    except ValueError:
        return None
    # A promo that "ended" months ago is really next year's edition.
    if parsed < reference - timedelta(days=180):
        parsed = parsed.replace(year=parsed.year + 1)
    return parsed


def parse_requests_cell(raw: str) -> tuple[int | None, int | None, bool]:
    """Return ``(current, previous, unlimited)`` for a requests table cell."""
    if "unlimited" in raw.lower():
        return None, None, True
    strike = STRIKE.search(raw)
    previous = T.parse_int(strike.group(1)) if strike else None
    current = T.parse_int(STRIKE.sub("", raw))
    return current, previous, False


_TRAILING_NUMBER = re.compile(r"(\d[\d.]*)$")


def expand_group(names: str) -> list[str]:
    """Expand a shorthand profile group into individual model names.

    Handles all three shapes used by the docs: ``"Grok 4.7/4.6"``,
    ``"GLM-5.3/5.2/5.1"`` and ``"Kimi K2.7/K2.6"``. The shared prefix is
    whatever precedes the head's trailing number, so trailing letters in
    later parts (the ``K`` of ``K2.6``) are dropped rather than duplicated.
    """
    names = names.strip()
    if "/" not in names:
        return [names]
    parts = names.split("/")
    head_match = _TRAILING_NUMBER.search(parts[0])
    if not head_match:
        return [part.strip() for part in parts]
    prefix = parts[0][: head_match.start()]
    variants = [head_match.group(1)]
    for part in parts[1:]:
        part_match = _TRAILING_NUMBER.search(part)
        variants.append(part_match.group(1) if part_match else part.strip())
    return [f"{prefix}{variant}" for variant in variants]


def _extract_listed_models(body: str) -> list[str]:
    section = re.search(
        r"The current list of models includes:\s*\n(.*?)\n\s*\nThe list of models may change",
        body,
        re.DOTALL,
    )
    if not section:
        return []
    return re.findall(r"^-\s+\*\*(?P<name>.+?)\*\*", section.group(1), re.MULTILINE)


def _table_by_header(tables: list[Table], *needles: str) -> Table | None:
    for table in tables:
        if all(any(needle.lower() in h.lower() for h in table.headers) for needle in needles):
            return table
    return None


def parse_go_docs(body: str, source_url: str, source_ref: str | None = None) -> GoDocs:
    tables = parse_tables(body)

    pricing = _table_by_header(tables, "Input", "Monthly limit")
    requests_table = _table_by_header(tables, "requests per 5 hour")
    endpoints = _table_by_header(tables, "Model ID")
    privacy = _table_by_header(tables, "Model training")

    if pricing is None:
        raise ValueError("pricing table not found in docs source")

    models: dict[str, DocsModel] = {}

    def ensure(name: str) -> DocsModel:
        return models.setdefault(name, DocsModel(name=name))

    for row in pricing.rows:
        raw_name = row[0]
        name, qualifier = split_model_cell(raw_name)
        input_usd, free = parse_price(row[1])
        output_usd, _ = parse_price(row[2])
        cache_read, _ = parse_price(row[3])
        cache_write, _ = parse_price(row[4])
        limit = parse_limit(row[5])
        ensure(name).rows.append(
            PricingRow(
                raw_name=T.strip_html(raw_name),
                name=name,
                qualifier=qualifier,
                input_usd=input_usd,
                output_usd=output_usd,
                cache_read_usd=cache_read,
                cache_write_usd=cache_write,
                free=free,
                limit=limit,
            )
        )

    if requests_table is not None:
        for row in requests_table.rows:
            name = T.strip_html(re.split(r"<br\s*/?>", row[0])[0])
            per_5h, per_5h_prev, unlimited = parse_requests_cell(row[1])
            per_week, per_week_prev, _ = parse_requests_cell(row[2])
            per_month, per_month_prev, _ = parse_requests_cell(row[3])
            ensure(name).requests = RequestsEstimate(
                per_5h=per_5h,
                per_week=per_week,
                per_month=per_month,
                per_5h_previous=per_5h_prev,
                per_week_previous=per_week_prev,
                per_month_previous=per_month_prev,
                unlimited=unlimited,
            )

    if endpoints is not None:
        for row in endpoints.rows:
            name = T.strip_html(row[0])
            model = ensure(name)
            model.model_id = T.clean(row[1])
            model.endpoint = T.clean(row[2])

    if privacy is not None:
        for row in privacy.rows:
            model = ensure(T.strip_html(row[0]))
            model.privacy_training = T.clean(row[1])
            model.privacy_retention = T.clean(row[2])

    for name in _extract_listed_models(body):
        ensure(name).listed = True

    _attach_profiles(body, models)

    return GoDocs(source_url=source_url, source_ref=source_ref, models=list(models.values()))


def _attach_profiles(body: str, models: dict[str, DocsModel]) -> None:
    known = list(models)
    for match in PROFILE_LINE.finditer(body):
        profile = TokenProfile(
            input_tokens=int(match.group("i").replace(",", "")),
            cached_tokens=int(match.group("c").replace(",", "")),
            output_tokens=int(match.group("o").replace(",", "")),
        )
        for group_name in expand_group(match.group("names")):
            target = group_name if group_name in models else _prefix_match(group_name, known)
            if target is None:
                continue
            models[target].token_profile = profile
            models[target].profile_source = match.group("names").strip()


def _prefix_match(name: str, candidates: list[str]) -> str | None:
    """Resolve ``"Kimi K2.7"`` to ``"Kimi K2.7 Code"`` when unambiguous."""
    matches = [c for c in candidates if c.startswith(name)]
    return matches[0] if len(matches) == 1 else None
