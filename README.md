# which-model

Terminal dashboard comparing **OpenCode Go** models on the two axes that
actually matter when you pay a flat $10/month:

- **real budget cost** — how much of a model's monthly allowance one coding
  task consumes, and how many tasks that buys, *including per-model verbosity*;
- **coding performance** — benchmark scores for agentic coding work.

Everything is fetched over HTTP and computed locally. **No LLM is called at
runtime**, so you can refresh as often as you like at zero cost.

```
uv sync
uv run which-model refresh    # fetch + normalise (network, no LLM)
uv run which-model report     # render the dashboard
```

## Views

```bash
uv run which-model report --view budget       # $/task, tasks per 5h and per month
uv run which-model report --view verbosity    # output length and its cost impact
uv run which-model report --view perf         # coding tiers, Pareto frontier
uv run which-model report --view provenance   # sources, disagreements, gaps
```

Handy flags: `--offline` (never touch the network), `--force` (ignore the
cache TTL), `--width N` (force output width).

## Why "price" needed a correction

Under OpenCode Go you do **not** pay per token. The per-token prices in the
docs only decrement a per-model **monthly allowance** ($15 / $30 / $60 /
unlimited). The metric that matters is therefore:

```
cost_per_task   = (in·price_in + cached·price_cache_read + out·price_out) / 1e6
tasks_per_month = monthly_limit / cost_per_task
tasks_5h        = 0.20 × tasks_per_month      # 5h is usually the binding window
```

This formula is verified against the docs' own *estimated requests* table:
27 of 31 published rows reproduce within 0.5 %. The four exceptions are
recorded in `KNOWN_DOC_INCONSISTENCIES` (`tests/test_docs.py`) because the
page contradicts itself — its stated token profile does not yield its own
published request count. The test asserts those deltas do not drift.

## Verbosity: measured, not guessed

Each model's per-request token counts come straight from the docs, and the
`output` count is the verbosity signal. The dashboard normalises it into an
index (100 = median output length) and shows a **sensitivity bar**: the cost
if that model were twice as chatty.

A caveat the dashboard makes visible rather than hides: under Go's token
profile, output length is often **not** the dominant cost — cached context
reads are. The `share of cost` bar in the verbosity view shows the split per
model, so "verbose" and "expensive" are never conflated.

## Data sources

| Data | Source | Notes |
| --- | --- | --- |
| Prices, allowances, tiers, verbosity | `go.mdx` in the opencode repo | only source for monthly limits and peak/off-peak |
| Capabilities, context, modalities | `models.dev/api.json` | **zero benchmark data** in the whole DB |
| What is actually served | `https://opencode.ai/zen/go/v1/models` | no prices; disagreements are reported |
| Coding scores | Artificial Analysis (optional) + curated seed | never inferred |

Raw responses are cached under `data/cache/` with a 12 h TTL. If the network
is down, the last cache is used and a warning is printed — a stale dashboard
beats no dashboard.

## Handing work to an agent

When something cannot be resolved deterministically, `refresh` writes:

- **`data/agent-requests/README.md`** — the master instruction file. It is
  self-contained: mission, exact output JSON shape, hard rules, the full work
  list with verbatim model names and target paths, and how to verify. This is
  the file to hand to an agent;
- `data/agent-requests/<slug>.md` — one file per model with its specifics
  (missing keys, where to look, target path).

`check` exits non-zero and points at the master file:

```bash
uv run which-model check          # exit 1 and list the gaps
uv run which-model check --json   # machine-readable
```

After overrides are written, `verify` cross-checks them against Artificial
Analysis, because overrides outrank AA and a wrong one hides the right value:

```bash
uv run which-model verify         # exit 1 on any override that contradicts AA
```

A human or an agent answers by writing `data/overrides/<slug>.json`:

```json
{
  "model_name": "GLM-5.3",
  "scores": { "coding": 61.2, "agentic": 48.0 },
  "source": "https://.../swebench-verified",
  "as_of": "2026-09-25"
}
```

Requests are **per score key**: a model Artificial Analysis covers only for
`intelligence` is still requested for `coding` and `agentic`.

If a real search finds nothing citable, the agent writes an empty answer
instead of a guess:

```json
{ "model_name": "GLM-5.3", "scores": {}, "status": "not_found",
  "source": "<what was checked>", "as_of": "2026-09-25" }
```

The model then shows `n/a` and is not requested again. Overrides always win.
Only citable values belong there: **an absent score is honest, an invented one
is worse than useless**. Matching is deliberately strict — an alias
(`data/aliases.json`), an exact id, or an unambiguous creator-prefixed slug.
There is no fuzzy matching, so `GLM-5.3` can never inherit `GLM-5.3-Flash`
scores. Slugs are compared with dots and dashes folded together, because AA
writes `glm-5-3-flash` where the docs write `glm-5.3-flash`; without that,
every dotted model would be missed and re-requested needlessly.

## Artificial Analysis

Set `AA_API_KEY` to pull coding/agentic scores automatically. The free tier
(100 req/day) is enough. Without a key, scores come from
`data/benchmarks.seed.json` and overrides only, and the queue reports the gap.

## Configuration files

- `data/benchmarks.seed.json` — curated fallback scores, safe to commit;
- `data/aliases.json` — map a Go model name to an Artificial Analysis slug;
- `data/overrides/` — curated answers, one file per model, safe to commit.

## Development

```bash
uv run pytest
```
