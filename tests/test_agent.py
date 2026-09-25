"""The agent hand-off: requests are precise, and stale ones are removed."""

from __future__ import annotations

from which_model import agent
from which_model.schemas import BenchmarkRecord, RequestKind


def test_requests_only_for_unresolved_models(docs_catalog):
    resolved = {
        "GLM-5.3-Flash": BenchmarkRecord(
            model_name="GLM-5.3-Flash",
            scores={"coding": 42.0, "agentic": 30.0, "intelligence": 25.0},
        )
    }
    requests = agent.build_requests(docs_catalog, resolved)
    names = {request.model_name for request in requests}
    assert "GLM-5.3-Flash" not in names
    assert "Kimi K3" in names
    assert all(request.kind == "benchmark" for request in requests)


def test_partial_scores_only_request_the_missing_keys(docs_catalog):
    """A model covered for one metric only is still worth requesting."""
    resolved = {"GLM-5.3-Flash": BenchmarkRecord(model_name="GLM-5.3-Flash", scores={"intelligence": 40.0})}
    requests = agent.build_requests(docs_catalog, resolved)
    partial = next(request for request in requests if request.model_name == "GLM-5.3-Flash")
    assert partial.missing == ["coding", "agentic"]


def test_not_found_models_are_not_requested_again(docs_catalog):
    resolved = {"GLM-5.3-Flash": BenchmarkRecord(model_name="GLM-5.3-Flash", scores={}, source="not_found")}
    names = {request.model_name for request in agent.build_requests(docs_catalog, resolved)}
    assert "GLM-5.3-Flash" not in names


def test_request_markdown_points_at_the_override_file(docs_catalog):
    requests = agent.build_requests(docs_catalog, {})
    markdown = agent.render_request(requests[0])
    assert "data/overrides/" in markdown
    assert "not_found" in markdown


def test_worklist_is_self_contained(docs_catalog):
    requests = agent.build_requests(docs_catalog, {})
    worklist = agent.render_worklist(requests)

    # Mission, format, hard rules and verification must all be present, so an
    # agent can act on this single file without extra context.
    assert "## Mission" in worklist
    assert "## Output format" in worklist
    assert "## Hard rules" in worklist
    assert "Never invent a number" in worklist
    assert "## If no citable value exists" in worklist
    assert "which-model check --offline" in worklist
    # And it must list concrete work, with verbatim names and exact paths.
    assert "GLM-5.3-Flash" in worklist
    assert "data/agent-requests/glm-5.3-flash.md" in worklist
    assert "data/overrides/glm-5.3-flash.json" in worklist
    assert f"**Pending: {len(requests)} model(s).**" in worklist


def test_write_requests_writes_and_keeps_the_worklist(docs_catalog, tmp_path):
    requests = agent.build_requests(docs_catalog, {})
    agent.write_requests(requests, tmp_path)
    worklist = tmp_path / agent.WORKLIST_NAME
    assert worklist.exists()

    # Re-running must not prune the work list as if it were a stale request.
    agent.write_requests(agent.build_requests(docs_catalog, {"GLM-5.3-Flash": _record()}), tmp_path)
    assert worklist.exists()


def _record():
    from which_model.schemas import BenchmarkRecord

    return BenchmarkRecord(model_name="GLM-5.3-Flash", scores={"coding": 1.0})


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


def test_request_kind_is_a_typed_enum():
    """A typo in the kind must fail validation, not travel as a free string."""
    import pytest
    from pydantic import ValidationError

    from which_model.schemas import AgentRequest

    assert AgentRequest(model_name="X", kind="benchmark").kind is RequestKind.BENCHMARK
    with pytest.raises(ValidationError):
        AgentRequest(model_name="X", kind="benchsmark")
