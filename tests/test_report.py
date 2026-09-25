"""Dashboard computation tests, using synthetic models on purpose.

No real benchmark score is ever fabricated for the shipped catalog; these
fixtures exist only to exercise the rendering and ranking logic.
"""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from which_model import report
from which_model.schemas import (
    BenchmarkRecord,
    Catalog,
    Limit,
    ModelRecord,
    PricingRow,
    TokenProfile,
)


def model(name: str, input_usd: float, output_usd: float, limit: float, output_tokens: int) -> ModelRecord:
    return ModelRecord(
        name=name,
        rows=[
            PricingRow(
                raw_name=name,
                name=name,
                input_usd=input_usd,
                output_usd=output_usd,
                cache_read_usd=0.0,
                limit=Limit(amount_usd=limit),
            )
        ],
        token_profile=TokenProfile(input_tokens=1_000, cached_tokens=50_000, output_tokens=output_tokens),
    )


def bench(name: str, coding: float, agentic: float) -> BenchmarkRecord:
    return BenchmarkRecord(model_name=name, scores={"coding": coding, "agentic": agentic}, source="seed")


def sample_catalog() -> tuple[Catalog, dict[str, BenchmarkRecord]]:
    catalog = Catalog(
        models=[
            model("Cheap Great", 0.10, 0.20, 60, 200),
            model("Cheap Weak", 0.10, 0.20, 60, 200),
            model("Pricey Great", 2.00, 6.00, 15, 200),
            model("No Score", 0.30, 1.20, 60, 200),
        ]
    )
    benchmarks = {
        "Cheap Great": bench("Cheap Great", 70.0, 60.0),
        "Cheap Weak": bench("Cheap Weak", 40.0, 30.0),
        "Pricey Great": bench("Pricey Great", 71.0, 65.0),
    }
    return catalog, benchmarks


def test_rows_compute_cost_and_tasks():
    catalog, benchmarks = sample_catalog()
    rows, baseline = report.build_rows(catalog, benchmarks)
    by_name = {row.model.name: row for row in rows}
    assert baseline == 200
    assert by_name["Cheap Great"].cost == 0.00014
    assert by_name["Cheap Great"].tasks_month is not None
    assert by_name["Cheap Great"].verbosity == 100.0


def test_pareto_marks_only_undominated_models():
    catalog, benchmarks = sample_catalog()
    rows, _ = report.build_rows(catalog, benchmarks)
    by_name = {row.model.name: row for row in rows}
    # Cheap Great beats Cheap Weak on score at equal cost.
    assert by_name["Cheap Great"].pareto is True
    assert by_name["Cheap Weak"].pareto is False
    # Pricey Great scores higher, so both cheap and pricey stay undominated.
    assert by_name["Pricey Great"].pareto is True


def test_tiers_group_close_scores():
    catalog, benchmarks = sample_catalog()
    rows, _ = report.build_rows(catalog, benchmarks)
    by_name = {row.model.name: row for row in rows}
    # 70 and 72 are within the 2-point noise gap, so they share tier 1.
    assert by_name["Cheap Great"].tier == 1
    assert by_name["Pricey Great"].tier == 1
    assert by_name["Cheap Weak"].tier == 2
    assert by_name["No Score"].tier is None


def _render(view: str) -> str:
    catalog, benchmarks = sample_catalog()
    rows, baseline = report.build_rows(catalog, benchmarks)
    stream = StringIO()
    console = Console(file=stream, width=140, force_terminal=False)
    report.render(console, rows, baseline, view, pending=1)
    return stream.getvalue()


def test_every_view_renders():
    for view in ("budget", "verbosity", "perf"):
        output = _render(view)
        assert "which-model" in output
        assert "Cheap Great" in output


def test_legend_explains_the_star_and_every_column():
    legends = {
        "budget": report.BUDGET_LEGEND,
        "verbosity": report.VERBOSITY_LEGEND,
        "perf": report.PERF_LEGEND,
    }
    for view, entries in legends.items():
        output = _render(view)
        assert "Pareto frontier" in output
        assert "Legend" in output
        # Every abbreviated header must be spelled out in the legend.
        for label, _ in entries:
            assert label in output, (view, label)


def test_provenance_view_renders_reconciliation():
    catalog, _ = sample_catalog()
    catalog.served_undocumented = ["legacy-model"]
    stream = StringIO()
    console = Console(file=stream, width=140, force_terminal=False)
    report.render_provenance(console, catalog, {}, pending=2)
    output = stream.getvalue()
    assert "legacy-model" in output
    assert "pending agent: 2" in output


def test_verbosity_view_shows_cost_sensitivity():
    output = _render("verbosity")
    assert "x2 out" in output
    assert "cost rise" in output
