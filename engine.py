from __future__ import annotations

import operator
from dataclasses import dataclass, asdict
from typing import Any

OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq}

METRIC_LABELS = {
    "Over 1.5 goals": "Powyżej 1,5 gola",
    "Over 2.5 goals": "Powyżej 2,5 gola",
    "Over 3.5 goals": "Powyżej 3,5 gola",
    "Under 1.5 goals": "Poniżej 1,5 gola",
    "Under 2.5 goals": "Poniżej 2,5 gola",
    "Under 3.5 goals": "Poniżej 3,5 gola",
    "Goals scored per game": "Gole zdobywane na mecz",
    "Goals conceded per game": "Gole tracone na mecz",
    "Both Teams to Score": "Obie drużyny strzelą",
    "Team scored": "Drużyna strzeliła gola",
    "Team scored twice": "Drużyna strzeliła co najmniej dwa gole",
    "Clean sheets": "Mecze bez straty gola",
    "Win": "Zwycięstwa",
    "Draw": "Remisy",
    "Lose": "Porażki",
}


@dataclass
class Recommendation:
    rule_id: str
    label: str
    score: float
    passed: bool
    reasons: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def metric_label(name: str) -> str:
    return METRIC_LABELS.get(name, name)


def _find_metric(stats: dict[str, dict[str, float]], requested: str) -> dict[str, float] | None:
    normalized = requested.casefold().strip()
    for key, value in stats.items():
        if key.casefold().strip() == normalized:
            return value
    return None


def _condition_value(metric: dict[str, float], condition: dict[str, Any]) -> float:
    side = condition.get("side")
    if side in {"home", "away"}:
        return float(metric[side])
    values = [float(metric["home"]), float(metric["away"])]
    aggregation = condition.get("aggregation", "mean")
    if aggregation == "min":
        return min(values)
    if aggregation == "max":
        return max(values)
    if aggregation == "sum":
        return sum(values)
    return sum(values) / len(values)


def evaluate_rule(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation:
    conditions = rule.get("conditions", [])
    passed_count = 0
    reasons: list[str] = []
    for condition in conditions:
        metric_name = condition["metric"]
        translated_name = metric_label(metric_name)
        metric = _find_metric(stats, metric_name)
        if metric is None:
            reasons.append(f"Brak danych dla metryki: {translated_name}")
            continue
        value = _condition_value(metric, condition)
        op_text = condition.get("operator", ">=")
        threshold = float(condition["threshold"])
        passed = OPS[op_text](value, threshold)
        passed_count += int(passed)
        reasons.append(
            f"{translated_name}: {value:.2f} {op_text} {threshold:g} — "
            f"{'warunek spełniony' if passed else 'warunek niespełniony'}"
        )
    score = 100.0 * passed_count / len(conditions) if conditions else 0.0
    return Recommendation(rule["id"], rule["label"], score, bool(conditions) and passed_count == len(conditions), reasons)


def analyze_match(match: dict[str, Any], config: dict[str, Any]) -> list[Recommendation]:
    rules = config.get("recommendations", {}).get("rules", [])
    return [evaluate_rule(match.get("stats", {}), rule) for rule in rules if rule.get("enabled", True)]
