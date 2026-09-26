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

```

╭───────────────────────────────────────────────── which-model · OpenCode Go ──────────────────────────────────────────────────╮
│ 33 models  ·  29 with benchmark scores  ·  4 searched, no citable source  ·  6 awaiting an agent  ·  verbosity baseline 200  │
│ output tokens                                                                                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                   Budget: what one task costs inside the Go allowance                    
Model                       Allow          $/M  Verb  ¢/task      5h      /mo  coding  src
★ Muse Spark 1.3 Contribu…     60      0.1/0.2   150   0.03¢  45,317  226,586    75.8  aa 
  Muse Spark 1.2 Contribu…     60      0.1/0.2   150   0.03¢  45,317  226,586    72.2  aa 
  MiMo-V2.6-Flash              60    0.14/0.28   148   0.04¢  30,075  150,376       -  n/a
  MiMo-V2.5                    60    0.14/0.28   148   0.04¢  30,075  150,376    56.8  aa 
  DeepSeek V4.1 Flash          60     0.15/0.6   155   0.05¢  26,008  130,039       -  aa 
  DeepSeek V4 Flash            30     0.15/0.6   155   0.05¢  13,004   65,020    69.1  aa 
  LongCat-2.0                  60      0.3/1.2   100   0.10¢  11,435   57,176    45.3  aa 
  DeepSeek V4 Flash Visio…     15     0.15/0.6   155   0.05¢   6,502   32,510    65.0  aa 
  GLM-5.3-Flash                60     0.15/0.5   100   0.19¢   6,316   31,579    71.5  aa 
  Qwen3.8 Flash                30    0.15/0.47   100   0.11¢   5,396   26,978       -  n/a
  Qwen3.7 Plus                 60      0.4/1.6    95   0.28¢   4,310   21,552    55.9  aa 
  Hy3                          60    0.14/0.58   148   0.28¢   4,301   21,507    58.8  aa 
  GPT 6 Luna                   15      0.1/0.5   110   0.07¢   4,225   21,127       -  aa 
  MiniMax M2.7                 60      0.3/1.2    62   0.35¢   3,390   16,949    52.6  aa 
  Qwen3.6 Plus                 60        0.5/3    95   0.37¢   3,270   16,349    54.5  aa 
  MiMo-V2.6-Pro                15   0.435/0.87   152   0.09¢   3,258   16,291       -  aa 
  MiMo-V2.5-Pro                15   0.435/0.87   152   0.09¢   3,258   16,291    60.2  aa 
  MiniMax M3                   60      0.3/1.2    95   0.37¢   3,208   16,038    58.6  aa 
  GPT 5.6 Luna                 15      0.2/1.2   110   0.15¢   2,049   10,246    71.4  aa 
  Hy4 preview                  30  0.834/2.501   148   0.44¢   1,353    6,767       -  n/a
  Kimi K2.6                    60       0.95/4   100   1.04¢   1,151    5,755    61.8  aa 
  DeepSeek V4 Pro              15    0.66/1.98   145   0.29¢   1,044    5,221    68.8  aa 
  Kimi K2.7 Code               60       0.95/4   100   1.21¢     994    4,968    60.8  aa 
  GLM-5.2                      60      1.4/4.4    75   1.52¢     792    3,958    68.8  aa 
  GLM-5.1                      60      1.4/4.4    75   1.52¢     792    3,958    55.8  aa 
  GLM-5.3                      15      1.4/4.4    75   1.52¢     198      989    74.8  aa 
  Grok 4.7                     15          2/6    60   1.77¢     169      845       -  aa 
★ Grok 4.6                     15          2/6    60   1.77¢     169      845    76.8  aa 
  Qwen3.7 Max                  30      2.5/7.5   100   3.55¢     169      844    66.0  aa 
  Qwen3.8 Max                  15          2/6   100   1.85¢     162      809    76.2  aa 
  Kimi K3                      15         3/15   150   3.06¢      98      490    76.2  aa 
  MiniMax M2.5                 60      0.3/1.2     -       -       -        -       -  aa 
  Space Bunny Free          unlim          0/0     -       -       ∞        ∞       -  n/a
╭─────────────────────────────────────────────────────────── Legend ───────────────────────────────────────────────────────────╮
│ ★  Pareto frontier: no other model is both cheaper AND better scored                                                         │
│                                                                                                                              │
│ Model   model name; a ★ prefix marks the Pareto frontier (see above)                                                         │
│ Allow   monthly included usage for that model, in dollars: $15, $30, $60 or unlimited                                        │
│ $/M     token price per million tokens, input / output                                                                       │
│ Verb    verbosity index: 100 = median output length across models                                                            │
│ ¢/task  cost of ONE task, counted in allowance cents — not money you pay                                                     │
│ 5h      tasks that fit in the 5-hour window (20% of the allowance)                                                           │
│ /mo     tasks that fit in the monthly window (100% of the allowance)                                                         │
│ coding  benchmark score, 0-100. '-' = not resolved yet                                                                       │
│ src     where the score comes from: see the source legend below                                                              │
│                                                                                                                              │
│ source: aa = Artificial Analysis · seed = curated seed · override = human/agent · n/a = searched, nothing citable · mixed =  │
│ several of these                                                                                                             │
│ verbosity baseline: 100 on the index = 200 output tokens per task                                                            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Views

```bash
uv run which-model report --view budget       # ¢/task, tasks per 5h and per month
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
