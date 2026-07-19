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


def _thresholds(condition: dict[str, Any]) -> tuple[float, float]:
    legacy = max(float(condition.get("threshold", 1)), 0.0001)
    return (
        max(float(condition.get("threshold_home", legacy)), 0.0001),
        max(float(condition.get("threshold_away", legacy)), 0.0001),
    )


def _evaluate_1x2(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation | None:
    rule_id = str(rule.get("id") or "")
    if rule_id not in {"home_win", "draw", "away_win"}:
        return None

    wins = _find_metric(stats, "Win")
    draws = _find_metric(stats, "Draw")
    losses = _find_metric(stats, "Lose")
    condition = (rule.get("conditions") or [{}])[0]
    threshold_home, threshold_away = _thresholds(condition)
    threshold = (threshold_home + threshold_away) / 2
    op_text = condition.get("operator", ">=")
    op = OPS[op_text]

    if rule_id == "draw":
        if draws is None:
            return Recommendation(rule_id, rule["label"], 0.0, False, ["Brak danych o remisach potrzebnych do obliczenia rynku 1X2."])
        left = float(draws["home"])
        right = float(draws["away"])
        formula = "remisy A + remisy B"
    elif rule_id == "home_win":
        if wins is None or losses is None:
            return Recommendation(rule_id, rule["label"], 0.0, False, ["Brak danych o zwycięstwach i porażkach potrzebnych do obliczenia rynku 1X2."])
        left = float(wins["home"])
        right = float(losses["away"])
        formula = "wygrane A + porażki B"
    else:
        if wins is None or losses is None:
            return Recommendation(rule_id, rule["label"], 0.0, False, ["Brak danych o zwycięstwach i porażkach potrzebnych do obliczenia rynku 1X2."])
        left = float(wins["away"])
        right = float(losses["home"])
        formula = "wygrane B + porażki A"

    value = (left + right) / 2
    passed = op(value, threshold)
    reason = (
        f"Stała formuła 1X2 — {formula}: ({left:.2f} + {right:.2f}) / 2 = {value:.2f} "
        f"{op_text} próg {threshold:g} — {'warunek spełniony' if passed else 'warunek niespełniony'}"
    )
    return Recommendation(rule_id, rule["label"], 100.0 if passed else 0.0, passed, [reason])


def evaluate_rule(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation:
    fixed_1x2 = _evaluate_1x2(stats, rule)
    if fixed_1x2 is not None:
        return fixed_1x2

    conditions = rule.get("conditions", [])
    reasons: list[str] = []
    condition_scores: list[float] = []
    condition_passed: list[bool] = []
    mode = str(rule.get("mode") or ("mean" if rule.get("combine") else "both"))

    for condition in conditions:
        metric_name = condition["metric"]
        translated_name = metric_label(metric_name)
        metric = _find_metric(stats, metric_name)
        if metric is None:
            reasons.append(f"Brak danych dla statystyki: {translated_name}")
            condition_scores.append(0.0)
            condition_passed.append(False)
            continue

        home_value = float(metric["home"])
        away_value = float(metric["away"])
        threshold_home, threshold_away = _thresholds(condition)
        op_text = condition.get("operator", ">=")
        op = OPS[op_text]
        home_passed = op(home_value, threshold_home)
        away_passed = op(away_value, threshold_away)

        if mode == "mean":
            value = (home_value + away_value) / 2
            threshold = (threshold_home + threshold_away) / 2
            passed = op(value, threshold)
            score = 100.0 if passed else 0.0
            reasons.append(
                f"Średnia A+B — {translated_name}: ({home_value:.2f} + {away_value:.2f}) / 2 = {value:.2f} "
                f"{op_text} próg {threshold:g} — {'warunek spełniony' if passed else 'warunek niespełniony'}"
            )
        elif mode == "any":
            passed = home_passed or away_passed
            score = 100.0 if passed else 0.0
            reasons.append(
                f"Wystarczy jedna drużyna — A: {home_value:.2f} {op_text} {threshold_home:g} "
                f"({'TAK' if home_passed else 'NIE'}), B: {away_value:.2f} {op_text} {threshold_away:g} "
                f"({'TAK' if away_passed else 'NIE'})"
            )
        else:
            passed = home_passed and away_passed
            score = 50.0 * (int(home_passed) + int(away_passed))
            reasons.append(
                f"Obie drużyny — A: {home_value:.2f} {op_text} {threshold_home:g} "
                f"({'TAK' if home_passed else 'NIE'}), B: {away_value:.2f} {op_text} {threshold_away:g} "
                f"({'TAK' if away_passed else 'NIE'})"
            )

        condition_scores.append(score)
        condition_passed.append(passed)

    score = sum(condition_scores) / len(condition_scores) if condition_scores else 0.0
    passed = bool(condition_passed) and all(condition_passed)
    return Recommendation(rule["id"], rule["label"], score, passed, reasons)


def analyze_match(match: dict[str, Any], config: dict[str, Any]) -> list[Recommendation]:
    rules = config.get("recommendations", {}).get("rules", [])
    return [evaluate_rule(match.get("stats", {}), rule) for rule in rules if rule.get("enabled", True)]
