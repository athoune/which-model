"""Pydantic schemas shared across sources and the dashboard.

The normalised catalog is deliberately *lossless* about the docs' tiers:
Go rows can be split by context window or by peak/off-peak, and a naive
"one price per model" model would silently pick the wrong one.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QualifierKind(str, Enum):
    NONE = "none"
    CONTEXT = "context"
    PERIOD = "period"


class Period(str, Enum):
    PEAK = "peak"
    OFF_PEAK = "off_peak"


class Qualifier(BaseModel):
    """The ``(…)`` suffix that makes a pricing row a distinct tier."""

    raw: str | None = None
    kind: QualifierKind = QualifierKind.NONE
    context_threshold: int | None = None
    context_above: bool | None = None
    period: Period | None = None


class Limit(BaseModel):
    """Monthly included usage for a model, plus any promo metadata."""

    amount_usd: float | None = None
    unlimited: bool = False
    promo_from_usd: float | None = None
    note: str | None = None
    promo_until: date | None = None


class TokenProfile(BaseModel):
    """Per-request token counts published by OpenCode for Go traffic.

    ``output_tokens`` is the verbosity signal used by the dashboard.
    """

    input_tokens: int
    cached_tokens: int
    output_tokens: int


class PricingRow(BaseModel):
    raw_name: str
    name: str
    qualifier: Qualifier = Field(default_factory=Qualifier)
    input_usd: float | None = None
    output_usd: float | None = None
    cache_read_usd: float | None = None
    cache_write_usd: float | None = None
    free: bool = False
    limit: Limit = Field(default_factory=Limit)


class RequestsEstimate(BaseModel):
    """The docs' own 'estimated requests' figure, used as a golden check."""

    per_5h: int | None = None
    per_week: int | None = None
    per_month: int | None = None
    per_5h_previous: int | None = None
    per_week_previous: int | None = None
    per_month_previous: int | None = None
    unlimited: bool = False


class DocsModel(BaseModel):
    name: str
    model_id: str | None = None
    endpoint: str | None = None
    rows: list[PricingRow] = Field(default_factory=list)
    token_profile: TokenProfile | None = None
    profile_source: str | None = None
    requests: RequestsEstimate | None = None
    listed: bool = False
    privacy_training: str | None = None
    privacy_retention: str | None = None


class GoDocs(BaseModel):
    fetched_at: datetime = Field(default_factory=utcnow)
    source_url: str
    source_ref: str | None = None
    models: list[DocsModel] = Field(default_factory=list)

    def by_name(self) -> dict[str, DocsModel]:
        return {model.name: model for model in self.models}
