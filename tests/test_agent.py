"""The agent hand-off: requests are precise, and stale ones are removed."""

from __future__ import annotations

from which_model import agent
from which_model.schemas import BenchmarkRecord


def test_requests_only_for_unresolved_models(docs_catalog):
    resolved = {"GLM-5.3-Flash": BenchmarkRecord(model_name="GLM-5.3-Flash", scores={"coding": 42.0})}
    requests = agent.build_requests(docs_catalog, resolved)
    names = {request.model_name for request in requests}
    assert "GLM-5.3-Flash" not in names
    assert "Kimi K3" in names
    assert all(request.kind == "benchmark" for request in requests)


def test_request_markdown_points_at_the_override_file(docs_catalog):
    requests = agent.build_requests(docs_catalog, {})
    markdown = agent.render_request(requests[0])
    assert "data/overrides/" in markdown
    assert "Only fill a value you can cite" in markdown


def test_write_requests_prunes_stale_files(docs_catalog, tmp_path):
    requests = agent.build_requests(docs_catalog, {})
    written = agent.write_requests(requests, tmp_path)
    assert len(written) == len(requests)

    stale = tmp_path / "obsolete-model.md"
    stale.write_text("old")
    agent.write_requests(requests, tmp_path)
    assert not stale.exists()


def test_pricing_request_when_a_model_has_no_rows():
    from which_model.schemas import Catalog, ModelRecord

    catalog = Catalog(models=[ModelRecord(name="Mystery", in_docs=False)])
    requests = agent.build_requests(catalog, {})
    assert len(requests) == 1
    assert requests[0].kind == "pricing"
