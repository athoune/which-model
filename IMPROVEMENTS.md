# Improvement leads for which-model

This file tracks potential enhancements, robustness fixes and tooling upgrades.
Items marked `[DONE]` have already been addressed.

## User-visible correctness

- [ ] **Align the budget view with its legend.** `report.py` defines an
  `agentic` entry in `BUDGET_LEGEND` but `_budget_table` only renders a `coding`
  column. Either add an `agentic` column or remove the legend entry.

- [ ] **Avoid double JSON serialization in `check --json`.** `cli.py` calls
  `console.print_json(json.dumps(...))`. Pass the object directly via
  `print_json(data=...)` instead.

- [ ] **Use a typed kind for `AgentRequest`.** `AgentRequest.kind` is currently
  `str`. Replace it with a `Literal["benchmark", "pricing", "identity"]` or a
  `StrEnum` to catch typos statically.

- [ ] **Preserve `as_of` from override files.** `benchmarks.resolve()` overwrites
  `as_of` with `datetime.now(UTC).date()` even when the override JSON contains
  its own date. Keep the override date when present.

- [ ] **Surface `models.dev` cost disagreements.** `models_dev.py` parses
  `cost_input`, `cost_output` and `cost_cache_read`, but `catalog.py` never
  compares them with the docs prices. Report mismatches as model issues.

- [ ] **Guard against `baseline == 0`.** `report.py` uses `if baseline:` to decide
  whether to compute the verbosity index. A median of `0` would silently skip it;
  use `if baseline is not None:`.

## Robustness and performance

- [DONE] **Reject `--offline --force` in `report`.** (Fixed: the combination is
  now reported as an error.)

- [DONE] **Narrow exception handling in the Artificial Analysis fetch.** (Fixed:
  catch `httpx.HTTPError` and `json.JSONDecodeError` instead of `Exception`.)

- [DONE] **Treat corrupted cache metadata as a cache miss.** (Fixed:
  `_read_cache` now returns `None` on invalid JSON, missing keys or malformed
  dates.)

- [ ] **Add HTTP retries.** `fetch.py` makes a single `httpx.get` call per URL.
  A transient failure currently falls back to stale cache or crashes. Add retries
  via an `httpx` transport or `tenacity`.

- [ ] **Fetch sources in parallel.** The docs, `models.dev` and `zen` endpoints
  are fetched sequentially (`pipeline.py`). Use `httpx.AsyncClient` to run them
  concurrently.

- [ ] **Support conditional HTTP requests.** The cache only uses TTL. Add
  `If-None-Match` / `If-Modified-Since` to avoid re-downloading unchanged
  upstream files.

- [ ] **Give friendlier network-error messages.** A connection failure currently
  surfaces as a Python traceback. Wrap fetch errors in a short actionable
  message.

## Tooling and maintainability

- [ ] **Add static type checking.** Install and configure `mypy` (or `pyright`)
  in the dev dependency group and enforce it in CI.

- [ ] **Add continuous integration.** Create a GitHub Actions workflow that runs
  `uv sync`, `ruff check .`, `pytest` and the type checker on every push and PR.

- [ ] **Measure test coverage.** Add `pytest-cov` and a `make coverage` target.
  Aim for a high bar on the math and reconciliation modules.

- [ ] **Remove dead code.** `fetch.py` defines a public `sleep()` helper that is
  never used. Delete it or expose it intentionally.

- [ ] **Configure a pre-commit hook.** Optional but helpful to keep `ruff` and
  `mypy` green before commits.

## Features and UX

- [ ] **Support machine-readable report outputs.** Add `--format json` and/or
  `--format csv` to `which-model report` for scripting and spreadsheet import.

- [ ] **Add snapshot diff.** `data/snapshot/YYYY-MM-DD/` already exists. Add a
  `which-model diff <date>` command to compare prices/scores between two refresh
  dates.

- [ ] **Make the data directory configurable.** The CLI always uses the current
  working directory (`Path.cwd()`). Support `--data-dir` or a
  `WHICH_MODEL_DATA_DIR` environment variable.

- [ ] **Account for cache-write tokens.** `TaskProfile` only carries input,
  cached and output tokens. If the docs ever publish cache-write token counts,
  include `cache_write_usd` in `cost_per_request`.

- [ ] **Expose provenance disagreements more prominently.** Models served but
  undocumented, or in docs but not served, are reported in the provenance view.
  Consider a non-zero exit code for `check` when structural mismatches exist.

- [ ] **Trend dashboards.** Plot cost-per-task or coding-score evolution over
  time using the daily snapshots.

## Refactoring ideas

- [ ] **Extract HTTP client configuration.** Move user-agent, timeouts and retry
  policy into a single place instead of hard-coding them in `Fetcher`.

- [ ] **Unify slug utilities.** `catalog.slugify()` and `agent.slug()` behave
  slightly differently. Consolidate on one slug function to avoid surprises in
  override filenames.

- [ ] **Model the pricing-window logic more explicitly.** `LIMIT_WINDOWS` is a
  module-level dict. A small dataclass or enum would make the 5h/week/month
  semantics clearer.

## How to use this list

Pick items from the top of each section first — they are the highest-value,
lowest-risk wins. Before starting a larger feature (parallel fetch, diff command,
trend dashboard), open a short design note so the trade-offs stay visible.
