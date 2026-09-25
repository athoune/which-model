"""Catalog reconciliation tests."""

from __future__ import annotations

from which_model.catalog import build_catalog, slugify
from which_model.sources.models_dev import ProviderModel


def test_slugify_matches_real_model_ids():
    assert slugify("DeepSeek V4.1 Flash") == "deepseek-v4.1-flash"
    assert slugify("MiMo-V2.6-Flash") == "mimo-v2.6-flash"
    assert slugify("Muse Spark 1.3 Contributor") == "muse-spark-1.3-contributor"
    assert slugify("Hy4 preview") == "hy4-preview"


def test_links_docs_to_models_dev_by_endpoint_id(docs_catalog):
    record = next(r for r in docs_catalog.models if r.name == "GLM-5.3-Flash")
    assert record.in_models_dev is True
    assert record.context == 200_000
    assert record.served is True


def test_flags_undocumented_served_models(docs):
    catalog = build_catalog(docs, {}, ["glm-5.3-flash", "brand-new-model"])
    assert "brand-new-model" in catalog.served_undocumented
    assert "glm-5.3-flash" not in catalog.served_undocumented


def test_flags_modeled_but_undocumented(docs):
    dev = {"ghost-model": ProviderModel(id="ghost-model", name="Ghost")}
    catalog = build_catalog(docs, dev, [])
    assert "ghost-model" in catalog.modeled_undocumented


def test_records_issue_when_absent_from_models_dev(docs_catalog):
    record = next(r for r in docs_catalog.models if r.name == "Kimi K3")
    assert record.in_models_dev is False
    assert any("models.dev" in issue for issue in record.issues)


def test_flags_models_dev_price_that_matches_no_tier(docs):
    """A price the two sources disagree on must surface, not be swallowed."""
    dev = {"glm-5.3-flash": ProviderModel(id="glm-5.3-flash", name="GLM-5.3-Flash", cost_input=9.99)}
    catalog = build_catalog(docs, dev, [])
    record = next(r for r in catalog.models if r.name == "GLM-5.3-Flash")
    assert any("prices match no documented tier" in issue for issue in record.issues)


def test_no_price_issue_when_models_dev_matches_a_tier(docs):
    dev = {
        "glm-5.3-flash": ProviderModel(
            id="glm-5.3-flash",
            name="GLM-5.3-Flash",
            cost_input=0.15,
            cost_output=0.5,
            cost_cache_read=0.03,
        )
    }
    catalog = build_catalog(docs, dev, [])
    record = next(r for r in catalog.models if r.name == "GLM-5.3-Flash")
    assert not any("match no documented tier" in issue for issue in record.issues)


def test_tiered_model_is_not_flagged_when_a_tier_matches(docs):
    """models.dev collapses tiers, so matching any single tier is agreement."""
    dev = {
        "qwen3.7-plus": ProviderModel(
            id="qwen3.7-plus",
            name="Qwen3.7 Plus",
            cost_input=1.2,
            cost_output=4.8,
            cost_cache_read=0.12,
        )
    }
    catalog = build_catalog(docs, dev, [])
    record = next(r for r in catalog.models if r.name == "Qwen3.7 Plus")
    assert not any("match no documented tier" in issue for issue in record.issues)
