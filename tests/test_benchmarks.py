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


def test_dotted_name_matches_dashed_aa_slug(docs_catalog):
    """The docs keep the dot; AA writes a dash (``glm-5.3`` vs ``glm-5-3``)."""
    resolution = benchmarks.resolve(
        docs_catalog,
        [AAEntry(slug="glm-5-3-flash", name="GLM 5.3 Flash", scores={"coding": 71.5})],
    )
    assert resolution.records["GLM-5.3-Flash"].scores["coding"] == 71.5
    assert resolution.records["GLM-5.3-Flash"].source == "artificial_analysis"


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


def test_override_date_is_preserved(docs_catalog):
    """The date the value was read matters more than the date of this run."""
    from datetime import date

    overrides = {
        "GLM-5.3-Flash": benchmarks.Override(scores={"coding": 77.0}, as_of=date(2026, 1, 2))
    }
    record = benchmarks.resolve(docs_catalog, [], overrides=overrides).records["GLM-5.3-Flash"]
    assert record.scores["coding"] == 77.0
    assert record.as_of == date(2026, 1, 2)


def test_override_without_a_date_falls_back_to_today(docs_catalog):
    from datetime import UTC, datetime

    record = benchmarks.resolve(
        docs_catalog, [], overrides={"GLM-5.3-Flash": {"coding": 77.0}}
    ).records["GLM-5.3-Flash"]
    assert record.as_of == datetime.now(UTC).date()


AA_FLASH = AAEntry(slug="glm-5-3-flash", name="GLM 5.3 Flash", scores={"coding": 71.5})


def test_check_overrides_flags_a_wrong_value(docs_catalog):
    problems = benchmarks.check_overrides(
        docs_catalog, [AA_FLASH], overrides={"GLM-5.3-Flash": {"coding": 99.0}}
    )
    assert [(p.model_name, p.key, p.reason) for p in problems] == [
        ("GLM-5.3-Flash", "coding", "value")
    ]
    assert problems[0].override == 99.0
    assert problems[0].aa == 71.5


def test_check_overrides_flags_a_false_not_found(docs_catalog):
    problems = benchmarks.check_overrides(docs_catalog, [AA_FLASH], overrides={"GLM-5.3-Flash": {}})
    assert len(problems) == 1
    assert problems[0].reason == "not_found"
    assert problems[0].aa_scores == {"coding": 71.5}


def test_check_overrides_is_quiet_when_there_is_nothing_to_disagree_with(docs_catalog):
    # Exact agreement is not a contradiction.
    assert (
        benchmarks.check_overrides(
            docs_catalog, [AA_FLASH], overrides={"GLM-5.3-Flash": {"coding": 71.5}}
        )
        == []
    )
    # No AA entry at all: an override cannot contradict what is absent.
    assert (
        benchmarks.check_overrides(
            docs_catalog, [], overrides={"GLM-5.3-Flash": {"coding": 99.0}}
        )
        == []
    )
    # A model with no override is never reported.
    assert benchmarks.check_overrides(docs_catalog, [AA_FLASH], overrides={}) == []
