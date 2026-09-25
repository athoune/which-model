"""The agent hand-off contract.

Refreshing never calls an LLM. When something cannot be resolved
deterministically, the pipeline writes a structured request next to the
cache and ``check`` exits non-zero. A human or an agent then answers by
writing ``data/overrides/<slug>.json``, which outranks every automatic
source. The request is a *file contract*, not a prompt.
"""

from __future__ import annotations

import json
from pathlib import Path

from .schemas import AgentRequest, BenchmarkRecord, Catalog

REQUEST_DIR = Path("data/agent-requests")

BENCHMARK_KEYS = ("coding", "agentic", "intelligence")

_HINTS = {
    "coding": "Artificial Analysis coding index, or SWE-bench Verified resolved %",
    "agentic": "Artificial Analysis agentic index, or Terminal-Bench score",
    "intelligence": "Artificial Analysis intelligence index",
}


def build_requests(
    catalog: Catalog,
    benchmarks: dict[str, BenchmarkRecord],
) -> list[AgentRequest]:
    requests: list[AgentRequest] = []

    for record in catalog.models:
        if not record.rows:
            requests.append(
                AgentRequest(
                    model_name=record.name,
                    model_id=record.model_id,
                    kind="pricing",
                    missing=["input_usd", "output_usd", "cache_read_usd", "monthly_limit"],
                    hints=["Add the row to the Go pricing table in the docs source"],
                )
            )
            continue

        if record.name not in benchmarks:
            requests.append(
                AgentRequest(
                    model_name=record.name,
                    model_id=record.model_id,
                    kind="benchmark",
                    missing=list(BENCHMARK_KEYS),
                    hints=[_HINTS[key] for key in BENCHMARK_KEYS],
                )
            )

    return requests


def render_request(request: AgentRequest) -> str:
    lines = [
        f"# Benchmark data needed: {request.model_name}",
        "",
        f"- kind: `{request.kind}`",
        f"- model name: `{request.model_name}`",
        f"- model id: `{request.model_id or 'unknown'}`",
        f"- missing: {', '.join(f'`{m}`' for m in request.missing)}",
        "",
        "## Where to look",
        "",
    ]
    lines += [f"- {hint}" for hint in request.hints]
    lines += [
        "",
        "## How to answer",
        "",
        f"Write `data/overrides/{_slug(request.model_name)}.json`:",
        "",
        "```json",
        json.dumps(
            {
                "model_name": request.model_name,
                "scores": {key: 0.0 for key in request.missing},
                "source": "<url or citation>",
                "as_of": "<YYYY-MM-DD>",
            },
            indent=2,
        ),
        "```",
        "",
        "Only fill a value you can cite. Leave a key out rather than guessing:",
        "an absent score is honest, an invented one is worse than useless.",
        "",
    ]
    return "\n".join(lines)


def write_requests(requests: list[AgentRequest], directory: Path = REQUEST_DIR) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    expected = {directory / f"{_slug(request.model_name)}.md" for request in requests}

    # Drop requests that no longer apply so the directory reflects reality.
    for path in directory.glob("*.md"):
        if path not in expected:
            path.unlink()

    written: list[Path] = []
    for request in requests:
        path = directory / f"{_slug(request.model_name)}.md"
        path.write_text(render_request(request))
        written.append(path)
    return written


def _slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-")
