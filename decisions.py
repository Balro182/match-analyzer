from __future__ import annotations

from typing import Any, Iterable

from evaluation import enrich_recommendation

RECOMMENDED_STATUSES = {"FORMAL", "BORDERLINE"}


def prepare_recommendation(
    recommendation: dict[str, Any],
    minimum_score: float = 100.0,
    minimum_quality: float = 100.0,
    require_passed: bool = True,
) -> dict[str, Any]:
    """Adds one canonical, snapshot-safe decision to a recommendation."""
    enriched = enrich_recommendation(recommendation, minimum_score, minimum_quality)
    passed = bool(enriched.get("passed"))
    eligible = (
        float(enriched.get("score") or 0.0) >= minimum_score
        and float(enriched.get("data_quality") or 0.0) >= minimum_quality
        and (passed or not require_passed)
    )
    recommended = eligible and str(enriched.get("status")) in RECOMMENDED_STATUSES
    enriched["eligible"] = eligible
    enriched["recommended"] = recommended
    enriched["decision_policy"] = {
        "minimum_score": float(minimum_score),
        "minimum_quality": float(minimum_quality),
        "require_passed": bool(require_passed),
    }
    return enriched


def prepare_recommendations(
    recommendations: Iterable[dict[str, Any]],
    minimum_score: float = 100.0,
    minimum_quality: float = 100.0,
    require_passed: bool = True,
) -> list[dict[str, Any]]:
    return [
        prepare_recommendation(item, minimum_score, minimum_quality, require_passed)
        for item in recommendations
    ]


def is_recommended(
    recommendation: dict[str, Any],
    minimum_score: float = 100.0,
    minimum_quality: float = 100.0,
    require_passed: bool = True,
) -> bool:
    """Uses the frozen snapshot decision when available; otherwise migrates legacy data."""
    if "recommended" in recommendation:
        return bool(recommendation.get("recommended"))
    return bool(
        prepare_recommendation(
            recommendation,
            minimum_score,
            minimum_quality,
            require_passed,
        ).get("recommended")
    )
