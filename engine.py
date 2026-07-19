from __future__ import annotations

import operator
from dataclasses import asdict, dataclass
from typing import Any

OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq}
ALGORITHM_VERSION = "2.0.0"

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
    "Win HT - Win FT": "A/A",
    "Win HT - Draw FT": "A/X",
    "Win HT - Lose FT": "A/B",
    "Draw HT - Win FT": "X/A",
    "Draw HT - Draw FT": "X/X",
    "Draw HT - Lose FT": "X/B",
    "Lose HT - Win FT": "B/A",
    "Lose HT - Draw FT": "B/X",
    "Lose HT - Lose FT": "B/B",
}


@dataclass
class Recommendation:
    rule_id: str
    label: str
    score: float
    passed: bool
    reasons: list[str]
    data_quality: float = 100.0
    raw_value: float | None = None
    threshold: float | None = None
    mode: str | None = None

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


def _strength(value: float, threshold: float, op_text: str) -> float:
    """Ciągły score: 100 oznacza dokładnie próg, >100 oznacza zapas."""
    threshold = max(abs(threshold), 0.0001)
    if op_text in {">=", ">"}:
        return max(0.0, min(150.0, value / threshold * 100.0))
    if op_text in {"<=", "<"}:
        if value <= 0:
            return 150.0
        return max(0.0, min(150.0, threshold / value * 100.0))
    return 100.0 if value == threshold else 0.0


def _special_average(
    stats: dict[str, dict[str, float]],
    rule: dict[str, Any],
    left_metric: str,
    left_side: str,
    right_metric: str,
    right_side: str,
    formula: str,
) -> Recommendation:
    condition = (rule.get("conditions") or [{}])[0]
    left_data = _find_metric(stats, left_metric)
    right_data = _find_metric(stats, right_metric)
    if left_data is None or right_data is None:
        return Recommendation(rule["id"], rule["label"], 0.0, False, [f"Brak danych do formuły: {formula}."], 0.0, mode="special")
    left = float(left_data[left_side])
    right = float(right_data[right_side])
    value = (left + right) / 2
    th_a, th_b = _thresholds(condition)
    threshold = (th_a + th_b) / 2
    op_text = condition.get("operator", ">=")
    passed = OPS[op_text](value, threshold)
    score = _strength(value, threshold, op_text)
    reason = (
        f"Stała formuła — {formula}: ({left:.2f} + {right:.2f}) / 2 = {value:.2f}; "
        f"próg {threshold:g}; zapas {value - threshold:+.2f}; score {score:.1f}"
    )
    return Recommendation(rule["id"], rule["label"], score, passed, [reason], 100.0, value, threshold, "special")


def _evaluate_special(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation | None:
    rule_id = str(rule.get("id") or "")
    formulas = {
        "home_win": ("Win", "home", "Lose", "away", "wygrane A + porażki B"),
        "draw": ("Draw", "home", "Draw", "away", "remisy A + remisy B"),
        "away_win": ("Win", "away", "Lose", "home", "wygrane B + porażki A"),
        "home_win_ht": ("Team win first half", "home", "Team lost first half", "away", "wygrane A do przerwy + porażki B do przerwy"),
        "draw_ht": ("Team draw at half time", "home", "Team draw at half time", "away", "remisy obu drużyn do przerwy"),
        "away_win_ht": ("Team win first half", "away", "Team lost first half", "home", "wygrane B do przerwy + porażki A do przerwy"),
    }
    if rule_id in formulas:
        return _special_average(stats, rule, *formulas[rule_id])

    directional = {
        "win_over15": ("Win and Over 1.5 goals", "home", "A wygra i Over 1,5"),
        "lose_over15": ("Win and Over 1.5 goals", "away", "B wygra i Over 1,5"),
        "home_win_btts": ("Win and BTTS", "home", "A wygra i BTTS"),
        "away_win_btts": ("Win and BTTS", "away", "B wygra i BTTS"),
    }
    if rule_id in directional:
        metric_name, side, formula = directional[rule_id]
        condition = (rule.get("conditions") or [{}])[0]
        metric = _find_metric(stats, metric_name)
        if metric is None:
            return Recommendation(rule_id, rule["label"], 0.0, False, [f"Brak danych: {metric_name}."], 0.0, mode="special")
        value = float(metric[side])
        th_a, th_b = _thresholds(condition)
        threshold = th_a if side == "home" else th_b
        op_text = condition.get("operator", ">=")
        passed = OPS[op_text](value, threshold)
        score = _strength(value, threshold, op_text)
        return Recommendation(rule_id, rule["label"], score, passed, [f"{formula}: {value:.2f}, próg {threshold:g}, score {score:.1f}"], 100.0, value, threshold, "special")
    return None


def evaluate_rule(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation:
    special = _evaluate_special(stats, rule)
    if special is not None:
        return special

    conditions = rule.get("conditions", [])
    reasons: list[str] = []
    scores: list[float] = []
    passes: list[bool] = []
    available = 0
    mode = str(rule.get("mode") or ("mean" if rule.get("combine") else "both"))
    raw_values: list[float] = []
    thresholds: list[float] = []

    for condition in conditions:
        metric_name = condition["metric"]
        translated_name = metric_label(metric_name)
        metric = _find_metric(stats, metric_name)
        if metric is None:
            reasons.append(f"Brak danych dla statystyki: {translated_name}")
            scores.append(0.0)
            passes.append(False)
            continue
        available += 1
        home_value = float(metric["home"])
        away_value = float(metric["away"])
        threshold_home, threshold_away = _thresholds(condition)
        op_text = condition.get("operator", ">=")
        op = OPS[op_text]
        home_passed = op(home_value, threshold_home)
        away_passed = op(away_value, threshold_away)
        home_score = _strength(home_value, threshold_home, op_text)
        away_score = _strength(away_value, threshold_away, op_text)

        if mode == "mean":
            value = (home_value + away_value) / 2
            threshold = (threshold_home + threshold_away) / 2
            passed = op(value, threshold)
            score = _strength(value, threshold, op_text)
            reasons.append(f"Średnia A+B — {translated_name}: {value:.2f}, próg {threshold:g}, zapas {value-threshold:+.2f}, score {score:.1f}")
        elif mode == "any":
            passed = home_passed or away_passed
            score = max(home_score, away_score)
            value = max(home_value, away_value)
            threshold = threshold_home if home_score >= away_score else threshold_away
            reasons.append(f"Wystarczy jedna — A {home_value:.2f}/{threshold_home:g} ({home_score:.1f}), B {away_value:.2f}/{threshold_away:g} ({away_score:.1f})")
        else:
            passed = home_passed and away_passed
            score = (home_score + away_score) / 2
            value = (home_value + away_value) / 2
            threshold = (threshold_home + threshold_away) / 2
            reasons.append(f"Wymagane obie — A {home_value:.2f}/{threshold_home:g} ({home_score:.1f}), B {away_value:.2f}/{threshold_away:g} ({away_score:.1f})")

        scores.append(score)
        passes.append(passed)
        raw_values.append(value)
        thresholds.append(threshold)

    quality = 100.0 * available / len(conditions) if conditions else 0.0
    score = sum(scores) / len(scores) if scores else 0.0
    passed = bool(passes) and all(passes) and quality == 100.0
    raw_value = sum(raw_values) / len(raw_values) if raw_values else None
    threshold = sum(thresholds) / len(thresholds) if thresholds else None
    return Recommendation(rule["id"], rule["label"], round(score, 1), passed, reasons, quality, raw_value, threshold, mode)


def analyze_match(match: dict[str, Any], config: dict[str, Any]) -> list[Recommendation]:
    rules = config.get("recommendations", {}).get("rules", [])
    return [evaluate_rule(match.get("stats", {}), rule) for rule in rules if rule.get("enabled", True)]
