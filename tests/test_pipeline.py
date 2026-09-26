"""End-to-end refresh, offline, with the network stubbed out.

This is the test that proves the whole pipeline is deterministic and needs
no LLM: given fixed source documents it produces a fixed catalog and a fixed
set of agent requests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from which_model import pipeline
from which_model.fetch import Fetched

FIXTURE = Path(__file__).parent / "fixtures" / "go.mdx"

DEV_JSON = json.dumps(
    {
        "opencode-go": {
            "name": "OpenCode Go",
            "models": {
                "glm-5.3-flash": {
                    "id": "glm-5.3-flash",
                    "name": "GLM-5.3-Flash",
                    "release_date": "2026-08-01",
                    "limit": {"context": 200000, "output": 32000},
                    "reasoning": True,
                    "open_weights": True,
                    "modalities": {"input": ["text"], "output": ["text"]},
                }
            },
        }
    }
)

ZEN_JSON = json.dumps(
    {
        "object": "list",
        "data": [{"id": "glm-5.3-flash"}, {"id": "kimi-k3"}, {"id": "legacy-model"}],
    }
)

AA_JSON = json.dumps(
    {
        "tier": "free",
        "pagination": {"has_more": False},
        "data": [
            {
                "slug": "glm-5.3-flash",
                "name": "GLM-5.3-Flash",
                "model_creator": {"name": "Z.ai"},
                "evaluations": {
                    "artificial_analysis_coding_index": 50.0,
                    "artificial_analysis_agentic_index": 44.0,
                    "artificial_analysis_intelligence_index": 39.0,
                },
            }
        ],
    }
)


class FakeFetcher:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def get(self, url: str, *, force: bool = False, headers: dict | None = None) -> Fetched:
        if "go.mdx" in url:
            text = FIXTURE.read_text()
        elif "models.dev" in url:
            text = DEV_JSON
        elif "artificialanalysis" in url:
            text = AA_JSON
        else:
            text = ZEN_JSON
        return Fetched(
            url=url,
            text=text,
            fetched_at=datetime(2026, 9, 25, tzinfo=UTC),
            sha256="deadbeef",
            from_cache=False,
        )


def test_refresh_without_aa_key_resolves_nothing_and_asks_an_agent(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "Fetcher", FakeFetcher)
    monkeypatch.delenv("AA_API_KEY", raising=False)

    # The snapshot directory is the refresh date: pin it so the assertion below
    # keeps passing the day after this test was written.
    snapshot = pipeline.refresh(tmp_path, now=datetime(2026, 9, 25, tzinfo=UTC))

    assert len(snapshot.catalog.models) == 33
    assert snapshot.benchmarks == {}
    assert snapshot.aa_available is False
    assert len(snapshot.requests) == 33

    assert (tmp_path / "data" / "catalog.json").exists()
    assert (tmp_path / "data" / "agent-requests").is_dir()
    assert (tmp_path / "data" / "snapshot" / "2026-09-25" / "catalog.json").exists()

    catalog = pipeline.load_catalog(tmp_path)
    assert catalog is not None
    served = next(r for r in catalog.models if r.name == "GLM-5.3-Flash")
    assert served.served is True
    assert served.context == 200_000
    assert "legacy-model" in catalog.served_undocumented


def test_refresh_with_aa_key_resolves_scores_and_shrinks_the_queue(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "Fetcher", FakeFetcher)
    monkeypatch.setenv("AA_API_KEY", "test-key")

    snapshot = pipeline.refresh(tmp_path, now=datetime(2026, 9, 25, tzinfo=UTC))

    assert snapshot.aa_available is True
    assert snapshot.benchmarks["GLM-5.3-Flash"].scores["coding"] == 50.0
    assert len(snapshot.requests) == 32
    assert all(request.model_name != "GLM-5.3-Flash" for request in snapshot.requests)


def test_stale_cache_warning_is_surfaced(monkeypatch, tmp_path):
    class StaleFetcher(FakeFetcher):
        def get(self, url, *, force=False, headers=None):
            fetched = super().get(url, force=force, headers=headers)
            fetched.stale = True
            return fetched

    monkeypatch.setattr(pipeline, "Fetcher", StaleFetcher)
    monkeypatch.delenv("AA_API_KEY", raising=False)

    snapshot = pipeline.refresh(tmp_path)
    assert len(snapshot.warnings) == 3
    assert all("stale" in warning for warning in snapshot.warnings)


def test_aa_http_error_does_not_kill_refresh(monkeypatch, tmp_path):
    class FailingAAFetcher(FakeFetcher):
        def get(self, url, *, force=False, headers=None):
            if "artificialanalysis" in url:
                raise httpx.HTTPError("mock Artificial Analysis failure")
            return super().get(url, force=force, headers=headers)

    monkeypatch.setattr(pipeline, "Fetcher", FailingAAFetcher)
    monkeypatch.setenv("AA_API_KEY", "test-key")

    snapshot = pipeline.refresh(tmp_path, now=datetime(2026, 9, 25, tzinfo=UTC))

    assert snapshot.aa_available is False
    assert any("Artificial Analysis fetch failed" in warning for warning in snapshot.warnings)
    assert len(snapshot.catalog.models) == 33
