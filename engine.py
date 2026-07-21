from __future__ import annotations

from dataclasses import replace
from typing import Any

import engine_core as core

ALGORITHM_VERSION = "2.5.0"
METRIC_LABELS = core.METRIC_LABELS
Recommendation = core.Recommendation
metric_label = core.metric_label

EXACT_TOTAL_RULE_IDS = {"total0", "total1", "total2", "total3", "total4", "total01", "total23", "total4plus"}
OVER_QUALITY_RULE_IDS = {"over25", "over35"}


def _evaluate_btts(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation:
    condition = (rule.get("conditions") or [{}])[0]
    required_names = ["Both Teams to Score", "Team scored", "Under 2.5 goals"]
    required = {name: core._find_metric(stats, name) for name in required_names}
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
    threshold_home, threshold_away = core._thresholds(condition)
    mean_threshold = (threshold_home + threshold_away) / 2
    minimum_btts = float(condition.get("minimum_btts", 45))
    minimum_team_scored = float(condition.get("minimum_team_scored", 70))
    maximum_under25 = float(condition.get("maximum_under25", 65))

    goals = core._find_metric(stats, "Goals scored per game")
    clean_sheets = core._find_metric(stats, "Clean sheets")
    dominance_profile = False
    dominance_escape = False
    dominance_reason = "Blok dominacji jednostronnej: brak pełnych danych — nieaktywny"

    if goals is not None and clean_sheets is not None:
        goals_home = float(goals["home"])
        goals_away = float(goals["away"])
        dominant_side = "home" if goals_home >= goals_away else "away"
        weaker_side = "away" if dominant_side == "home" else "home"
        dominant_goals = float(goals[dominant_side])
        weaker_goals = float(goals[weaker_side])
        goal_gap = dominant_goals - weaker_goals
        dominant_clean_sheets = float(clean_sheets[dominant_side])
        weaker_team_scored = float(team_scored[weaker_side])
        weaker_btts = float(btts[weaker_side])

        dominance_min_goals = float(condition.get("dominance_min_goals", 2.0))
        dominance_min_gap = float(condition.get("dominance_min_gap", 1.0))
        dominance_min_clean_sheets = float(condition.get("dominance_min_clean_sheets", 40))
        dominance_max_weaker_goals = float(condition.get("dominance_max_weaker_goals", 1.2))
        dominance_escape_team_scored = float(condition.get("dominance_escape_team_scored", 90))
        dominance_escape_btts = float(condition.get("dominance_escape_btts", 70))

        dominance_profile = (
            dominant_goals >= dominance_min_goals
            and goal_gap >= dominance_min_gap
            and dominant_clean_sheets >= dominance_min_clean_sheets
            and weaker_goals <= dominance_max_weaker_goals
        )
        dominance_escape = (
            weaker_team_scored >= dominance_escape_team_scored
            and weaker_btts >= dominance_escape_btts
        )
        side_label = "A" if dominant_side == "home" else "B"
        weaker_label = "B" if dominant_side == "home" else "A"
        dominance_reason = (
            f"Dominacja {side_label}: gole {dominant_goals:.2f} vs {weaker_goals:.2f}, "
            f"różnica {goal_gap:.2f}, czyste konta {dominant_clean_sheets:.1f}%; "
            f"wyjątek {weaker_label}: Team scored {weaker_team_scored:.1f}%/{dominance_escape_team_scored:g}, "
            f"BTTS {weaker_btts:.1f}%/{dominance_escape_btts:g}; "
            f"blok={'TAK' if dominance_profile and not dominance_escape else 'NIE'}"
        )

    no_unilateral_dominance_block = not dominance_profile or dominance_escape
    checks = {
        "średnia BTTS": btts_mean >= mean_threshold,
        "minimum BTTS": btts_minimum >= minimum_btts,
        "Team scored A": team_scored_home >= minimum_team_scored,
        "Team scored B": team_scored_away >= minimum_team_scored,
        "średni Under 2,5": under25_mean < maximum_under25,
        "brak bloku dominacji jednostronnej": no_unilateral_dominance_block,
    }
    component_scores = [
        core._strength(btts_mean, mean_threshold, ">="),
        core._strength(btts_minimum, minimum_btts, ">="),
        core._strength(team_scored_home, minimum_team_scored, ">="),
        core._strength(team_scored_away, minimum_team_scored, ">="),
        core._strength(under25_mean, maximum_under25, "<"),
        100.0 if no_unilateral_dominance_block else 0.0,
    ]
    score = round(sum(component_scores) / len(component_scores), 1)
    reasons = [
        f"BTTS średnia: ({btts_home:.1f} + {btts_away:.1f}) / 2 = {btts_mean:.1f}, próg {mean_threshold:g}",
        f"BTTS słabszej strony: {btts_minimum:.1f}, minimum {minimum_btts:g}",
        f"Team scored: A {team_scored_home:.1f}, B {team_scored_away:.1f}, minimum {minimum_team_scored:g}",
        f"Średni Under 2,5: {under25_mean:.1f}, wymagane poniżej {maximum_under25:g}",
        dominance_reason,
        "Warunki: " + ", ".join(f"{name}={'TAK' if value else 'NIE'}" for name, value in checks.items()),
    ]
    return Recommendation(
        rule["id"], rule["label"], score, all(checks.values()), reasons,
        100.0, btts_mean, mean_threshold, "special",
    )


def _goal_data_conflicts(
    stats: dict[str, dict[str, float]],
    consistency_config: dict[str, Any] | None = None,
) -> list[str]:
    settings = consistency_config or {}
    max_gap = float(settings.get("maximum_4plus_gap", 20))
    under35 = core._find_metric(stats, "Under 3.5 goals")
    reported_4plus = core._find_metric(stats, "Match total goals 4+")
    exact4 = core._find_metric(stats, "Match total goals 4")
    if under35 is None or reported_4plus is None:
        return []

    conflicts: list[str] = []
    for side, label in (("home", "A"), ("away", "B")):
        derived_4plus = 100.0 - float(under35[side])
        reported = float(reported_4plus[side])
        gap = abs(derived_4plus - reported)
        if gap > max_gap:
            conflicts.append(
                f"strona {label}: 4+ z Under 3,5 = {derived_4plus:.1f}%, podane 4+ = {reported:.1f}%, różnica {gap:.1f} pp"
            )
        if exact4 is not None and float(exact4[side]) > reported:
            conflicts.append(
                f"strona {label}: dokładnie 4 gole = {float(exact4[side]):.1f}% przekracza podane 4+ = {reported:.1f}%"
            )
    return conflicts


def _apply_goal_data_quality(
    stats: dict[str, dict[str, float]],
    rule: dict[str, Any],
    result: Recommendation,
    consistency_config: dict[str, Any] | None = None,
) -> Recommendation:
    settings = consistency_config or {}
    rule_id = str(rule.get("id") or "")
    conflicts = _goal_data_conflicts(stats, settings)
    reasons = list(result.reasons)

    goals = core._find_metric(stats, "Goals scored per game")
    extreme_threshold = float(settings.get("extreme_goals_warning", 3.0))
    if goals is not None and max(float(goals["home"]), float(goals["away"])) >= extreme_threshold and rule_id in OVER_QUALITY_RULE_IDS:
        reasons.append(
            f"Ostrzeżenie: ekstremalna średnia goli ≥ {extreme_threshold:g}; możliwy wpływ wyników odstających."
        )

    if not conflicts:
        return replace(result, reasons=reasons)

    reasons.append("Niespójność danych bramkowych: " + " | ".join(conflicts))
    if rule_id in EXACT_TOTAL_RULE_IDS:
        return replace(result, passed=False, data_quality=0.0, reasons=reasons)
    if rule_id in OVER_QUALITY_RULE_IDS:
        quality_cap = float(settings.get("over_quality_cap", 80))
        return replace(result, data_quality=min(result.data_quality, quality_cap), reasons=reasons)
    return replace(result, reasons=reasons)


def evaluate_rule(
    stats: dict[str, dict[str, float]],
    rule: dict[str, Any],
    consistency_config: dict[str, Any] | None = None,
) -> Recommendation:
    if str(rule.get("id") or "") == "btts":
        result = _evaluate_btts(stats, rule)
    else:
        result = core.evaluate_rule(stats, rule)
    return _apply_goal_data_quality(stats, rule, result, consistency_config)


def analyze_match(match: dict[str, Any], config: dict[str, Any]) -> list[Recommendation]:
    recommendations = config.get("recommendations", {})
    rules = recommendations.get("rules", [])
    consistency_config = recommendations.get("goal_data_consistency", {})
    return [
        evaluate_rule(match.get("stats", {}), rule, consistency_config)
        for rule in rules
        if rule.get("enabled", True)
    ]
