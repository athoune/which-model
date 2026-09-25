"""CLI smoke tests using Typer's runner."""

from __future__ import annotations

from typer.testing import CliRunner

from which_model.cli import app

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
