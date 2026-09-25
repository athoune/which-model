# Improvement leads for which-model

This file tracks potential enhancements, robustness fixes and tooling upgrades.
Items marked `[DONE]` have already been addressed.

## User-visible correctness

- [DONE] **Align the budget view with its legend.** (Fixed: the stale `agentic`
  entry was removed from `BUDGET_LEGEND`; the narrow budget table keeps only the
  `coding` column, and `agentic` stays documented in the `perf` view. A test now
  asserts every legend entry maps to a column that is actually rendered.)

- [DONE] **Avoid double JSON serialization in `check --json`.** (Fixed:
  `print_json(data=...)` receives the objects directly; the manual `json.dumps`
  call and its now-unused import are gone.)

- [DONE] **Use a typed kind for `AgentRequest`.** (Fixed: a `RequestKind`
  `StrEnum` with `benchmark` / `pricing` / `identity`; a typo now fails
  validation instead of travelling as a free string.)

- [DONE] **Preserve `as_of` from override files.** (Fixed: `load_overrides`
  returns an `Override` carrying the file's date and citation; a present date is
  kept, otherwise the run date is used.)

- [DONE] **Surface `models.dev` cost disagreements.** (Fixed: `catalog.py` flags
  a model when models.dev's price matches *no* documented tier. models.dev
  collapses tiers into one rate, so matching any single tier counts as
  agreement and tiered models are not spuriously flagged.)

- [DONE] **Guard against `baseline == 0`.** (Fixed: `if baseline is not None:`
  everywhere, and `verbosity_index` returns `None` for a non-positive baseline
  instead of dividing by zero.)

- [DONE] **Count `not_found` honestly in the provenance panel.** (Fixed: it
  claimed `benchmarks resolved: 33/33` while counting investigated-but-empty
  records as resolved; it now reports scored, searched-none and pending
  separately.)

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
