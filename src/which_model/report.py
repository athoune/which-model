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
        if baseline is not None:
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

# Shared explanation for the star prefix, used by every view that ranks models.
STAR_LEGEND = "★  Pareto frontier: no other model is both cheaper AND better scored"

BUDGET_LEGEND = (
    ("Model", "model name; a ★ prefix marks the Pareto frontier (see above)"),
    ("Allow", "monthly included usage for that model, in dollars: $15, $30, $60 or unlimited"),
    ("$/M", "token price per million tokens, input / output"),
    ("Verb", "verbosity index: 100 = median output length across models"),
    ("¢/task", "cost of ONE task, counted in allowance cents — not money you pay"),
    ("5h", "tasks that fit in the 5-hour window (20% of the allowance)"),
    ("/mo", "tasks that fit in the monthly window (100% of the allowance)"),
    ("coding", "benchmark score, 0-100. '-' = not resolved yet"),
    ("src", "where the score comes from: see the source legend below"),
)

VERBOSITY_LEGEND = (
    ("out tok/task", "average output tokens per request: the verbosity signal"),
    ("index", "same value normalised, 100 = median output length across models"),
    ("share of cost", "split of one task's cost: in = fresh input, cache = cached input, out = output"),
    ("¢/task", "cost of one task in allowance cents"),
    ("¢/task x2 out", "same task with twice the output length"),
    ("cost rise", "how much more that would cost"),
)

PERF_LEGEND = (
    ("Tier", "performance tier: scores within 2 points share a tier, because gaps that small are noise"),
    ("coding", "coding benchmark score, 0-100"),
    ("agentic", "agentic/tool-use benchmark score, 0-100"),
    ("¢/task", "cost of one task in allowance cents"),
    ("/mo", "tasks that fit in the monthly allowance"),
    ("src", "where the score comes from: see the source legend below"),
)

SOURCE_LEGEND = (
    "source: aa = Artificial Analysis · seed = curated seed · override = human/agent · "
    "n/a = searched, nothing citable · mixed = several of these"
)


def _legend(view: str, baseline: int | None, compact: bool = False) -> Panel:
    entries = {
        "budget": BUDGET_LEGEND,
        "verbosity": VERBOSITY_LEGEND,
        "perf": PERF_LEGEND,
    }[view]
    width = max(len(label) for label, _ in entries)
    lines = [
        STAR_LEGEND,
        "",
        *[f"[bold]{label.ljust(width)}[/bold]  {text}" for label, text in entries],
        "",
    ]
    if compact:
        lines.append("narrow terminal: the 5h and /mo quotas are in kilo-tasks, k = 1000 tasks")
        lines.append("")
    lines.append(SOURCE_LEGEND)
    if baseline is not None:
        lines.append(f"verbosity baseline: 100 on the index = {baseline} output tokens per task")
    return Panel(Group(*[Text.from_markup(line) for line in lines]), title="Legend", border_style="dim")



def _task_cost(value: float | None) -> str:
    """Cost of one task, in cents.

    One task costs a fraction of a cent in allowance dollars (roughly 0.03¢ to
    3.6¢ across the catalog), so dollars would need four to six decimals and
    blow up the column. Cents keep every value at five characters and match how
    these prices are discussed ("the priciest model is about 3 cents a task").
    """
    if value is None:
        return "-"
    cents = value * 100
    if 0 < cents < 0.01:
        return "<0.01¢"
    return f"{cents:.2f}¢"


def _source_tag(source: str | None) -> str:
    return {
        "artificial_analysis": "aa",
        "seed": "seed",
        "override": "override",
        "mixed": "mixed",
        "not_found": "n/a",
        None: "—",
    }.get(source, source or "—")


def _number(value: float | None) -> str:
    return "-" if value is None else f"{value:,.0f}"


def _tasks(value: float | None, unlimited: bool, compact: bool = False) -> str:
    if unlimited:
        return "∞"
    if value is None:
        return "-"
    if compact and value >= 1000:
        return _kilo_tasks(value)
    return f"{value:,.0f}"


def _kilo_tasks(value: float) -> str:
    """Kilo-tasks for the narrow layout: 226,586 -> 227k, 45,317 -> 45k.

    Below 1000 the plain number is already shorter than any suffixed form, so
    the caller only routes values that actually shrink onto this function.
    """
    if value >= 10_000:
        return f"{value / 1000:.0f}k"
    return f"{value / 1000:.1f}k"


def _natural_width(table: Table) -> int:
    """Intrinsic width a table needs, independent of the console width."""
    return Console(width=10_000, force_terminal=False).measure(table).maximum


def _table(
    rows: list[Row], baseline: int | None, view: str, width: int
) -> tuple[Table, bool]:
    """The view's table, plus whether its quotas were switched to kilo-tasks.

    Whether the terminal is "too thin" is read off the table's own intrinsic
    width instead of a hardcoded column count, so it keeps working when the
    catalog (or its longest model name) changes.
    """
    if view == "verbosity":
        return _verbosity_table(rows, baseline), False
    build = {"budget": _build_budget_table, "perf": _build_perf_table}.get(view)
    if build is None:
        raise ValueError(f"unknown view {view!r}")
    table = build(rows, compact=False)
    if _natural_width(table) <= width:
        return table, False
    return build(rows, compact=True), True


def render(console: Console, rows: list[Row], baseline: int | None, view: str, pending: int = 0) -> None:
    console.print(_header(rows, baseline, pending))
    table, compact = _table(rows, baseline, view, console.width)
    console.print(table)
    console.print(_legend(view, baseline, compact))


def _header(rows: list[Row], baseline: int | None, pending: int) -> Panel:
    scored = sum(1 for row in rows if row.benchmark and row.benchmark.scores)
    not_found = sum(1 for row in rows if row.benchmark and row.benchmark.source == "not_found")
    text = Text()
    text.append(f"{len(rows)} models", style="bold")
    text.append("  ·  ")
    text.append(f"{scored} with benchmark scores", style="green" if scored else "yellow")
    if not_found:
        text.append("  ·  ")
        text.append(f"{not_found} searched, no citable source", style="dim")
    if pending:
        text.append("  ·  ")
        text.append(f"{pending} awaiting an agent", style="yellow")
    if baseline is not None:
        text.append(f"  ·  verbosity baseline {baseline} output tokens", style="dim")
    return Panel(text, title="which-model · OpenCode Go", border_style="cyan")


def _build_budget_table(rows: list[Row], *, compact: bool) -> Table:
    table = Table(
        title="Budget: what one task costs inside the Go allowance",
        box=None,
        pad_edge=False,
        expand=False,
    )
    table.add_column("Model", style="bold", no_wrap=True, overflow="ellipsis", max_width=26)
    table.add_column("Allow", justify="right", no_wrap=True)
    table.add_column("$/M", justify="right", no_wrap=True, style="dim")
    table.add_column("Verb", justify="right", no_wrap=True)
    table.add_column("¢/task", justify="right", no_wrap=True)
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
            _tasks(row.tasks_5h, unlimited, compact=compact),
            _tasks(row.tasks_month, unlimited, compact=compact),
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
    table.add_column("¢/task", justify="right", no_wrap=True)
    table.add_column("¢/task x2 out", justify="right", no_wrap=True)
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


def _build_perf_table(rows: list[Row], *, compact: bool) -> Table:
    table = Table(title="Performance: coding tiers (gaps under 2 points are one tier)", box=None, pad_edge=False)
    table.add_column("Tier", justify="right", style="bold", no_wrap=True)
    table.add_column("Model", style="bold", no_wrap=True, overflow="ellipsis", max_width=26)
    table.add_column("coding", justify="right", no_wrap=True)
    table.add_column("agentic", justify="right", no_wrap=True)
    table.add_column("¢/task", justify="right", no_wrap=True)
    table.add_column("/mo", justify="right", no_wrap=True)
    table.add_column("src", style="dim", no_wrap=True)

    ranked = sorted(
        (r for r in rows if r.benchmark),
        key=lambda r: (-(r.benchmark.scores.get("coding") or 0), r.cost if r.cost is not None else 1e9),
    )
    for row in ranked:
        unlimited = bool(row.row and row.row.limit.unlimited)
        table.add_row(
            str(row.tier or "?"),
            ("★ " if row.pareto else "  ") + row.model.name,
            _score(row, "coding"),
            _score(row, "agentic"),
            _task_cost(row.cost),
            _tasks(row.tasks_month, unlimited, compact=compact),
            _source_tag(row.benchmark.source),
        )
    return table


def _score(row: Row, key: str) -> str:
    if row.benchmark is None:
        return "-"
    value = row.benchmark.scores.get(key)
    return "-" if value is None else f"{value:.1f}"


def _benchmark_summary(catalog: Catalog, benchmarks: dict[str, BenchmarkRecord], pending: int) -> str:
    """Scored, searched-but-empty and still-pending, never conflated."""
    scored = sum(1 for record in benchmarks.values() if record.scores)
    searched = sum(1 for record in benchmarks.values() if record.source == "not_found")
    return (
        f"benchmarks: {scored} scored  ·  {searched} searched, none citable  ·  "
        f"{pending} pending  ·  {len(catalog.models)} models"
    )


def provenance_panel(catalog: Catalog, benchmarks: dict[str, BenchmarkRecord], pending: int) -> Panel:
    lines = [
        f"docs {catalog.refs.get('docs_url', '?')}",
        f"  sha256 {catalog.refs.get('docs_sha256', '?')[:16]}…  built {catalog.refs.get('built_at', '?')}",
        _benchmark_summary(catalog, benchmarks, pending),
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
