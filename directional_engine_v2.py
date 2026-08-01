from __future__ import annotations

from dataclasses import replace
from typing import Any

import directional_engine_impl as impl
from directional_engine_impl import *


def analyze_match(match: dict[str, Any], config: dict[str, Any]) -> list[Recommendation]:
    source_stats = match.get("stats", {})
    stats, goal_total_warnings = impl.legacy._canonicalize_goal_totals(source_stats)
    home_team = str(match.get("home_team") or "Drużyna A")
    away_team = str(match.get("away_team") or "Drużyna B")
    rules = [
        rule for rule in config["recommendations"].get("rules", [])
        if str(rule.get("id") or "") not in impl.REMOVED_NON_BETTABLE_RULE_IDS
    ]

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

    rules.extend(impl._directional_rules(home_team, away_team))
    recommendations: list[Recommendation] = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        rule_id = str(rule.get("id") or "")
        rec = impl.evaluate_rule(stats, rule)
        if goal_total_warnings and rule_id in {"total4", "total4plus"}:
            rec = replace(rec, reasons=[*rec.reasons, "Normalizacja sum goli: " + " | ".join(goal_total_warnings)])
        recommendations.append(rec)
    return impl.legacy.apply_final_selection(recommendations, config)


def analyze_match_report(match: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    recommendations = analyze_match(match, config)
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "recommendations": recommendations,
        "telemetry": selection_telemetry(recommendations),
    }
