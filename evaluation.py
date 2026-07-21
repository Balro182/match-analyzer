from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

STATUS_FORMAL = "FORMAL"
STATUS_BORDERLINE = "BORDERLINE"
STATUS_OBSERVATIONAL = "OBSERVATIONAL"
STATUS_LOW_DATA_QUALITY = "LOW_DATA_QUALITY"
STATUS_REJECTED = "REJECTED"

OUTCOME_HIT = "HIT"
OUTCOME_FALSE_POSITIVE = "FALSE_POSITIVE"
OUTCOME_FALSE_NEGATIVE = "FALSE_NEGATIVE"
OUTCOME_TRUE_NEGATIVE = "TRUE_NEGATIVE"
OUTCOME_NO_DATA = "NO_DATA"


def recommendation_status(
    recommendation: dict[str, Any],
    minimum_score: float = 100.0,
    minimum_quality: float = 100.0,
    borderline_margin: float = 5.0,
    observational_floor: float = 90.0,
) -> str:
    """Nadaje rekomendacji jednoznaczny status prezentacyjny.

    Status nie zmienia wyniku reguły. Porządkuje tylko sposób, w jaki sygnał
    powinien być prezentowany i później oceniany.
    """
    score = float(recommendation.get("score") or 0.0)
    quality = float(recommendation.get("data_quality") or 0.0)
    passed = bool(recommendation.get("passed"))

    if quality < minimum_quality:
        return STATUS_LOW_DATA_QUALITY
    if passed and score >= minimum_score + borderline_margin:
        return STATUS_FORMAL
    if passed and score >= minimum_score:
        return STATUS_BORDERLINE
    if score >= observational_floor:
        return STATUS_OBSERVATIONAL
    return STATUS_REJECTED


def score_bucket(score: float | int | None) -> str:
    value = float(score or 0.0)
    if value < 100:
        return "<100"
    if value < 105:
        return "100–104"
    if value < 110:
        return "105–109"
    if value < 120:
        return "110–119"
    if value < 130:
        return "120–129"
    return "130+"


def quality_bucket(quality: float | int | None) -> str:
    value = float(quality or 0.0)
    if value < 50:
        return "0–49"
    if value < 80:
        return "50–79"
    if value < 100:
        return "80–99"
    return "100"


def classify_outcome(predicted: bool, actual: bool | None) -> str:
    if actual is None:
        return OUTCOME_NO_DATA
    if predicted and actual:
        return OUTCOME_HIT
    if predicted and not actual:
        return OUTCOME_FALSE_POSITIVE
    if not predicted and actual:
        return OUTCOME_FALSE_NEGATIVE
    return OUTCOME_TRUE_NEGATIVE


def enrich_recommendation(
    recommendation: dict[str, Any],
    minimum_score: float = 100.0,
    minimum_quality: float = 100.0,
) -> dict[str, Any]:
    result = dict(recommendation)
    result["status"] = recommendation_status(result, minimum_score, minimum_quality)
    result["score_bucket"] = score_bucket(result.get("score"))
    result["quality_bucket"] = quality_bucket(result.get("data_quality"))
    return result


def _group_summary(records: Iterable[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[str(record.get(key) or "brak")].append(record)

    rows: list[dict[str, Any]] = []
    for name, items in groups.items():
        active = [item for item in items if item.get("actual") is not None]
        predictions = [item for item in active if bool(item.get("predicted"))]
        hits = sum(item.get("outcome_class") == OUTCOME_HIT for item in predictions)
        false_positives = sum(item.get("outcome_class") == OUTCOME_FALSE_POSITIVE for item in predictions)
        false_negatives = sum(item.get("outcome_class") == OUTCOME_FALSE_NEGATIVE for item in active)
        scores = [float(item.get("score") or 0.0) for item in predictions]
        qualities = [float(item.get("data_quality") or 0.0) for item in predictions]
        count = len(predictions)
        rows.append(
            {
                key: name,
                "recommendations": count,
                "hits": hits,
                "misses": false_positives,
                "false_negatives": false_negatives,
                "hit_rate": round(hits / count * 100, 1) if count else None,
                "average_score": round(sum(scores) / len(scores), 1) if scores else None,
                "average_quality": round(sum(qualities) / len(qualities), 1) if qualities else None,
            }
        )
    return sorted(rows, key=lambda row: (-int(row["recommendations"]), str(row[key])))


def build_evaluation_report(records: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    normalized = [dict(record) for record in records]
    return {
        "by_market": _group_summary(normalized, "label"),
        "by_score_bucket": _group_summary(normalized, "score_bucket"),
        "by_quality_bucket": _group_summary(normalized, "quality_bucket"),
        "by_status": _group_summary(normalized, "status"),
        "by_algorithm_version": _group_summary(normalized, "algorithm_version"),
        "by_league": _group_summary(normalized, "league"),
    }
