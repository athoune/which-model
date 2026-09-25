"""Cost math for the Go subscription.

The crucial correction over a naive "tokens x price" reading: under Go you
pay a flat monthly fee, and the per-token prices only *decrement* a
per-model monthly allowance. The number that matters is therefore
"how many tasks fit in the allowance", not "how many dollars does it cost".
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .schemas import DocsModel, Period, PricingRow, QualifierKind

TOKENS_PER_MILLION = 1_000_000
LIMIT_WINDOWS = {"5h": 0.20, "week": 0.50, "month": 1.00}


@dataclass(frozen=True)
class TaskProfile:
    """A user-supplied coding-agent request shape."""

    input_tokens: int
    cached_tokens: int
    output_tokens: int

    def with_output_factor(self, factor: float) -> TaskProfile:
        return replace(self, output_tokens=round(self.output_tokens * factor))

    @classmethod
    def from_model(cls, model: DocsModel) -> TaskProfile | None:
        if model.token_profile is None:
            return None
        profile = model.token_profile
        return cls(profile.input_tokens, profile.cached_tokens, profile.output_tokens)


def cost_per_request(row: PricingRow, profile: TaskProfile) -> float:
    """Cost of one request in "allowance dollars"."""
    price_in = row.input_usd or 0.0
    price_cached = row.cache_read_usd or 0.0
    price_out = row.output_usd or 0.0
    return (
        profile.input_tokens * price_in
        + profile.cached_tokens * price_cached
        + profile.output_tokens * price_out
    ) / TOKENS_PER_MILLION


def requests_in_limit(row: PricingRow, profile: TaskProfile) -> float | None:
    """How many requests fit in the monthly allowance (None when unlimited)."""
    if row.limit.unlimited:
        return None
    if row.limit.amount_usd is None:
        return None
    cost = cost_per_request(row, profile)
    if cost <= 0:
        return None
    return row.limit.amount_usd / cost


def requests_per_window(row: PricingRow, profile: TaskProfile) -> dict[str, float | None]:
    """Requests allowed per 5h / week / month windows."""
    monthly = requests_in_limit(row, profile)
    if monthly is None:
        return {window: None for window in LIMIT_WINDOWS}
    return {window: monthly * share for window, share in LIMIT_WINDOWS.items()}


def default_row(model: DocsModel) -> PricingRow | None:
    """Choose the representative tier for headline numbers.

    Preference order: off-peak over peak, and the lowest context tier over
    the "above threshold" one, because those are what a normal session hits.
    """
    if not model.rows:
        return None
    ranked = sorted(model.rows, key=_row_rank)
    return ranked[0]


def _row_rank(row: PricingRow) -> tuple:
    qualifier = row.qualifier
    period_rank = 0 if qualifier.period == Period.OFF_PEAK else 1
    context_rank = 0 if qualifier.kind == QualifierKind.CONTEXT and not qualifier.context_above else 1
    if qualifier.kind != QualifierKind.CONTEXT:
        context_rank = 0
    threshold = qualifier.context_threshold or 0
    return (period_rank, context_rank, threshold)


def verbosity_index(profile: TaskProfile | None, baseline_output: int) -> float | None:
    """Relative verbosity, 100 == baseline output length.

    ``None`` when the profile is unknown or the baseline is not positive:
    dividing by a zero median would be meaningless.
    """
    if profile is None or baseline_output <= 0:
        return None
    return 100.0 * profile.output_tokens / baseline_output
