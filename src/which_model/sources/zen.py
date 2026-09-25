"""The live Go models endpoint.

``/zen/go/v1/models`` tells us what the service actually serves right now.
It is the only source that is guaranteed to be current, but it exposes no
price, no allowance and no capability data. It is therefore used to *check*
the documented offer, and disagreements are surfaced rather than hidden.
"""

from __future__ import annotations

import json

URL = "https://opencode.ai/zen/go/v1/models"


def parse(data: dict) -> list[str]:
    """Return the served model ids, in the order the endpoint lists them."""
    return [entry["id"] for entry in data.get("data", []) if "id" in entry]


def load(text: str) -> list[str]:
    return parse(json.loads(text))
