from __future__ import annotations

from dataclasses import replace
from typing import Any

import engine_core as core
from selection import apply_final_selection

ALGORITHM_VERSION = "2.9.0"
METRIC_LABELS = core.METRIC_LABELS
Recommendation = core.Recommendation
metric_label = core.metric_label

EXACT_TOTAL_RULE_IDS = {"total0", "total1", "total2", "total3", "total4", "total01", "total23", "total4plus"}
TOTAL_QUALITY_RULE_IDS = {"over25", "over35", "under25", "under35"}
OVER_QUALITY_RULE_IDS = {"over25", "over35"}


def _conceding_support(value: float) -> float:
    if value <= 0.7:
        return 20.0
    if value <= 1.0:
        return 40.0
    if value <= 1.3:
        return 60.0
    if value <= 1.6:
        return 80.0
    return 100.0


def _evaluate_btts(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation:
    condition = (rule.get("conditions") or [{}])[0]
    names = ["Both Teams to Score", "Team scored", "Under 2.5 goals", "Goals scored per game", "Goals conceded per game", "Clean sheets"]
    values = {name: core._find_metric(stats, name) for name in names}
    missing = [name for name, value in values.items() if value is None]
    threshold = float(condition.get("threshold_home", condition.get("threshold", 55)))
    if missing:
        return Recommendation(rule["id"], rule["label"], False, 0.0, None, threshold, "special", ["Brak danych: " + ", ".join(missing)], 0.0)

    btts_home, btts_away = values["Both Teams to Score"]
    scored_home, scored_away = values["Team scored"]
    under_home, under_away = values["Under 2.5 goals"]
    goals_home, goals_away = values["Goals scored per game"]
    conceded_home, conceded_away = values["Goals conceded per game"]
    clean_home, clean_away = values["Clean sheets"]

    btts_mean = (btts_home + btts_away) / 2
    btts_min = min(btts_home, btts_away)
    under_mean = (under_home + under_away) / 2
    minimum_btts = max(50.0, float(condition.get("minimum_btts", 45)))
    minimum_team_scored = float(condition.get("minimum_team_scored", 70))
    maximum_under25 = float(condition.get("maximum_under25", 65))

    scoring_home = (scored_home + btts_home + (100 - clean_away) + _conceding_support(conceded_away)) / 4
    scoring_away = (scored_away + btts_away + (100 - clean_home) + _conceding_support(conceded_home)) / 4
    clean_home_base = (clean_home + (100 - scored_away)) / 2
    clean_away_base = (clean_away + (100 - scored_home)) / 2
    clean_conflict = max(clean_home_base, clean_away_base) >= 60

    defensive_home = clean_home >= 50 and conceded_home <= 0.8 and goals_away <= 1.0
    defensive_away = clean_away >= 50 and conceded_away <= 0.8 and goals_home <= 1.0
    defensive_block = defensive_home or defensive_away

    dominance_min_goals = float(condition.get("dominance_min_goals", 2.0))
    dominance_min_gap = float(condition.get("dominance_min_gap", 1.0))
    dominance_min_clean = float(condition.get("dominance_min_clean_sheets", 40))
    dominance_max_weaker = float(condition.get("dominance_max_weaker_goals", 1.2))
    dominance_escape_scored = float(condition.get("dominance_escape_team_scored", 90))
    dominance_escape_btts = float(condition.get("dominance_escape_btts", 70))

    home_dominance = goals_home >= dominance_min_goals and goals_home - goals_away >= dominance_min_gap and clean_home >= dominance_min_clean and goals_away <= dominance_max_weaker
    away_dominance = goals_away >= dominance_min_goals and goals_away - goals_home >= dominance_min_gap and clean_away >= dominance_min_clean and goals_home <= dominance_max_weaker
    dominance_block = home_dominance or away_dominance
    if home_dominance and scored_away >= dominance_escape_scored and btts_away >= dominance_escape_btts:
        dominance_block = False
    if away_dominance and scored_home >= dominance_escape_scored and btts_home >= dominance_escape_btts:
        dominance_block = False

    checks = [
        (btts_mean >= threshold, f"Średnia BTTS {btts_mean:.1f}% ≥ {threshold:g}%"),
        (btts_min >= minimum_btts, f"Słabsza strona BTTS {btts_min:.1f}% ≥ {minimum_btts:g}%"),
        (scored_home >= minimum_team_scored, f"Team scored A {scored_home:.1f}% ≥ {minimum_team_scored:g}%"),
        (scored_away >= minimum_team_scored, f"Team scored B {scored_away:.1f}% ≥ {minimum_team_scored:g}%"),
        (goals_home >= 1.0, f"Gole A {goals_home:.2f} ≥ 1.00"),
        (goals_away >= 1.0, f"Gole B {goals_away:.2f} ≥ 1.00"),
        (max(goals_home, goals_away) >= 1.4, f"Mocniejsza ofensywa {max(goals_home, goals_away):.2f} ≥ 1.40"),
        (under_mean < maximum_under25, f"Średni Under 2.5 {under_mean:.1f}% < {maximum_under25:g}%"),
        (scoring_home >= 60, f"Baza strzelenia A {scoring_home:.1f}% ≥ 60%"),
        (scoring_away >= 60, f"Baza strzelenia B {scoring_away:.1f}% ≥ 60%"),
        (not clean_conflict, f"Brak konfliktu clean sheet (max baza {max(clean_home_base, clean_away_base):.1f}% < 60%)"),
        (not defensive_block, "Brak twardego bloku defensywnego"),
        (not dominance_block, "Brak twardego bloku dominacji"),
    ]
    passed = all(ok for ok, _ in checks)
    scores = [
        core._strength(btts_mean, threshold, ">="),
        core._strength(btts_min, minimum_btts, ">="),
        core._strength(scored_home, minimum_team_scored, ">="),
        core._strength(scored_away, minimum_team_scored, ">="),
        core._strength(goals_home, 1.0, ">="),
        core._strength(goals_away, 1.0, ">="),
        core._strength(max(goals_home, goals_away), 1.4, ">="),
        core._strength(under_mean, maximum_under25, "<"),
        core._strength(scoring_home, 60, ">="),
        core._strength(scoring_away, 60, ">="),
        100.0 if not clean_conflict else 0.0,
        100.0 if not defensive_block else 0.0,
        100.0 if not dominance_block else 0.0,
    ]
    score = round(sum(scores) / len(scores), 1)
    reasons = [("TAK: " if ok else "NIE: ") + text for ok, text in checks]
    return Recommendation(rule["id"], rule["label"], passed, score, round(btts_mean, 2), threshold, "special", reasons, 100.0)


def _goal_data_quality(stats: dict[str, dict[str, float]], config: dict[str, Any]) -> tuple[bool, list[str]]:
    total4plus = core._find_metric(stats, "Match total goals 4+")
    total4 = core._find_metric(stats, "Match total goals 4")
    under35 = core._find_metric(stats, "Under 3.5 goals")
    if total4plus is None or total4 is None or under35 is None:
        return False, ["Brak pełnych danych do kontroli sum goli"]

    cfg = config.get("recommendations", {}).get("goal_data_consistency", {})
    maximum_gap = float(cfg.get("maximum_4plus_gap", 20))
    reasons = []
    conflict = False
    for side, index in (("A", 0), ("B", 1)):
        reported = float(total4plus[index])
        exact4 = float(total4[index])
        derived = 100.0 - float(under35[index])
        gap = abs(reported - derived)
        if gap > maximum_gap:
            conflict = True
            reasons.append(f"{side}: 4+ {reported:.1f}% vs 100-Under3.5 {derived:.1f}% (różnica {gap:.1f} pp)")
        if exact4 > reported:
            conflict = True
            reasons.append(f"{side}: dokładnie 4 gole {exact4:.1f}% > zgłoszone 4+ {reported:.1f}%")
    return conflict, reasons


def analyze_match(match: dict[str, Any], config: dict[str, Any]) -> list[Recommendation]:
    stats = match.get("stats", {})
    recommendations = []
    for rule in config["recommendations"].get("rules", []):
        if not rule.get("enabled", True):
            continue
        if rule.get("id") == "btts":
            recommendations.append(_evaluate_btts(stats, rule))
        else:
            recommendations.append(core.evaluate_rule(stats, rule))

    conflict, conflict_reasons = _goal_data_quality(stats, config)
    if conflict:
        cap = float(config.get("recommendations", {}).get("goal_data_consistency", {}).get("over_quality_cap", 80))
        adjusted = []
        for rec in recommendations:
            if rec.rule_id in EXACT_TOTAL_RULE_IDS:
                adjusted.append(replace(rec, passed=False, data_quality=0.0, reasons=[*rec.reasons, "Konflikt danych sum goli: " + " | ".join(conflict_reasons)]))
            elif rec.rule_id in TOTAL_QUALITY_RULE_IDS:
                adjusted.append(replace(rec, data_quality=min(float(rec.data_quality), cap), reasons=[*rec.reasons, "Obniżona jakość danych sum goli: " + " | ".join(conflict_reasons)]))
            else:
                adjusted.append(rec)
        recommendations = adjusted

    return apply_final_selection(recommendations, config)
