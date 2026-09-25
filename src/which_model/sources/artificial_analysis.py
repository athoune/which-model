"""Artificial Analysis benchmark adapter (free tier).

Requires an API key in ``AA_API_KEY``. The free tier exposes headline
indices and input/output pricing; per-model *token counts* (the independent
verbosity measure) are Pro-only, which is why the dashboard gets verbosity
from the Go docs instead and only takes **scores** from here.

No key, no data: in that case the pipeline falls back to the curated seed
and eventually to the agent queue. Nothing is ever invented.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

BASE_URL = "https://artificialanalysis.ai/api/v2/language/models/free"
API_KEY_ENV = "AA_API_KEY"

# Scores worth showing for coding-agent work, in display order.
SCORE_KEYS = {
    "artificial_analysis_coding_index": "coding",
    "artificial_analysis_agentic_index": "agentic",
    "artificial_analysis_intelligence_index": "intelligence",
}


@dataclass
class AAEntry:
    slug: str
    name: str
    creator: str | None = None
    scores: dict[str, float] = field(default_factory=dict)
    price_input: float | None = None
    price_output: float | None = None


def parse(text: str) -> list[AAEntry]:
    payload = json.loads(text)
    entries: list[AAEntry] = []
    for raw in payload.get("data", []):
        evaluations = raw.get("evaluations") or {}
        scores = {
            short: float(evaluations[key])
            for key, short in SCORE_KEYS.items()
            if evaluations.get(key) is not None
        }
        pricing = raw.get("pricing") or {}
        creator = (raw.get("model_creator") or {}).get("name")
        entries.append(
            AAEntry(
                slug=raw.get("slug") or "",
                name=raw.get("name") or raw.get("slug") or "",
                creator=creator,
                scores=scores,
                price_input=pricing.get("price_1m_input_tokens"),
                price_output=pricing.get("price_1m_output_tokens"),
            )
        )
    return entries


def has_more(text: str) -> bool:
    return bool(json.loads(text).get("pagination", {}).get("has_more"))


def page_url(page: int) -> str:
    return f"{BASE_URL}?page={page}"
