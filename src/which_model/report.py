"""Terminal dashboard rendering.

Four views over the same computed rows: budget, verbosity, performance and
provenance. Numbers are computed once in :func:`build_rows` so every view
agrees with the others.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .pricing import (
    TaskProfile,
    cost_per_request,
    default_row,
    requests_in_limit,
    requests_per_window,
    verbosity_index,
)
from .schemas import BenchmarkRecord, Catalog, ModelRecord, PricingRow

# Score keys understood by the dashboard, in display order.
SCORE_COLUMNS = (("coding", "coding"), ("agentic", "agentic"))

# Adjacent scores closer than this are shown as one tier: benchmark gaps of a
# point or two are not meaningful (see the SWE-bench significance analysis).
TIER_GAP = 2.0


@dataclass
class Row:
    model: ModelRecord
    row: PricingRow | None
    profile: TaskProfile | None
    cost: float | None = None
    tasks_month: float | None = None
    tasks_5h: float | None = None
    verbosity: float | None = None
    benchmark: BenchmarkRecord | None = None
    pareto: bool = False
    tier: int | None = None


def build_rows(
    catalog: Catalog,
    benchmarks: dict[str, BenchmarkRecord],
) -> tuple[list[Row], int | None]:
    profiles = [m.token_profile.output_tokens for m in catalog.models if m.token_profile]
    baseline = int(median(profiles)) if profiles else None

    rows: list[Row] = []
    for model in catalog.models:
        pricing = default_row(model)
        profile = TaskProfile.from_model(model)
        row = Row(model=model, row=pricing, profile=profile, benchmark=benchmarks.get(model.name))
        if pricing is not None and profile is not None:
            row.cost = cost_per_request(pricing, profile)
            row.tasks_month = requests_in_limit(pricing, profile)
            windows = requests_per_window(pricing, profile)
            row.tasks_5h = windows["5h"]
        if baseline:
            row.verbosity = verbosity_index(profile, baseline)
        rows.append(row)

    _assign_pareto(rows)
    _assign_tiers(rows)
    return rows, baseline


def _assign_pareto(rows: list[Row]) -> None:
    """Mark rows not beaten on both cost and coding score.

    Domination uses weak inequalities with at least one strict, so a model
    that is strictly worse at the same cost does not stay on the frontier.
    """
    scored = [r for r in rows if r.cost is not None and r.benchmark and "coding" in r.benchmark.scores]
    for candidate in scored:
        coding = candidate.benchmark.scores["coding"]
        dominated = any(
            other.cost <= candidate.cost
            and other.benchmark.scores["coding"] >= coding
            and (other.cost < candidate.cost or other.benchmark.scores["coding"] > coding)
            for other in scored
            if other is not candidate
        )
        candidate.pareto = not dominated


def _assign_tiers(rows: list[Row]) -> None:
    """Group models into statistically-plausible performance tiers."""
    scored = sorted(
        (r for r in rows if r.benchmark and "coding" in r.benchmark.scores),
        key=lambda r: r.benchmark.scores["coding"],
        reverse=True,
    )
    tier = 0
    previous: float | None = None
    for row in scored:
        score = row.benchmark.scores["coding"]
        if previous is None or previous - score >= TIER_GAP:
            tier += 1
        row.tier = tier
        previous = score


# --- rendering -------------------------------------------------------------


def _task_cost(value: float | None) -> str:
    """Adaptive precision: a task costs fractions of a cent."""
    if value is None:
        return "-"
    if value >= 0.01:
        return f"${value:,.4f}"
    if value >= 0.001:
        return f"${value:,.5f}"
    return f"${value:,.6f}"


def _source_tag(source: str | None) -> str:
    return {
        "artificial_analysis": "aa",
        "seed": "seed",
        "override": "override",
        "mixed": "mixed",
        None: "—",
    }.get(source, source or "—")


def _number(value: float | None) -> str:
    return "-" if value is None else f"{value:,.0f}"


def _tasks(value: float | None, unlimited: bool) -> str:
    return "∞" if unlimited else _number(value)


def render(console: Console, rows: list[Row], baseline: int | None, view: str, pending: int = 0) -> None:
    console.print(_header(rows, baseline, pending))
    if view == "budget":
        console.print(_budget_table(rows))
    elif view == "verbosity":
        console.print(_verbosity_table(rows, baseline))
    elif view == "perf":
        console.print(_perf_table(rows))
    else:
        raise ValueError(f"unknown view {view!r}")


def _header(rows: list[Row], baseline: int | None, pending: int) -> Panel:
    resolved = sum(1 for row in rows if row.benchmark)
    text = Text()
    text.append(f"{len(rows)} models", style="bold")
    text.append("  ·  ")
    text.append(f"{resolved} with benchmark scores", style="green" if resolved else "yellow")
    if pending:
        text.append("  ·  ")
        text.append(f"{pending} awaiting an agent", style="yellow")
    if baseline:
        text.append(f"  ·  verbosity baseline {baseline} output tokens", style="dim")
    return Panel(text, title="which-model · OpenCode Go", border_style="cyan")


def _budget_table(rows: list[Row]) -> Table:
    table = Table(
        title="Budget: what one task costs inside the Go allowance",
        box=None,
        pad_edge=False,
        expand=False,
    )
    table.add_column("Model", style="bold", no_wrap=True, overflow="ellipsis", max_width=26)
    table.add_column("Allow", justify="right", no_wrap=True)
    table.add_column("$/M in/out", justify="right", no_wrap=True, style="dim")
    table.add_column("Verb", justify="right", no_wrap=True)
    table.add_column("$/task", justify="right", no_wrap=True)
    table.add_column("5h", justify="right", no_wrap=True)
    table.add_column("/mo", justify="right", no_wrap=True)
    table.add_column("coding", justify="right", no_wrap=True, style="magenta")
    table.add_column("src", no_wrap=True, style="dim")

    for row in sorted(rows, key=lambda r: (r.tasks_month is None, -(r.tasks_month or 0))):
        pricing = row.row
        allow = "unlim" if pricing and pricing.limit.unlimited else _number(
            pricing.limit.amount_usd if pricing else None
        )
        unlimited = bool(pricing and pricing.limit.unlimited)
        prices = (
            f"{pricing.input_usd:g}/{pricing.output_usd:g}" if pricing and pricing.input_usd is not None else "-"
        )
        table.add_row(
            ("★ " if row.pareto else "  ") + row.model.name,
            allow,
            prices,
            _number(row.verbosity),
            _task_cost(row.cost),
            _tasks(row.tasks_5h, unlimited),
            _tasks(row.tasks_month, unlimited),
            _score(row, "coding"),
            _source_tag(row.benchmark.source if row.benchmark else None),
        )
    return table


def _verbosity_table(rows: list[Row], baseline: int | None) -> Table:
    table = Table(
        title=f"Verbosity: output tokens per task (100 = baseline {baseline})",
        box=None,
        pad_edge=False,
    )
    table.add_column("Model", style="bold", no_wrap=True, overflow="ellipsis", max_width=26)
    table.add_column("out tok/task", justify="right", no_wrap=True)
    table.add_column("index", justify="right", no_wrap=True)
    table.add_column("share of cost", justify="left", no_wrap=True)
    table.add_column("$/task", justify="right", no_wrap=True)
    table.add_column("$/task x2 out", justify="right", no_wrap=True)
    table.add_column("cost rise", justify="right", no_wrap=True, style="yellow")

    for row in sorted(rows, key=lambda r: (r.verbosity is None, -(r.verbosity or 0))):
        if row.profile is None or row.row is None:
            table.add_row(row.model.name, "-", "-", "[dim]no profile[/dim]", "-", "-", "-")
            continue
        doubled = cost_per_request(row.row, row.profile.with_output_factor(2))
        rise = "-" if not row.cost else f"+{100 * (doubled - row.cost) / row.cost:.0f}%"
        table.add_row(
            row.model.name,
            f"{row.profile.output_tokens:,}",
            _number(row.verbosity),
            _cost_breakdown(row),
            _task_cost(row.cost),
            _task_cost(doubled),
            rise,
        )
    return table


def _cost_breakdown(row: Row, width: int = 20) -> str:
    """Bar showing which token class drives the cost."""
    if row.row is None or row.profile is None:
        return "-"
    parts = {
        "in": (row.profile.input_tokens * (row.row.input_usd or 0.0)),
        "cache": (row.profile.cached_tokens * (row.row.cache_read_usd or 0.0)),
        "out": (row.profile.output_tokens * (row.row.output_usd or 0.0)),
    }
    total = sum(parts.values())
    if total <= 0:
        return "[dim]free[/dim]"
    shares = {key: value / total for key, value in parts.items()}
    colors = {"in": "blue", "cache": "cyan", "out": "yellow"}
    chunks = []
    for key in ("in", "cache", "out"):
        filled = round(shares[key] * width)
        if filled:
            chunks.append(f"[{colors[key]}]{'█' * filled}[/]")
    legend = " ".join(f"{key} {shares[key]:.0%}" for key in ("in", "cache", "out"))
    return "".join(chunks) + "  " + legend


def _perf_table(rows: list[Row]) -> Table:
    table = Table(title="Performance: coding tiers (gaps under 2 points are one tier)", box=None, pad_edge=False)
    table.add_column("Tier", justify="right", style="bold", no_wrap=True)
    table.add_column("Model", style="bold", no_wrap=True, overflow="ellipsis", max_width=26)
    table.add_column("coding", justify="right", no_wrap=True)
    table.add_column("agentic", justify="right", no_wrap=True)
    table.add_column("$/task", justify="right", no_wrap=True)
    table.add_column("/mo", justify="right", no_wrap=True)
    table.add_column("src", style="dim", no_wrap=True)

    ranked = sorted(
        (r for r in rows if r.benchmark),
        key=lambda r: (-(r.benchmark.scores.get("coding") or 0), r.cost if r.cost is not None else 1e9),
    )
    for row in ranked:
        table.add_row(
            str(row.tier or "?"),
            ("★ " if row.pareto else "  ") + row.model.name,
            _score(row, "coding"),
            _score(row, "agentic"),
            _task_cost(row.cost),
            _number(row.tasks_month),
            _source_tag(row.benchmark.source),
        )
    return table


def _score(row: Row, key: str) -> str:
    if row.benchmark is None:
        return "-"
    value = row.benchmark.scores.get(key)
    return "-" if value is None else f"{value:.1f}"


def provenance_panel(catalog: Catalog, benchmarks: dict[str, BenchmarkRecord], pending: int) -> Panel:
    lines = [
        f"docs {catalog.refs.get('docs_url', '?')}",
        f"  sha256 {catalog.refs.get('docs_sha256', '?')[:16]}…  built {catalog.refs.get('built_at', '?')}",
        f"benchmarks resolved: {len(benchmarks)}/{len(catalog.models)}  ·  pending agent: {pending}",
    ]
    if catalog.served_undocumented:
        lines.append(
            f"[yellow]served but undocumented ({len(catalog.served_undocumented)}):[/] "
            + ", ".join(catalog.served_undocumented)
        )
    if catalog.modeled_undocumented:
        lines.append(
            f"[yellow]in models.dev but not in docs ({len(catalog.modeled_undocumented)}):[/] "
            + ", ".join(catalog.modeled_undocumented)
        )
    if catalog.docs_missing_from_models_dev:
        lines.append(
            f"[yellow]in docs but not models.dev ({len(catalog.docs_missing_from_models_dev)}):[/] "
            + ", ".join(catalog.docs_missing_from_models_dev)
        )
    issues = [f"{r.name}: {'; '.join(r.issues)}" for r in catalog.models if r.issues]
    if issues:
        lines.append("")
        lines.append("[bold]per-model issues[/bold]")
        lines.extend(f"  {issue}" for issue in issues)
    return Panel(Group(*[Text.from_markup(line) for line in lines]), title="Provenance", border_style="dim")


def render_provenance(
    console: Console, catalog: Catalog, benchmarks: dict[str, BenchmarkRecord], pending: int
) -> None:
    console.print(provenance_panel(catalog, benchmarks, pending))
