from __future__ import annotations

from dataclasses import replace
from typing import Any

import engine_core as core
import engine_legacy as legacy

ALGORITHM_VERSION = "2.12.0"
METRIC_LABELS = legacy.METRIC_LABELS
Recommendation = legacy.Recommendation
metric_label = legacy.metric_label

DIRECTIONAL_TEAM_RULE_IDS = {
    "home_team_over15",
    "away_team_over15",
    "home_score_both_halves",
    "away_score_both_halves",
}
REMOVED_NON_BETTABLE_RULE_IDS = {"team_scored_twice", "scored_both_halves"}


def _metric_values(
    stats: dict[str, dict[str, float]],
    names: list[str],
) -> tuple[dict[str, dict[str, float]], list[str]]:
    values = {name: core._find_metric(stats, name) for name in names}
    missing = [name for name, value in values.items() if value is None]
    return {name: value for name, value in values.items() if value is not None}, missing


def _directional_team_over15(
    stats: dict[str, dict[str, float]],
    rule: dict[str, Any],
    side: str,
) -> Recommendation:
    opponent = "away" if side == "home" else "home"
    side_label = "A" if side == "home" else "B"
    opponent_label = "B" if side == "home" else "A"
    condition = (rule.get("conditions") or [{}])[0]
    names = [
        "Team scored twice",
        "Goals scored per game",
        "Goals conceded per game",
        "Team scored",
        "Clean sheets",
    ]
    values, missing = _metric_values(stats, names)
    base_threshold = float(condition.get("minimum_team_scored_twice", 50))
    if missing:
        return Recommendation(
            str(rule["id"]), str(rule["label"]), 0.0, False,
            ["Brak danych do kierunkowego team total: " + ", ".join(missing)],
            100.0 * (len(names) - len(missing)) / len(names), None,
            base_threshold, "special",
        )

    twice = float(values["Team scored twice"][side])
    own_goals = float(values["Goals scored per game"][side])
    opponent_conceded = float(values["Goals conceded per game"][opponent])
    own_scored = float(values["Team scored"][side])
    opponent_clean = float(values["Clean sheets"][opponent])

    minimum_own_goals = float(condition.get("minimum_own_goals", 1.5))
    minimum_opponent_conceded = float(condition.get("minimum_opponent_conceded", 1.2))
    minimum_team_scored = float(condition.get("minimum_team_scored", 80))
    maximum_opponent_clean = float(condition.get("maximum_opponent_clean_sheets", 30))
    minimum_supports = int(condition.get("minimum_supports", 2))

    base_passed = twice >= base_threshold
    supports = {
        f"gole {side_label}": own_goals >= minimum_own_goals,
        f"gole tracone {opponent_label}": opponent_conceded >= minimum_opponent_conceded,
        f"Team scored {side_label}": own_scored >= minimum_team_scored,
        f"clean sheets {opponent_label}": opponent_clean <= maximum_opponent_clean,
    }
    support_count = sum(supports.values())
    passed = base_passed and support_count >= minimum_supports
    component_scores = [
        core._strength(twice, base_threshold, ">="),
        core._strength(own_goals, minimum_own_goals, ">="),
        core._strength(opponent_conceded, minimum_opponent_conceded, ">="),
        core._strength(own_scored, minimum_team_scored, ">="),
        core._strength(opponent_clean, maximum_opponent_clean, "<="),
    ]
    reasons = [
        f"Kierunkowy rynek drużynowy: {side_label} powyżej 1,5 gola",
        f"Baza Team scored twice {side_label}: {twice:.1f}% ≥ {base_threshold:g}% — {'TAK' if base_passed else 'NIE'}",
        f"Ofensywa {side_label}: {own_goals:.2f} gola/mecz, minimum {minimum_own_goals:g}",
        f"Defensywa {opponent_label}: {opponent_conceded:.2f} straconego gola/mecz, minimum {minimum_opponent_conceded:g}",
        f"Team scored {side_label}: {own_scored:.1f}%, minimum {minimum_team_scored:g}%",
        f"Clean sheets {opponent_label}: {opponent_clean:.1f}%, maksimum {maximum_opponent_clean:g}%",
        f"Wsparcia: {support_count}/4, wymagane minimum {minimum_supports}; "
        + ", ".join(f"{name}={'TAK' if ok else 'NIE'}" for name, ok in supports.items()),
    ]
    return Recommendation(
        str(rule["id"]), str(rule["label"]),
        round(sum(component_scores) / len(component_scores), 1), passed, reasons,
        100.0, round(twice, 2), base_threshold, "special",
    )


def _directional_score_both_halves(
    stats: dict[str, dict[str, float]],
    rule: dict[str, Any],
    side: str,
) -> Recommendation:
    opponent = "away" if side == "home" else "home"
    side_label = "A" if side == "home" else "B"
    opponent_label = "B" if side == "home" else "A"
    condition = (rule.get("conditions") or [{}])[0]
    names = [
        "Scored in both halves",
        "Goals scored per game",
        "Goals conceded per game",
        "Team scored",
        "Clean sheets",
    ]
    values, missing = _metric_values(stats, names)
    base_threshold = float(condition.get("minimum_scored_both_halves", 50))
    if missing:
        return Recommendation(
            str(rule["id"]), str(rule["label"]), 0.0, False,
            ["Brak danych do kierunkowego rynku obu połów: " + ", ".join(missing)],
            100.0 * (len(names) - len(missing)) / len(names), None,
            base_threshold, "special",
        )

    both_halves = float(values["Scored in both halves"][side])
    own_goals = float(values["Goals scored per game"][side])
    opponent_conceded = float(values["Goals conceded per game"][opponent])
    own_scored = float(values["Team scored"][side])
    opponent_clean = float(values["Clean sheets"][opponent])

    minimum_own_goals = float(condition.get("minimum_own_goals", 1.4))
    minimum_opponent_conceded = float(condition.get("minimum_opponent_conceded", 1.2))
    minimum_team_scored = float(condition.get("minimum_team_scored", 80))
    maximum_opponent_clean = float(condition.get("maximum_opponent_clean_sheets", 30))
    minimum_supports = int(condition.get("minimum_supports", 2))

    base_passed = both_halves >= base_threshold
    supports = {
        f"gole {side_label}": own_goals >= minimum_own_goals,
        f"gole tracone {opponent_label}": opponent_conceded >= minimum_opponent_conceded,
        f"Team scored {side_label}": own_scored >= minimum_team_scored,
        f"clean sheets {opponent_label}": opponent_clean <= maximum_opponent_clean,
    }
    support_count = sum(supports.values())
    passed = base_passed and support_count >= minimum_supports
    component_scores = [
        core._strength(both_halves, base_threshold, ">="),
        core._strength(own_goals, minimum_own_goals, ">="),
        core._strength(opponent_conceded, minimum_opponent_conceded, ">="),
        core._strength(own_scored, minimum_team_scored, ">="),
        core._strength(opponent_clean, maximum_opponent_clean, "<="),
    ]
    reasons = [
        f"Kierunkowy rynek czasowy: {side_label} strzeli w obu połowach",
        f"Baza Scored in both halves {side_label}: {both_halves:.1f}% ≥ {base_threshold:g}% — {'TAK' if base_passed else 'NIE'}",
        f"Wsparcia: {support_count}/4, wymagane minimum {minimum_supports}; "
        + ", ".join(f"{name}={'TAK' if ok else 'NIE'}" for name, ok in supports.items()),
    ]
    return Recommendation(
        str(rule["id"]), str(rule["label"]),
        round(sum(component_scores) / len(component_scores), 1), passed, reasons,
        100.0, round(both_halves, 2), base_threshold, "special",
    )


def _directional_rules(home_team: str, away_team: str) -> list[dict[str, Any]]:
    shared_over15 = {
        "minimum_team_scored_twice": 50,
        "minimum_own_goals": 1.5,
        "minimum_opponent_conceded": 1.2,
        "minimum_team_scored": 80,
        "maximum_opponent_clean_sheets": 30,
        "minimum_supports": 2,
    }
    shared_halves = {
        "minimum_scored_both_halves": 50,
        "minimum_own_goals": 1.4,
        "minimum_opponent_conceded": 1.2,
        "minimum_team_scored": 80,
        "maximum_opponent_clean_sheets": 30,
        "minimum_supports": 2,
    }
    return [
        {"id": "home_team_over15", "label": f"{home_team} strzeli powyżej 1,5 gola", "enabled": True, "mode": "special", "conditions": [shared_over15]},
        {"id": "away_team_over15", "label": f"{away_team} strzeli powyżej 1,5 gola", "enabled": True, "mode": "special", "conditions": [shared_over15]},
        {"id": "home_score_both_halves", "label": f"{home_team} strzeli w obu połowach", "enabled": True, "mode": "special", "conditions": [shared_halves]},
        {"id": "away_score_both_halves", "label": f"{away_team} strzeli w obu połowach", "enabled": True, "mode": "special", "conditions": [shared_halves]},
    ]


def evaluate_rule(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation:
    rule_id = str(rule.get("id") or "")
    if rule_id == "home_team_over15":
        return _directional_team_over15(stats, rule, "home")
    if rule_id == "away_team_over15":
        return _directional_team_over15(stats, rule, "away")
    if rule_id == "home_score_both_halves":
        return _directional_score_both_halves(stats, rule, "home")
    if rule_id == "away_score_both_halves":
        return _directional_score_both_halves(stats, rule, "away")
    return legacy.evaluate_rule(stats, rule)


def selection_telemetry(recommendations: list[Recommendation]) -> list[dict[str, Any]]:
    rows = legacy.selection_telemetry(recommendations)
    for row in rows:
        row["algorithm_version"] = ALGORITHM_VERSION
    return rows


def analyze_match(match: dict[str, Any], config: dict[str, Any]) -> list[Recommendation]:
    source_stats = match.get("stats", {})
    stats, goal_total_warnings = legacy._canonicalize_goal_totals(source_stats)
    home_team = str(match.get("home_team") or "Drużyna A")
    away_team = str(match.get("away_team") or "Drużyna B")
    rules = [
        rule for rule in config["recommendations"].get("rules", [])
        if str(rule.get("id") or "") not in REMOVED_NON_BETTABLE_RULE_IDS
    ]
    rules.extend(_directional_rules(home_team, away_team))

    btts_no_cfg = config["recommendations"].get("btts_no", {})
    if bool(btts_no_cfg.get("enabled", True)) and not any(str(rule.get("id")) == "btts_no" for rule in rules):
        rules.append({
            "id": "btts_no", "label": "BTTS NIE — przynajmniej jedna drużyna nie strzeli", "enabled": True,
            "mode": "special", "conditions": [{
                "maximum_btts": btts_no_cfg.get("maximum_btts", 40),
                "maximum_weak_team_scored": btts_no_cfg.get("maximum_weak_team_scored", 50),
                "maximum_weak_goals": btts_no_cfg.get("maximum_weak_goals", 0.9),
                "minimum_opponent_clean_sheets": btts_no_cfg.get("minimum_opponent_clean_sheets", 35),
                "maximum_opponent_conceded": btts_no_cfg.get("maximum_opponent_conceded", 1.1),
                "minimum_under25": btts_no_cfg.get("minimum_under25", 60),
            }],
        })

    recommendations: list[Recommendation] = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        rule_id = str(rule.get("id") or "")
        rec = evaluate_rule(stats, rule)
        if goal_total_warnings and rule_id in {"total4", "total4plus"}:
            rec = replace(rec, reasons=[*rec.reasons, "Normalizacja sum goli: " + " | ".join(goal_total_warnings)])
        recommendations.append(rec)
    return legacy.apply_final_selection(recommendations, config)


def analyze_match_report(match: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    recommendations = analyze_match(match, config)
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "recommendations": recommendations,
        "telemetry": selection_telemetry(recommendations),
    }
