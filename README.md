# which-model

Terminal dashboard comparing **OpenCode Go** models on two axes that actually
matter when you pay a flat $10/month:

- **real budget cost** — how much of a model's monthly allowance one coding
  task consumes, and how many tasks that buys, *including per-model verbosity*;
- **coding performance** — benchmark scores for agentic coding work.

Everything is fetched over HTTP and computed locally. No LLM is called at
runtime, so the dashboard can be refreshed as often as you like at zero cost.

## Quick start

```bash
uv sync
uv run which-model refresh   # fetch + normalise + write cache (no LLM)
uv run which-model report    # render the dashboard in your terminal
```

## Why "price" needs a correction

Under OpenCode Go you do not pay per token. The per-token prices in the docs
only decrement a per-model **monthly allowance** ($15 / $30 / $60 / unlimited).
The useful metric is therefore:

```
cost_per_task   = (in*price_in + cached*price_cache_read + out*price_out) / 1e6
tasks_per_month = monthly_limit / cost_per_task
```

A model is "expensive" either because its tokens cost a lot **or** because it
is verbose. Those are different failures; the dashboard keeps them separate.

## Data sources

| Data | Source |
| --- | --- |
| Prices, monthly limits, tiers, verbosity profile | `go.mdx` in the opencode repo |
| Capabilities, context, modalities | `models.dev/api.json` |
| What is actually served | `https://opencode.ai/zen/go/v1/models` |
| Coding benchmarks | Artificial Analysis (optional key) + curated seed |

## Seeking an agent's help

When a model cannot be resolved automatically (new model, unknown price tier,
no benchmark score), `refresh` writes a structured request to
`data/agent-requests/<model>.md` and `check` exits non-zero. A human or an
agent then fills `data/overrides/<model>.json`, which always wins over the
automatic pipeline. The runtime path never invokes an LLM.
