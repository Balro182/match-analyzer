from __future__ import annotations

import operator
from dataclasses import asdict, dataclass
from typing import Any

OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq}

METRIC_LABELS = {
    "Goals scored per game": "Średnia bramek zdobytych",
    "Goals conceded per game": "Średnia bramek straconych",
    "Clean sheets": "Czyste konto",
    "Team scored": "Drużyna strzeliła gola",
    "Team scored twice": "Drużyna strzeliła minimum dwa razy",
    "Scored in both halves": "Drużyna strzeliła w obu połowach",
    "Goal in both halves": "Gol w obu połowach",
    "Win": "Zwycięstwa",
    "Draw": "Remisy",
    "Lose": "Porażki",
    "Win and Over 1.5 goals": "Zwycięstwo i powyżej 1,5 gola",
    "Lose and Over 1.5 goals": "Porażka i powyżej 1,5 gola",
    "Team win first half": "Drużyna wygrywa pierwszą połowę",
    "Team draw at half time": "Remis w pierwszej połowie",
    "Team lost first half": "Drużyna przegrywa pierwszą połowę",
    "Both Teams to Score": "Obie drużyny strzelą",
    "BTTS in first-half": "Obie drużyny strzelą w pierwszej połowie",
    "BBTS in second-half": "Obie drużyny strzelą w drugiej połowie",
    "BBTS and Over 1.5": "Obie drużyny strzelą i powyżej 1,5 gola",
    "BBTS and Over 2.5": "Obie drużyny strzelą i powyżej 2,5 gola",
    "Win and BTTS": "Zwycięstwo i obie drużyny strzelą",
    "Draw and BTTS": "Remis i obie drużyny strzelą",
    "Lose and BTTS": "Porażka i obie drużyny strzelą",
    "Match total goals 0": "Suma goli: 0",
    "Match total goals 1": "Suma goli: 1",
    "Match total goals 2": "Suma goli: 2",
    "Match total goals 3": "Suma goli: 3",
    "Match total goals 4": "Suma goli: 4",
    "Match total goals 0 or 1": "Suma goli: 0–1",
    "Match total goals 2 or 3": "Suma goli: 2–3",
    "Match total goals 4+": "Suma goli: 4+",
    "Over 1.5 goals": "Powyżej 1,5 gola",
    "Over 2.5 goals": "Powyżej 2,5 gola",
    "Over 3.5 goals": "Powyżej 3,5 gola",
    "Under 1.5 goals": "Poniżej 1,5 gola",
    "Under 2.5 goals": "Poniżej 2,5 gola",
    "Under 3.5 goals": "Poniżej 3,5 gola",
    "Over 0.5 goals at half-time": "Powyżej 0,5 gola w pierwszej połowie",
    "Over 1.5 goals at half-time": "Powyżej 1,5 gola w pierwszej połowie",
    "Over 2.5 goals at half-time": "Powyżej 2,5 gola w pierwszej połowie",
    "Win HT - Win FT": "Wygrana do przerwy – wygrana na koniec",
    "Win HT - Draw FT": "Wygrana do przerwy – remis na koniec",
    "Win HT - Lose FT": "Wygrana do przerwy – porażka na koniec",
    "Draw HT - Win FT": "Remis do przerwy – wygrana na koniec",
    "Draw HT - Draw FT": "Remis do przerwy – remis na koniec",
    "Draw HT - Lose FT": "Remis do przerwy – porażka na koniec",
    "Lose HT - Win FT": "Porażka do przerwy – wygrana na koniec",
    "Lose HT - Draw FT": "Porażka do przerwy – remis na koniec",
    "Lose HT - Lose FT": "Porażka do przerwy – porażka na koniec",
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


def condition_scope(condition: dict[str, Any]) -> str:
    side = condition.get("side")
    if side == "home":
        return "Gospodarze (A)"
    if side == "away":
        return "Goście (B)"
    aggregation = condition.get("aggregation", "mean")
    return {
        "mean": "Średnia obu drużyn",
        "sum": "Suma wartości obu drużyn",
        "min": "Niższa wartość z obu drużyn",
        "max": "Wyższa wartość z obu drużyn",
    }.get(aggregation, "Średnia obu drużyn")


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
        scope = condition_scope(condition)
        metric = _find_metric(stats, metric_name)
        if metric is None:
            reasons.append(f"{scope} — brak danych dla statystyki: {translated_name}")
            continue
        value = _condition_value(metric, condition)
        op_text = condition.get("operator", ">=")
        threshold = float(condition["threshold"])
        passed = OPS[op_text](value, threshold)
        passed_count += int(passed)
        reasons.append(
            f"{scope} — {translated_name}: {value:.2f} {op_text} {threshold:g} — "
            f"{'warunek spełniony' if passed else 'warunek niespełniony'}"
        )
    score = 100.0 * passed_count / len(conditions) if conditions else 0.0
    return Recommendation(rule["id"], rule["label"], score, bool(conditions) and passed_count == len(conditions), reasons)


def analyze_match(match: dict[str, Any], config: dict[str, Any]) -> list[Recommendation]:
    rules = config.get("recommendations", {}).get("rules", [])
    return [evaluate_rule(match.get("stats", {}), rule) for rule in rules if rule.get("enabled", True)]