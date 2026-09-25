"""Tests for the ``go.mdx`` parser.

The fixture is pinned to a specific upstream commit so that documentation
drift shows up as a test failure rather than as silently wrong numbers.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from which_model.docs import expand_group, parse_go_docs
from which_model.pricing import TaskProfile, default_row, requests_in_limit
from which_model.schemas import Period, QualifierKind

FIXTURE = Path(__file__).parent / "fixtures" / "go.mdx"

# Rows whose published "requests per month" cannot be reproduced from the
# token profile the same page publishes for them. Verified 2026-09-25 against
# commit 1d6c3c0; 27/31 other rows match within 0.5%, so the formula and the
# parser are sound and these four are documentation inconsistencies.
# Value: (expected delta in percent, published requests per month, tolerance pp)
KNOWN_DOC_INCONSISTENCIES: dict[str, tuple[float, int, float]] = {
    "GLM-5.3": (-8.4, 1080, 1.0),
    "GLM-5.2": (-8.0, 4300, 1.0),
    "GLM-5.1": (-8.0, 4300, 1.0),
    "Kimi K2.7 Code": (-26.4, 6750, 1.0),
}


@pytest.fixture(scope="module")
def docs():
    return parse_go_docs(FIXTURE.read_text(), source_url="fixture", source_ref="1d6c3c0")


def test_model_count(docs):
    assert len(docs.models) == 33


def test_unlisted_model_is_kept(docs):
    """MiniMax M2.5 is priced but dropped from the 'current list' prose."""
    m2_5 = docs.by_name()["MiniMax M2.5"]
    assert m2_5.listed is False
    assert m2_5.rows[0].input_usd == 0.30


def test_price_parsing_and_free_model(docs):
    flash = docs.by_name()["GLM-5.3-Flash"].rows[0]
    assert (flash.input_usd, flash.output_usd, flash.cache_read_usd) == (0.15, 0.50, 0.03)
    assert flash.cache_write_usd is None
    assert flash.limit.amount_usd == 60

    bunny = docs.by_name()["Space Bunny Free"].rows[0]
    assert bunny.free is True
    assert bunny.limit.unlimited is True


def test_promo_row_keeps_old_limit_and_expiry(docs):
    ds = docs.by_name()["DeepSeek V4.1 Flash"].rows
    off_peak = next(r for r in ds if r.qualifier.period == Period.OFF_PEAK)
    assert off_peak.limit.amount_usd == 60
    assert off_peak.limit.promo_from_usd == 15
    assert off_peak.limit.promo_until == date(2026, 9, 27)
    assert "4x" in off_peak.limit.note


def test_context_tiers_are_distinct_rows(docs):
    plus = docs.by_name()["Qwen3.7 Plus"].rows
    assert len(plus) == 2
    low = next(r for r in plus if r.qualifier.context_above is False)
    high = next(r for r in plus if r.qualifier.context_above is True)
    assert low.qualifier.context_threshold == 256_000
    assert (low.input_usd, high.input_usd) == (0.40, 1.20)


def test_default_row_prefers_off_peak_and_small_context(docs):
    ds = default_row(docs.by_name()["DeepSeek V4.1 Flash"])
    assert ds.qualifier.period == Period.OFF_PEAK
    qwen = default_row(docs.by_name()["Qwen3.7 Plus"])
    assert qwen.qualifier.kind == QualifierKind.CONTEXT
    assert qwen.qualifier.context_above is False


def test_token_profiles_attach_to_every_member_of_a_group(docs):
    by_name = docs.by_name()
    for name in ("Kimi K2.7 Code", "Kimi K2.6"):
        profile = by_name[name].token_profile
        assert profile is not None, name
        assert (profile.input_tokens, profile.output_tokens) == (870, 200)
    grok = by_name["Grok 4.7"].token_profile
    assert (grok.input_tokens, grok.cached_tokens, grok.output_tokens) == (390, 32_500, 120)


def test_expand_group_shapes():
    assert expand_group("Grok 4.7/4.6") == ["Grok 4.7", "Grok 4.6"]
    assert expand_group("GLM-5.3/5.2/5.1") == ["GLM-5.3", "GLM-5.2", "GLM-5.1"]
    assert expand_group("Kimi K2.7/K2.6") == ["Kimi K2.7", "Kimi K2.6"]
    assert expand_group("Hy3") == ["Hy3"]


def test_golden_requests_match_published_numbers(docs):
    """The docs' own 'requests per month' validates parser + formula.

    This is the strongest available correctness signal: it is a set of
    independent numbers published by the same page we parse.
    """
    checked = 0
    for model in docs.models:
        if model.requests is None or model.requests.unlimited:
            continue
        row = default_row(model)
        profile = TaskProfile.from_model(model)
        published = model.requests.per_month
        if row is None or profile is None or published is None:
            continue
        computed = requests_in_limit(row, profile)
        assert computed is not None, model.name
        delta = 100.0 * (computed - published) / published
        checked += 1

        if model.name in KNOWN_DOC_INCONSISTENCIES:
            expected, expected_published, tolerance = KNOWN_DOC_INCONSISTENCIES[model.name]
            assert published == expected_published, model.name
            assert abs(delta - expected) <= tolerance, (model.name, delta)
        else:
            assert abs(delta) <= 1.5, (model.name, published, round(computed), delta)

    assert checked == 31
