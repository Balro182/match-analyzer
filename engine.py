from __future__ import annotations

import operator
from dataclasses import asdict, dataclass
from typing import Any

OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq}
ALGORITHM_VERSION = "2.3.0"

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


def _btts_profile(stats: dict[str, dict[str, float]], condition: dict[str, Any]) -> tuple[dict[str, bool], list[str]] | None:
    btts = _find_metric(stats, "Both Teams to Score")
    team_scored = _find_metric(stats, "Team scored")
    under25 = _find_metric(stats, "Under 2.5 goals")
    if btts is None or team_scored is None or under25 is None:
        return None

    btts_home = float(btts["home"])
    btts_away = float(btts["away"])
    btts_mean = (btts_home + btts_away) / 2
    btts_minimum = min(btts_home, btts_away)
    team_scored_home = float(team_scored["home"])
    team_scored_away = float(team_scored["away"])
    under25_mean = (float(under25["home"]) + float(under25["away"])) / 2
    threshold_home, threshold_away = _thresholds(condition)
    mean_threshold = (threshold_home + threshold_away) / 2
    minimum_btts = float(condition.get("minimum_btts", 45))
    minimum_team_scored = float(condition.get("minimum_team_scored", 70))
    maximum_under25 = float(condition.get("maximum_under25", 65))

    checks = {
        "średnia BTTS": btts_mean >= mean_threshold,
        "minimum BTTS": btts_minimum >= minimum_btts,
        "Team scored A": team_scored_home >= minimum_team_scored,
        "Team scored B": team_scored_away >= minimum_team_scored,
        "średni Under 2,5": under25_mean < maximum_under25,
    }
    values = [
        f"BTTS średnia: ({btts_home:.1f} + {btts_away:.1f}) / 2 = {btts_mean:.1f}, próg {mean_threshold:g}",
        f"BTTS słabszej strony: {btts_minimum:.1f}, minimum {minimum_btts:g}",
        f"Team scored: A {team_scored_home:.1f}, B {team_scored_away:.1f}, minimum {minimum_team_scored:g}",
        f"Średni Under 2,5: {under25_mean:.1f}, wymagane poniżej {maximum_under25:g}",
    ]
    return checks, values


def _evaluate_btts(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation:
    condition = (rule.get("conditions") or [{}])[0]
    required_names = ["Both Teams to Score", "Team scored", "Under 2.5 goals"]
    required = {name: _find_metric(stats, name) for name in required_names}
    missing = [name for name, data in required.items() if data is None]
    if missing:
        return Recommendation(
            rule["id"], rule["label"], 0.0, False,
            ["Brak danych do formuły BTTS: " + ", ".join(missing)],
            100.0 * (len(required) - len(missing)) / len(required), mode="special",
        )

    btts = required["Both Teams to Score"]
    team_scored = required["Team scored"]
    under25 = required["Under 2.5 goals"]
    assert btts is not None and team_scored is not None and under25 is not None

    btts_home = float(btts["home"])
    btts_away = float(btts["away"])
    btts_mean = (btts_home + btts_away) / 2
    btts_minimum = min(btts_home, btts_away)
    team_scored_home = float(team_scored["home"])
    team_scored_away = float(team_scored["away"])
    under25_mean = (float(under25["home"]) + float(under25["away"])) / 2
    threshold_home, threshold_away = _thresholds(condition)
    mean_threshold = (threshold_home + threshold_away) / 2
    minimum_btts = float(condition.get("minimum_btts", 45))
    minimum_team_scored = float(condition.get("minimum_team_scored", 70))
    maximum_under25 = float(condition.get("maximum_under25", 65))

    profile = _btts_profile(stats, condition)
    assert profile is not None
    checks, reasons = profile
    component_scores = [
        _strength(btts_mean, mean_threshold, ">="),
        _strength(btts_minimum, minimum_btts, ">="),
        _strength(team_scored_home, minimum_team_scored, ">="),
        _strength(team_scored_away, minimum_team_scored, ">="),
        _strength(under25_mean, maximum_under25, "<"),
    ]
    score = round(sum(component_scores) / len(component_scores), 1)
    reasons.append("Warunki: " + ", ".join(f"{name}={'TAK' if value else 'NIE'}" for name, value in checks.items()))
    return Recommendation(rule["id"], rule["label"], score, all(checks.values()), reasons, 100.0, btts_mean, mean_threshold, "special")


def _winner_base(stats: dict[str, dict[str, float]], winner_side: str) -> float | None:
    win = _find_metric(stats, "Win")
    lose = _find_metric(stats, "Lose")
    if win is None or lose is None:
        return None
    loser_side = "away" if winner_side == "home" else "home"
    return (float(win[winner_side]) + float(lose[loser_side])) / 2


def _evaluate_guarded_winner(stats: dict[str, dict[str, float]], rule: dict[str, Any], winner_side: str) -> Recommendation:
    condition = (rule.get("conditions") or [{}])[0]
    loser_side = "away" if winner_side == "home" else "home"
    required_names = ["Win", "Lose", "Goals scored per game", "Goals conceded per game", "Team scored"]
    required = {name: _find_metric(stats, name) for name in required_names}
    missing = [name for name, data in required.items() if data is None]
    if missing:
        return Recommendation(
            rule["id"], rule["label"], 0.0, False,
            ["Brak danych do zabezpieczonej reguły 1X2: " + ", ".join(missing)],
            100.0 * (len(required) - len(missing)) / len(required), mode="special",
        )

    win = required["Win"]
    lose = required["Lose"]
    scored = required["Goals scored per game"]
    conceded = required["Goals conceded per game"]
    team_scored = required["Team scored"]
    assert win is not None and lose is not None and scored is not None and conceded is not None and team_scored is not None

    own_win = float(win[winner_side])
    opponent_lose = float(lose[loser_side])
    base = (own_win + opponent_lose) / 2
    own_goals = float(scored[winner_side])
    opponent_conceded = float(conceded[loser_side])
    opponent_goals = float(scored[loser_side])
    opponent_team_scored = float(team_scored[loser_side])

    threshold_home, threshold_away = _thresholds(condition)
    base_threshold = threshold_home if winner_side == "home" else threshold_away
    minimum_own_win = float(condition.get("minimum_own_win", 50))
    minimum_opponent_lose = float(condition.get("minimum_opponent_lose", 50))
    minimum_own_goals = float(condition.get("minimum_own_goals", 1.4))
    minimum_opponent_conceded = float(condition.get("minimum_opponent_conceded", 1.3))
    volatility_opponent_goals = float(condition.get("volatility_opponent_goals", 1.5))
    volatility_team_scored = float(condition.get("volatility_team_scored", 80))

    btts_condition = {
        "threshold_home": float(condition.get("btts_mean_threshold", 55)),
        "threshold_away": float(condition.get("btts_mean_threshold", 55)),
        "minimum_btts": float(condition.get("btts_minimum", 45)),
        "minimum_team_scored": float(condition.get("btts_minimum_team_scored", 70)),
        "maximum_under25": float(condition.get("btts_maximum_under25", 65)),
    }
    btts_profile = _btts_profile(stats, btts_condition)
    btts_passed = bool(btts_profile and all(btts_profile[0].values()))
    volatility_block = btts_passed and opponent_goals >= volatility_opponent_goals and opponent_team_scored >= volatility_team_scored

    checks = {
        "baza Win/Lose": base >= base_threshold,
        "własne zwycięstwa": own_win >= minimum_own_win,
        "porażki rywala": opponent_lose >= minimum_opponent_lose,
        "gole zwycięzcy": own_goals >= minimum_own_goals,
        "gole tracone rywala": opponent_conceded >= minimum_opponent_conceded,
        "brak blokady zmienności": not volatility_block,
    }
    component_scores = [
        _strength(base, base_threshold, ">="),
        _strength(own_win, minimum_own_win, ">="),
        _strength(opponent_lose, minimum_opponent_lose, ">="),
        _strength(own_goals, minimum_own_goals, ">="),
        _strength(opponent_conceded, minimum_opponent_conceded, ">="),
        100.0 if not volatility_block else 0.0,
    ]
    score = round(sum(component_scores) / len(component_scores), 1)
    side_label = "A" if winner_side == "home" else "B"
    opponent_label = "B" if winner_side == "home" else "A"
    reasons = [
        f"Baza {side_label}: (Win {side_label} {own_win:.1f} + Lose {opponent_label} {opponent_lose:.1f}) / 2 = {base:.1f}, próg {base_threshold:g}",
        f"Ofensywa {side_label}: {own_goals:.2f} gola/mecz, minimum {minimum_own_goals:g}",
        f"Defensywa {opponent_label}: {opponent_conceded:.2f} gola straconego/mecz, minimum {minimum_opponent_conceded:g}",
        f"Ryzyko rywala: gole {opponent_goals:.2f}, Team scored {opponent_team_scored:.1f}, BTTS={'TAK' if btts_passed else 'NIE'}",
        f"Blokada zmienności: {'TAK' if volatility_block else 'NIE'}",
        "Warunki: " + ", ".join(f"{name}={'TAK' if value else 'NIE'}" for name, value in checks.items()),
    ]
    return Recommendation(rule["id"], rule["label"], score, all(checks.values()), reasons, 100.0, base, base_threshold, "special")


def _evaluate_guarded_draw(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation:
    condition = (rule.get("conditions") or [{}])[0]
    required_names = ["Draw", "Win", "Lose", "Under 3.5 goals", "Team draw at half time"]
    required = {name: _find_metric(stats, name) for name in required_names}
    missing = [name for name, data in required.items() if data is None]
    if missing:
        return Recommendation(
            rule["id"], rule["label"], 0.0, False,
            ["Brak danych do złożonej reguły remisu: " + ", ".join(missing)],
            100.0 * (len(required) - len(missing)) / len(required), mode="special",
        )

    draw = required["Draw"]
    under35 = required["Under 3.5 goals"]
    draw_ht = required["Team draw at half time"]
    assert draw is not None and under35 is not None and draw_ht is not None

    draw_mean = (float(draw["home"]) + float(draw["away"])) / 2
    home_base = _winner_base(stats, "home")
    away_base = _winner_base(stats, "away")
    assert home_base is not None and away_base is not None
    base_gap = abs(home_base - away_base)
    strongest_base = max(home_base, away_base)
    under35_mean = (float(under35["home"]) + float(under35["away"])) / 2
    draw_ht_mean = (float(draw_ht["home"]) + float(draw_ht["away"])) / 2

    primary_draw = float(condition.get("primary_draw", 35))
    primary_max_gap = float(condition.get("primary_max_gap", 25))
    low_draw = float(condition.get("low_draw", 30))
    low_under35 = float(condition.get("low_under35", 70))
    low_draw_ht = float(condition.get("low_draw_ht", 45))
    maximum_winner_base = float(condition.get("maximum_winner_base", 55))
    guarded_winner_threshold = float(condition.get("guarded_winner_threshold", 60))

    no_guarded_winner = strongest_base < guarded_winner_threshold
    primary_checks = {
        "średnia Draw": draw_mean >= primary_draw,
        "brak zabezpieczonego zwycięzcy": no_guarded_winner,
        "różnica baz": base_gap <= primary_max_gap,
    }
    low_checks = {
        "średnia Draw": draw_mean >= low_draw,
        "średni Under 3,5": under35_mean >= low_under35,
        "średni remis HT": draw_ht_mean >= low_draw_ht,
        "brak mocnej bazy zwycięstwa": strongest_base < maximum_winner_base,
    }
    primary_passed = all(primary_checks.values())
    low_passed = all(low_checks.values())
    passed = primary_passed or low_passed

    primary_score = sum([
        _strength(draw_mean, primary_draw, ">="),
        100.0 if no_guarded_winner else 0.0,
        _strength(base_gap, primary_max_gap, "<="),
    ]) / 3
    low_score = sum([
        _strength(draw_mean, low_draw, ">="),
        _strength(under35_mean, low_under35, ">="),
        _strength(draw_ht_mean, low_draw_ht, ">="),
        _strength(strongest_base, maximum_winner_base, "<"),
    ]) / 4
    score = round(max(primary_score, low_score), 1)

    reasons = [
        f"Średnia Draw: {draw_mean:.1f}; ścieżka A próg {primary_draw:g}, ścieżka B próg {low_draw:g}",
        f"Bazy zwycięstwa: A {home_base:.1f}, B {away_base:.1f}; różnica {base_gap:.1f}, maksimum A {primary_max_gap:g}",
        f"Średni Under 3,5: {under35_mean:.1f}, minimum B {low_under35:g}",
        f"Średni remis HT: {draw_ht_mean:.1f}, minimum B {low_draw_ht:g}",
        "Ścieżka A: " + ", ".join(f"{name}={'TAK' if value else 'NIE'}" for name, value in primary_checks.items()),
        "Ścieżka B: " + ", ".join(f"{name}={'TAK' if value else 'NIE'}" for name, value in low_checks.items()),
        f"Aktywna ścieżka: {'A — podstawowa' if primary_passed else 'B — niskobramkowa' if low_passed else 'brak'}",
    ]
    threshold = primary_draw if primary_passed or draw_mean >= primary_draw else low_draw
    return Recommendation(rule["id"], rule["label"], score, passed, reasons, 100.0, draw_mean, threshold, "special")


def _evaluate_special(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation | None:
    rule_id = str(rule.get("id") or "")
    if rule_id == "btts":
        return _evaluate_btts(stats, rule)
    if rule_id == "home_win":
        return _evaluate_guarded_winner(stats, rule, "home")
    if rule_id == "away_win":
        return _evaluate_guarded_winner(stats, rule, "away")
    if rule_id == "draw":
        return _evaluate_guarded_draw(stats, rule)

    formulas = {
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
