"""Reconcile the three upstream sources into one normalised catalog.

No source is complete on its own:

* the docs carry prices and allowances but may lag the service;
* models.dev carries capabilities but no allowances and no benchmarks;
* the zen endpoint is authoritative for what is served but has no metadata.

Reconciliation is explicit: disagreements become ``issues`` on the record and
cross-set differences are reported, never silently resolved.
"""

from __future__ import annotations

import re

from .schemas import Catalog, DocsModel, GoDocs, ModelRecord, RequestsEstimate
from .sources.models_dev import ProviderModel

_SLUG_DOTS = re.compile(r"[^a-z0-9.]+")


def slugify(name: str) -> str:
    """Best-effort model name to model id, used only when the docs are silent."""
    return _SLUG_DOTS.sub("-", name.strip().lower()).strip("-")


def build_catalog(
    docs: GoDocs,
    dev_models: dict[str, ProviderModel],
    served: list[str],
    *,
    refs: dict[str, str] | None = None,
) -> Catalog:
    served_set = set(served)
    records: list[ModelRecord] = []
    matched_dev_ids: set[str] = set()

    for doc_model in docs.models:
        record = _from_docs(doc_model)
        dev = _find_dev(doc_model, dev_models)
        if dev is not None:
            matched_dev_ids.add(dev.id)
            record.model_id = record.model_id or dev.id
            record.in_models_dev = True
            record.dev_name = dev.name
            record.context = dev.context
            record.output_limit = dev.output_limit
            record.reasoning = dev.reasoning
            record.open_weights = dev.open_weights
            record.modalities_input = dev.modalities_input
            record.release_date = dev.release_date
            if record.model_id and dev.id != record.model_id:
                record.issues.append(f"docs id {record.model_id!r} != models.dev id {dev.id!r}")
        else:
            record.issues.append("absent from models.dev")

        if record.model_id:
            record.served = record.model_id in served_set
        if not record.served:
            record.issues.append("not served by the live endpoint")
        if record.token_profile is None and not _is_free(record):
            record.issues.append("no token profile (verbosity unknown)")

        records.append(record)

    served_undocumented = sorted(served_set - {r.model_id for r in records if r.model_id})
    modeled_undocumented = sorted(set(dev_models) - matched_dev_ids)
    docs_missing = sorted(r.name for r in records if not r.in_models_dev)

    return Catalog(
        refs=refs or {},
        models=records,
        served_undocumented=served_undocumented,
        modeled_undocumented=modeled_undocumented,
        docs_missing_from_models_dev=docs_missing,
    )


def _from_docs(model: DocsModel) -> ModelRecord:
    return ModelRecord(
        name=model.name,
        model_id=model.model_id,
        endpoint=model.endpoint,
        rows=model.rows,
        token_profile=model.token_profile,
        profile_source=model.profile_source,
        published_requests=model.requests,
        listed=model.listed,
        privacy_training=model.privacy_training,
        privacy_retention=model.privacy_retention,
        in_docs=True,
    )


def _find_dev(model: DocsModel, dev_models: dict[str, ProviderModel]) -> ProviderModel | None:
    if model.model_id and model.model_id in dev_models:
        return dev_models[model.model_id]
    slug = slugify(model.name)
    return dev_models.get(slug)


def _is_free(record: ModelRecord) -> bool:
    return bool(record.rows) and all(row.free for row in record.rows)


def empty_requests() -> RequestsEstimate:
    return RequestsEstimate()
