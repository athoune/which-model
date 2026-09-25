"""Command line entry point.

Three verbs, in order of how often you use them:

* ``refresh`` — deterministic fetch + normalise, never calls an LLM;
* ``report``  — render the dashboard (refreshes through the cache by default);
* ``check``   — refresh, then exit non-zero if an agent has work to do.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from . import agent, benchmarks, pipeline
from . import report as dashboard

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)

VIEWS = ("budget", "verbosity", "perf", "provenance")


def _base_dir() -> Path:
    return Path.cwd()


def _snapshot_offline(base_dir: Path) -> pipeline.Snapshot:
    catalog = pipeline.load_catalog(base_dir)
    if catalog is None:
        err_console.print("[red]No cached catalog. Run `which-model refresh` first.[/red]")
        raise typer.Exit(code=2)
    benchmarks = pipeline.load_benchmarks(base_dir)
    requests = agent.build_requests(catalog, benchmarks)
    return pipeline.Snapshot(catalog=catalog, benchmarks=benchmarks, requests=requests)


def _current(base_dir: Path, *, refresh: bool, force: bool) -> pipeline.Snapshot:
    if refresh:
        return pipeline.refresh(base_dir, force=force)
    return _snapshot_offline(base_dir)


@app.command()
def refresh(
    force: bool = typer.Option(False, "--force", help="Ignore the cache TTL and refetch everything."),
    ttl_hours: float = typer.Option(12.0, "--ttl-hours", help="Cache lifetime in hours."),
) -> None:
    """Fetch the sources, rebuild the catalog, and write the cache."""
    base_dir = _base_dir()
    snapshot = pipeline.refresh(base_dir, force=force, ttl=timedelta(hours=ttl_hours))

    scored = sum(1 for record in snapshot.benchmarks.values() if record.scores)
    not_found = sum(1 for record in snapshot.benchmarks.values() if record.source == "not_found")
    console.print(
        f"[bold]{len(snapshot.catalog.models)}[/bold] models  ·  "
        f"{scored} with scores  ·  "
        f"{not_found} searched, none citable  ·  "
        f"{len(snapshot.requests)} awaiting an agent"
    )
    if not snapshot.aa_available:
        console.print(
            "[dim]No Artificial Analysis key (AA_API_KEY): scores come from the seed "
            "and overrides only.[/dim]"
        )
    for warning in snapshot.warnings:
        err_console.print(f"[yellow]warning:[/yellow] {warning}")
    if not snapshot.benchmarks:
        console.print(
            "[yellow]No benchmark scores resolved. Run `which-model check` to see the "
            "requests to hand to an agent.[/yellow]"
        )
    if snapshot.requests:
        console.print(
            f"[dim]Work list for an agent: {agent.REQUEST_DIR}/{agent.WORKLIST_NAME}[/dim]"
        )


@app.command()
def report(
    view: Annotated[str, typer.Option("--view", "-v", help=f"One of {', '.join(VIEWS)}.")] = "budget",
    offline: bool = typer.Option(False, "--offline", help="Use the cached catalog, do not hit the network."),
    force: bool = typer.Option(False, "--force", help="Force a refresh before rendering."),
    width: int = typer.Option(0, "--width", help="Force the output width (0 = detect terminal)."),
) -> None:
    """Render the dashboard."""
    if view not in VIEWS:
        err_console.print(f"[red]Unknown view {view!r}. Choose from {', '.join(VIEWS)}.[/red]")
        raise typer.Exit(code=2)
    if width > 0:
        console.width = width

    if offline and force:
        err_console.print("[red]--offline and --force are mutually exclusive.[/red]")
        raise typer.Exit(code=2)

    base_dir = _base_dir()
    snapshot = _current(base_dir, refresh=not offline, force=force)
    rows, baseline = dashboard.build_rows(snapshot.catalog, snapshot.benchmarks)

    if view == "provenance":
        dashboard.render_provenance(console, snapshot.catalog, snapshot.benchmarks, len(snapshot.requests))
    else:
        dashboard.render(console, rows, baseline, view, pending=len(snapshot.requests))
    for warning in snapshot.warnings:
        err_console.print(f"[yellow]warning:[/yellow] {warning}")


@app.command()
def check(
    offline: bool = typer.Option(False, "--offline", help="Use the cached catalog, do not hit the network."),
    as_json: bool = typer.Option(False, "--json", help="Emit the requests as JSON."),
) -> None:
    """Exit non-zero and describe the work an agent must do."""
    base_dir = _base_dir()
    snapshot = _current(base_dir, refresh=not offline, force=False)

    if as_json:
        console.print_json(data=[request.model_dump(mode="json") for request in snapshot.requests])
        raise typer.Exit(code=1 if snapshot.requests else 0)

    if not snapshot.requests:
        console.print("[green]Nothing pending: every model is resolved.[/green]")
        raise typer.Exit(code=0)

    console.print(
        f"[yellow]{len(snapshot.requests)} model(s) need a human or an agent.[/yellow] "
        f"Hand the agent [bold]{agent.REQUEST_DIR}/{agent.WORKLIST_NAME}[/bold] — "
        f"it contains the mission, the exact output format and the work list."
    )
    for request in snapshot.requests:
        console.print(f"  · {request.model_name} — missing {', '.join(request.missing)}")
    raise typer.Exit(code=1)


@app.command()
def verify(
    force: bool = typer.Option(False, "--force", help="Ignore the cache TTL and refetch Artificial Analysis."),
) -> None:
    """Cross-check curated overrides against Artificial Analysis.

    Overrides outrank every automatic source, so a wrong one silently hides a
    correct value. Exits non-zero if any override disagrees with AA.
    """
    base_dir = _base_dir()
    catalog = pipeline.load_catalog(base_dir)
    if catalog is None:
        err_console.print("[red]No cached catalog. Run `which-model refresh` first.[/red]")
        raise typer.Exit(code=2)

    entries, available, warnings = pipeline.load_aa_entries(base_dir, force=force)
    for warning in warnings:
        err_console.print(f"[yellow]warning:[/yellow] {warning}")
    if not available:
        err_console.print(
            "[red]Artificial Analysis unavailable (set AA_API_KEY). Cannot verify.[/red]"
        )
        raise typer.Exit(code=2)

    problems = benchmarks.check_overrides(
        catalog,
        entries,
        overrides=benchmarks.load_overrides(base_dir / benchmarks.OVERRIDES_DIR),
        aliases=benchmarks.load_aliases(base_dir / benchmarks.ALIASES_PATH),
    )
    if not problems:
        console.print("[green]No contradiction: every override agrees with Artificial Analysis.[/green]")
        raise typer.Exit(code=0)

    console.print(f"[red]{len(problems)} contradiction(s) between overrides and Artificial Analysis.[/red]")
    for problem in problems:
        if problem.reason == "not_found":
            detail = ", ".join(f"{key} {value:g}" for key, value in sorted(problem.aa_scores.items()))
            console.print(f"  · {problem.model_name}: override says not_found, AA has {detail}")
        else:
            console.print(
                f"  · {problem.model_name}: {problem.key} override={problem.override:g} AA={problem.aa:g}"
            )
    raise typer.Exit(code=1)


def main() -> None:  # pragma: no cover - console entry point
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
