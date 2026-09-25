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
