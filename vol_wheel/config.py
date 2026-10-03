"""Load config/rules.yaml."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "config" / "rules.yaml"


def load_rules(path: str | Path | None = None) -> dict:
    with open(path or DEFAULT_PATH) as f:
        return yaml.safe_load(f)


def universe(rules: dict) -> list[dict]:
    """Flatten the bucket table into [{symbol, bucket, role, cap}] in config order."""
    out = []
    for bucket, spec in rules["universe"].items():
        for role in ("core", "opportunistic"):
            for sym in spec.get(role) or []:
                out.append({"symbol": sym, "bucket": bucket, "role": role, "cap": spec["cap"]})
    return out
