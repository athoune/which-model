"""models.dev provider metadata.

models.dev is the database behind OpenCode's own model picker. It is the
best machine-readable source for capabilities (context window, modalities,
reasoning, open weights) but it carries **no benchmark data at all** and
collapses the Go pricing tiers into a single rate, so it must never be used
as the source of truth for cost or scores.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

URL = "https://models.dev/api.json"
PROVIDER_ID = "opencode-go"


@dataclass
class ProviderModel:
    id: str
    name: str
    release_date: str | None = None
    context: int | None = None
    output_limit: int | None = None
    reasoning: bool = False
    open_weights: bool = False
    tool_call: bool = False
    modalities_input: list[str] = field(default_factory=list)
    cost_input: float | None = None
    cost_output: float | None = None
    cost_cache_read: float | None = None


def parse(data: dict, provider: str = PROVIDER_ID) -> dict[str, ProviderModel]:
    """Extract the provider's models keyed by model id."""
    provider_block = data.get(provider)
    if provider_block is None:
        raise KeyError(f"provider {provider!r} not found in models.dev payload")

    parsed: dict[str, ProviderModel] = {}
    for model_id, raw in provider_block.get("models", {}).items():
        limit = raw.get("limit") or {}
        cost = raw.get("cost") or {}
        modalities = raw.get("modalities") or {}
        parsed[model_id] = ProviderModel(
            id=model_id,
            name=raw.get("name") or model_id,
            release_date=raw.get("release_date"),
            context=limit.get("context"),
            output_limit=limit.get("output"),
            reasoning=bool(raw.get("reasoning")),
            open_weights=bool(raw.get("open_weights")),
            tool_call=bool(raw.get("tool_call")),
            modalities_input=list(modalities.get("input") or []),
            cost_input=cost.get("input"),
            cost_output=cost.get("output"),
            cost_cache_read=cost.get("cache_read"),
        )
    return parsed


def load(text: str, provider: str = PROVIDER_ID) -> dict[str, ProviderModel]:
    return parse(json.loads(text), provider=provider)
