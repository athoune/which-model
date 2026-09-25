"""CLI smoke tests using Typer's runner."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from which_model.cli import app
from which_model.schemas import Catalog, Limit, ModelRecord, PricingRow

runner = CliRunner()


def test_check_without_a_cached_catalog_exits_two(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["check", "--offline"])
    assert result.exit_code == 2
    assert "No cached catalog" in result.output


def test_report_rejects_unknown_view(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["report", "--view", "nonsense", "--offline"])
    assert result.exit_code == 2
    assert "Unknown view" in result.output


def test_report_rejects_offline_with_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["report", "--offline", "--force"])
    assert result.exit_code == 2
    assert "--offline and --force" in result.output


def test_check_json_emits_one_parseable_document(tmp_path, monkeypatch):
    """`check --json` must print a JSON array, not a JSON string of one."""
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    catalog = Catalog(
        models=[
            ModelRecord(
                name="Solo",
                rows=[
                    PricingRow(
                        raw_name="Solo",
                        name="Solo",
                        input_usd=1.0,
                        output_usd=2.0,
                        limit=Limit(amount_usd=10.0),
                    )
                ],
            )
        ]
    )
    (data / "catalog.json").write_text(catalog.model_dump_json())

    result = runner.invoke(app, ["check", "--offline", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert payload[0]["model_name"] == "Solo"


def test_verify_flags_an_override_that_contradicts_aa(tmp_path, monkeypatch):
    from which_model import pipeline
    from which_model.sources.artificial_analysis import AAEntry

    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data"
    (data / "overrides").mkdir(parents=True)
    catalog = Catalog(
        models=[
            ModelRecord(
                name="Solo",
                model_id="solo-model",
                rows=[PricingRow(raw_name="Solo", name="Solo", input_usd=1.0)],
            )
        ]
    )
    (data / "catalog.json").write_text(catalog.model_dump_json())
    (data / "overrides" / "solo.json").write_text(
        json.dumps({"model_name": "Solo", "scores": {"coding": 99.0}})
    )
    monkeypatch.setattr(
        pipeline,
        "load_aa_entries",
        lambda *args, **kwargs: (
            [AAEntry(slug="solo-model", name="Solo", scores={"coding": 50.0})],
            True,
            [],
        ),
    )

    result = runner.invoke(app, ["verify"])

    assert result.exit_code == 1
    assert "contradiction" in result.output.lower()
    assert "override=99" in result.output
    assert "AA=50" in result.output


def test_verify_passes_when_every_override_agrees(tmp_path, monkeypatch):
    from which_model import pipeline
    from which_model.sources.artificial_analysis import AAEntry

    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data"
    (data / "overrides").mkdir(parents=True)
    catalog = Catalog(
        models=[
            ModelRecord(
                name="Solo",
                model_id="solo-model",
                rows=[PricingRow(raw_name="Solo", name="Solo", input_usd=1.0)],
            )
        ]
    )
    (data / "catalog.json").write_text(catalog.model_dump_json())
    monkeypatch.setattr(
        pipeline,
        "load_aa_entries",
        lambda *args, **kwargs: (
            [AAEntry(slug="solo-model", name="Solo", scores={"coding": 50.0})],
            True,
            [],
        ),
    )

    result = runner.invoke(app, ["verify"])

    assert result.exit_code == 0
    assert "No contradiction" in result.output
