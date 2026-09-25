"""Benchmark resolution tests: precedence, and above all, no fabrication."""

from __future__ import annotations

from which_model import benchmarks
from which_model.sources.artificial_analysis import AAEntry


def test_override_beats_aa_and_seed(docs_catalog):
    resolution = benchmarks.resolve(
        docs_catalog,
        [AAEntry(slug="glm-5.3-flash", name="GLM-5.3-Flash", scores={"coding": 50.0})],
        seed={"GLM-5.3-Flash": {"coding": 40.0}},
        overrides={"GLM-5.3-Flash": {"coding": 99.0}},
    )
    record = resolution.records["GLM-5.3-Flash"]
    assert record.scores["coding"] == 99.0
    assert record.confidence == "override"
    assert record.source == "mixed"


def test_aa_used_when_no_override(docs_catalog):
    resolution = benchmarks.resolve(
        docs_catalog,
        [AAEntry(slug="glm-5.3-flash", name="GLM-5.3-Flash", scores={"coding": 50.0})],
        seed={"GLM-5.3-Flash": {"coding": 40.0}},
    )
    assert resolution.records["GLM-5.3-Flash"].scores["coding"] == 50.0
    assert resolution.aa_matched == 1


def test_seed_used_when_aa_absent(docs_catalog):
    resolution = benchmarks.resolve(docs_catalog, [], seed={"GLM-5.3-Flash": {"coding": 40.0}})
    assert resolution.records["GLM-5.3-Flash"].scores["coding"] == 40.0
    assert resolution.records["GLM-5.3-Flash"].source == "seed"
    assert resolution.aa_available is False


def test_unmatched_model_is_reported_not_invented(docs_catalog):
    resolution = benchmarks.resolve(docs_catalog, [AAEntry(slug="some-other-lab/model", name="Other")])
    assert "GLM-5.3-Flash" in resolution.unresolved
    assert "GLM-5.3-Flash" not in resolution.records


def test_alias_wins_over_slug_guess(docs_catalog):
    resolution = benchmarks.resolve(
        docs_catalog,
        [AAEntry(slug="z-ai/glm-5.3-flash-thinking", name="GLM", scores={"coding": 61.0})],
        aliases={"GLM-5.3-Flash": "z-ai/glm-5.3-flash-thinking"},
    )
    assert resolution.records["GLM-5.3-Flash"].scores["coding"] == 61.0


def test_prefix_family_does_not_inherit_scores(docs_catalog):
    """GLM-5.3 must not silently inherit GLM-5.3-Flash's scores."""
    resolution = benchmarks.resolve(
        docs_catalog,
        [AAEntry(slug="glm-5.3-flash", name="GLM-5.3-Flash", scores={"coding": 50.0})],
    )
    assert resolution.records["GLM-5.3-Flash"].scores["coding"] == 50.0
    assert "GLM-5.3" in resolution.unresolved


def test_creator_prefixed_slug_matches_unambiguously(docs_catalog):
    resolution = benchmarks.resolve(
        docs_catalog,
        [AAEntry(slug="z-ai/glm-5.3-flash", name="GLM-5.3-Flash", scores={"coding": 55.0})],
    )
    assert resolution.records["GLM-5.3-Flash"].scores["coding"] == 55.0
    assert resolution.records["GLM-5.3-Flash"].matched_slug == "z-ai/glm-5.3-flash"


def test_ambiguous_short_slug_does_not_match(docs_catalog):
    resolution = benchmarks.resolve(
        docs_catalog,
        [
            AAEntry(slug="lab-a/glm-5.3-flash", name="A", scores={"coding": 1.0}),
            AAEntry(slug="lab-b/glm-5.3-flash", name="B", scores={"coding": 2.0}),
        ],
    )
    assert "GLM-5.3-Flash" in resolution.unresolved


def test_not_found_override_records_without_inventing_a_score(docs_catalog):
    """An agent that searched and found nothing must stop the requests."""
    resolution = benchmarks.resolve(docs_catalog, [], overrides={"GLM-5.3-Flash": {}})
    record = resolution.records["GLM-5.3-Flash"]
    assert record.scores == {}
    assert record.source == "not_found"
    assert "GLM-5.3-Flash" not in resolution.unresolved
