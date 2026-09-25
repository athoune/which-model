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
