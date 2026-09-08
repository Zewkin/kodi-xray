from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MatchResult:
    person: dict[str, Any] | None
    best: float
    second: float
    margin: float
    accepted: bool


def _identities(gallery: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for item in gallery:
        group = grouped.setdefault(item["person_id"], {**item, "vectors": []})
        group["vectors"].append(item["vector"])
        group["roles"] = list(dict.fromkeys(group["roles"] + item.get("roles", [])))
    return list(grouped.values())


def match_embedding(
    embedding: np.ndarray,
    gallery: list[dict[str, Any]],
    threshold: float,
    required_margin: float,
) -> MatchResult:
    candidates = _identities(gallery)
    scored = sorted(
        (
            (
                max(float(np.dot(embedding, vector)) for vector in item["vectors"]),
                item,
            )
            for item in candidates
        ),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not scored:
        return MatchResult(None, -1.0, -1.0, 0.0, False)
    best, person = scored[0]
    second = scored[1][0] if len(scored) > 1 else -1.0
    margin = best - second
    accepted = best >= threshold and margin >= required_margin
    return MatchResult(person if accepted else None, best, second, margin, accepted)
