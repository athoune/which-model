"""Shared fixtures: the pinned docs fixture and a catalog built from it."""

from __future__ import annotations

from pathlib import Path

import pytest

from which_model import pipeline
from which_model.catalog import build_catalog
from which_model.docs import parse_go_docs
from which_model.schemas import BenchmarkRecord, Catalog
from which_model.sources.models_dev import ProviderModel

FIXTURE = Path(__file__).parent / "fixtures" / "go.mdx"
ROOT = Path(__file__).resolve().parent.parent

# A real `which-model refresh` output, kept in the repository because `data/`
# itself is generated and gitignored: a fresh clone (or CI) has no live copy.
# The files live in `fixtures/data/` to mirror the layout `load_catalog` expects;
# re-pin them with `make fixture` after a refresh.
PINNED_DATA = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def docs():
    return parse_go_docs(FIXTURE.read_text(), source_url="fixture", source_ref="1d6c3c0")


@pytest.fixture
def docs_catalog(docs):
    dev = {"glm-5.3-flash": ProviderModel(id="glm-5.3-flash", name="GLM-5.3-Flash", context=200_000)}
    return build_catalog(docs, dev, ["glm-5.3-flash"])


@pytest.fixture(scope="session")
def shipped_catalog() -> tuple[Catalog, dict[str, BenchmarkRecord]]:
    """The catalog the dashboard is really built from.

    The live one when the working copy has been refreshed, otherwise the pinned
    copy. Tests about real values (column widths, quotas) need a catalog that
    looks like production, not hand-made models; preferring the live data means
    a refresh that widens a column fails on the machine that produced it,
    instead of only in CI.
    """
    live = pipeline.load_catalog(ROOT)
    if live is not None:
        return live, pipeline.load_benchmarks(ROOT)
    pinned = pipeline.load_catalog(PINNED_DATA)
    assert pinned is not None, f"missing pinned catalog fixture in {PINNED_DATA / "data"}"
    return pinned, pipeline.load_benchmarks(PINNED_DATA)
