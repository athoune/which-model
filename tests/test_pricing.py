"""Tests for the Go budget math."""

from __future__ import annotations

import pytest

from which_model.pricing import (
    TaskProfile,
    cost_per_request,
    requests_in_limit,
    requests_per_window,
    verbosity_index,
)
from which_model.schemas import Limit, PricingRow


def make_row(input_usd: float, output_usd: float, cache_read: float, limit: float | None) -> PricingRow:
    return PricingRow(
        raw_name="Test",
        name="Test",
        input_usd=input_usd,
        output_usd=output_usd,
        cache_read_usd=cache_read,
        limit=Limit(amount_usd=limit, unlimited=limit is None),
    )


def test_cost_per_request_matches_published_mimo_figures():
    """MiMo-V2.6-Flash: 830 in, 71,500 cached, 295 out, $60 allowance."""
    row = make_row(0.14, 0.28, 0.0028, 60)
    profile = TaskProfile(830, 71_500, 295)
    assert cost_per_request(row, profile) == pytest.approx(0.000399)
    assert requests_in_limit(row, profile) == pytest.approx(150_376, rel=0.01)


def test_expensive_output_dominates_cost():
    """Kimi K3 is costly because output tokens are $15/M, not because it is verbose."""
    k3 = make_row(3.00, 15.00, 0.30, 15)
    mimo = make_row(0.14, 0.28, 0.0028, 60)
    profile = TaskProfile(1050, 76_500, 300)
    assert cost_per_request(k3, profile) > 60 * cost_per_request(mimo, profile)


def test_verbose_but_cheap_model_is_not_expensive():
    chatty_cheap = make_row(0.10, 0.20, 0.002, 60)
    terse_pricey = make_row(2.00, 6.00, 0.50, 15)
    verbose = TaskProfile(600, 60_000, 400)
    terse = TaskProfile(600, 60_000, 120)
    assert cost_per_request(chatty_cheap, verbose) < cost_per_request(terse_pricey, terse)


def test_window_shares_are_twenty_and_fifty_percent():
    row = make_row(0.14, 0.28, 0.0028, 60)
    windows = requests_per_window(row, TaskProfile(830, 71_500, 295))
    assert windows["month"] == pytest.approx(windows["week"] * 2)
    assert windows["month"] == pytest.approx(windows["5h"] * 5)


def test_unlimited_model_has_no_cap():
    bunny = make_row(0.0, 0.0, 0.0, None)
    assert requests_in_limit(bunny, TaskProfile(830, 71_500, 295)) is None


def test_verbosity_index_is_relative_to_baseline():
    assert verbosity_index(TaskProfile(1, 1, 240), baseline_output=120) == 200.0
    assert verbosity_index(None, baseline_output=120) is None
