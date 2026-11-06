.PHONY: sync refresh report verbosity perf provenance check test fixture clean

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

# Re-pin the test fixture from the working copy after a refresh: CI and fresh
# clones have no data/ of their own, so they read tests/fixtures/data/ instead.
fixture: data/catalog.json
	cp data/catalog.json data/benchmarks.json tests/fixtures/data/

data/catalog.json:
	@echo "No catalog yet: run 'make refresh' first." >&2
	@exit 1

clean:
	rm -rf data/cache data/snapshot data/catalog.json data/benchmarks.json data/meta.json data/agent-requests
