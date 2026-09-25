.PHONY: sync refresh report verbosity perf provenance check test clean

sync:
	uv sync

refresh:
	uv run which-model refresh

report:
	uv run which-model report --view budget

verbosity:
	uv run which-model report --view verbosity

perf:
	uv run which-model report --view perf

provenance:
	uv run which-model report --view provenance

check:
	uv run which-model check

test:
	uv run pytest

clean:
	rm -rf data/cache data/snapshot data/catalog.json data/benchmarks.json data/meta.json data/agent-requests
