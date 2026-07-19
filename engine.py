from __future__ import annotations

import operator
from dataclasses import asdict, dataclass
from typing import Any

OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq}

METRIC_LABELS = {
    "Goals scored per game": "Gole zdobywane na mecz",
    "Goals conceded per game": "Gole tracone na mecz",
    "Clean sheets": "Mecze bez straty gola",
    "Team scored": "Drużyna strzeliła gola",
    "Team scored twice": "Drużyna strzeliła co najmniej dwa gole",
    "Scored in both halves": "Gol strzelony w obu połowach",
    "Goal in both halves": "Gol w obu połowach",
    "Win": "Zwycięstwa",
    "Draw": "Remisy",
    "Lose": "Porażki",
    "Win and Over 1.5 goals": "Zwycięstwo i powyżej 1,5 gola",
    "Lose and Over 1.5 goals": "Porażka i powyżej 1,5 gola",
    "Team win first half": "Drużyna wygrywa pierwszą połowę",
    "Team draw at half time": "Remis do przerwy",
    "Team lost first half": "Drużyna przegrywa pierwszą połowę",
    "Both Teams to Score": "Obie drużyny strzelą",
    "BTTS in first-half": "Obie drużyny strzelą w pierwszej połowie",
    "BBTS in second-half": "Obie drużyny strzelą w drugiej połowie",
    "BBTS and Over 1.5": "Obie drużyny strzelą i powyżej 1,5 gola",
    "BBTS and Over 2.5": "Obie drużyny strzelą i powyżej 2,5 gola",
    "Win and BTTS": "Zwycięstwo i obie drużyny strzelą",
    "Draw and BTTS": "Remis i obie drużyny strzelą",
    "Lose and BTTS": "Porażka i obie drużyny strzelą",
    "Over 1.5 goals": "Powyżej 1,5 gola",
    "Over 2.5 goals": "Powyżej 2,5 gola",
    "Over 3.5 goals": "Powyżej 3,5 gola",
    "Under 1.5 goals": "Poniżej 1,5 gola",
    "Under 2.5 goals": "Poniżej 2,5 gola",
    "Under 3.5 goals": "Poniżej 3,5 gola",
    "Over 0.5 goals at half-time": "Powyżej 0,5 gola do przerwy",
    "Over 1.5 goals at half-time": "Powyżej 1,5 gola do przerwy",
    "Over 2.5 goals at half-time": "Powyżej 2,5 gola do przerwy",
    "Win HT - Win FT": "Wygrana do przerwy i wygrana na koniec",
    "Win HT - Draw FT": "Wygrana do przerwy i remis na koniec",
    "Win HT - Lose FT": "Wygrana do przerwy i porażka na koniec",
    "Draw HT - Win FT": "Remis do przerwy i wygrana na koniec",
    "Draw HT - Draw FT": "Remis do przerwy i remis na koniec",
    "Draw HT - Lose FT": "Remis do przerwy i porażka na koniec",
    "Lose HT - Win FT": "Porażka do przerwy i wygrana na koniec",
    "Lose HT - Draw FT": "Porażka do przerwy i remis na koniec",
    "Lose HT - Lose FT": "Porażka do przerwy i porażka na koniec",
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
            reasons.append(f"Brak danych dla statystyki: {translated_name}")
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
