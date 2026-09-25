"""Shared fixtures: the pinned docs fixture and a catalog built from it."""

from __future__ import annotations

from pathlib import Path

import pytest

from which_model.catalog import build_catalog
from which_model.docs import parse_go_docs
from which_model.sources.models_dev import ProviderModel

FIXTURE = Path(__file__).parent / "fixtures" / "go.mdx"


@pytest.fixture(scope="session")
def docs():
    return parse_go_docs(FIXTURE.read_text(), source_url="fixture", source_ref="1d6c3c0")


@pytest.fixture
def docs_catalog(docs):
    dev = {"glm-5.3-flash": ProviderModel(id="glm-5.3-flash", name="GLM-5.3-Flash", context=200_000)}
    return build_catalog(docs, dev, ["glm-5.3-flash"])
