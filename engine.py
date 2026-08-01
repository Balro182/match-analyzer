from __future__ import annotations

from dataclasses import replace
from typing import Any

import engine_core as core
from selection import apply_final_selection

ALGORITHM_VERSION = "2.11.0"
METRIC_LABELS = core.METRIC_LABELS
Recommendation = core.Recommendation
metric_label = core.metric_label

# Public compatibility API used by the historical test suite and external callers.
evaluate_rule = core.evaluate_rule

HTFT_RULE_IDS = {
    "win_win", "win_draw", "win_lose",
    "draw_win", "draw_draw", "draw_lose",
    "lose_win", "lose_draw", "lose_lose",
}

HTFT_DIRECTIONAL_PAIRS = {
    "win_win": ("Win HT - Win FT", "Lose HT - Lose FT", "A/A"),
    "win_draw": ("Win HT - Draw FT", "Lose HT - Draw FT", "A/X"),
    "win_lose": ("Win HT - Lose FT", "Lose HT - Win FT", "A/B"),
    "draw_win": ("Draw HT - Win FT", "Draw HT - Lose FT", "X/A"),
    "draw_draw": ("Draw HT - Draw FT", "Draw HT - Draw FT", "X/X"),
    "draw_lose": ("Draw HT - Lose FT", "Draw HT - Win FT", "X/B"),
    "lose_win": ("Lose HT - Win FT", "Win HT - Lose FT", "B/A"),
    "lose_draw": ("Lose HT - Draw FT", "Win HT - Draw FT", "B/X"),
    "lose_lose": ("Lose HT - Lose FT", "Win HT - Win FT", "B/B"),
}


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


def _canonicalize_goal_totals(
    stats: dict[str, dict[str, float]],
) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Use 100 - Under 3.5 as the canonical definition of 4+ goals."""
    normalized = {
        name: dict(values) if isinstance(values, dict) else values
        for name, values in stats.items()
    }
    under35 = core._find_metric(stats, "Under 3.5 goals")
    if under35 is None:
        return normalized, []

    source_four_plus = core._find_metric(stats, "Match total goals 4+")
    exact_four = core._find_metric(stats, "Match total goals 4")
    canonical = {
        "home": max(0.0, min(100.0, 100.0 - float(under35["home"]))),
        "away": max(0.0, min(100.0, 100.0 - float(under35["away"]))),
    }
    warnings: list[str] = []

    if source_four_plus is not None:
        for side, key in (("A", "home"), ("B", "away")):
            reported = float(source_four_plus[key])
            derived = canonical[key]
            if abs(reported - derived) > 0.01:
                warnings.append(
                    f"{side}: źródłowe 4+ {reported:.1f}% zastąpiono "
                    f"wartością 100-Under3.5 = {derived:.1f}%"
                )

    normalized["Match total goals 4+"] = canonical

    if exact_four is not None:
        capped = {
            "home": min(float(exact_four["home"]), canonical["home"]),
            "away": min(float(exact_four["away"]), canonical["away"]),
        }
        for side, key in (("A", "home"), ("B", "away")):
            if float(exact_four[key]) > canonical[key]:
                warnings.append(
                    f"{side}: dokładnie 4 gole {float(exact_four[key]):.1f}% "
                    f"ograniczono do kanonicznego 4+ {canonical[key]:.1f}%"
                )
        normalized["Match total goals 4"] = capped

    return normalized, warnings


def _evaluate_htft(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation:
    rule_id = str(rule.get("id") or "")
    home_metric_name, away_metric_name, formula_label = HTFT_DIRECTIONAL_PAIRS[rule_id]
    home_metric = core._find_metric(stats, home_metric_name)
    away_metric = core._find_metric(stats, away_metric_name)
    condition = (rule.get("conditions") or [{}])[0]
    threshold_home, threshold_away = core._thresholds(condition)
    threshold = (threshold_home + threshold_away) / 2

    missing = []
    if home_metric is None:
        missing.append(home_metric_name)
    if away_metric is None:
        missing.append(away_metric_name)
    if missing:
        return Recommendation(
            rule_id=rule_id,
            label=rule["label"],
            score=0.0,
            passed=False,
            reasons=["Brak danych do kierunkowej formuły HT/FT: " + ", ".join(missing)],
            data_quality=0.0,
            raw_value=None,
            threshold=threshold,
            mode="special",
        )

    home_value = float(home_metric["home"])
    away_value = float(away_metric["away"])
    value = (home_value + away_value) / 2
    op_text = str(condition.get("operator", ">="))
    passed = core.OPS[op_text](value, threshold)
    score = round(core._strength(value, threshold, op_text), 1)
    reasons = [
        f"Kierunkowe HT/FT {formula_label}",
        f"profil A {home_metric_name} = {home_value:.1f}%",
        f"profil B {away_metric_name} = {away_value:.1f}%",
        f"średnia ({home_value:.1f} + {away_value:.1f}) / 2 = {value:.1f}%; próg {threshold:g}%; score {score:.1f}",
    ]
    return Recommendation(
        rule_id=rule_id,
        label=rule["label"],
        score=score,
        passed=passed,
        reasons=reasons,
        data_quality=100.0,
        raw_value=round(value, 2),
        threshold=threshold,
        mode="special",
    )


def _evaluate_btts(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation:
    condition = (rule.get("conditions") or [{}])[0]
    names = [
        "Both Teams to Score", "Team scored", "Under 2.5 goals",
        "Goals scored per game", "Goals conceded per game", "Clean sheets",
    ]
    values = {name: core._find_metric(stats, name) for name in names}
    missing = [name for name, value in values.items() if value is None]
    threshold = float(condition.get("threshold_home", condition.get("threshold", 55)))
    if missing:
        return Recommendation(
            rule_id=rule["id"], label=rule["label"], score=0.0, passed=False,
            reasons=["Brak danych: " + ", ".join(missing)], data_quality=0.0,
            raw_value=None, threshold=threshold, mode="special",
        )

    btts = values["Both Teams to Score"]
    scored = values["Team scored"]
    under = values["Under 2.5 goals"]
    goals = values["Goals scored per game"]
    conceded = values["Goals conceded per game"]
    clean = values["Clean sheets"]
    assert btts and scored and under and goals and conceded and clean

    btts_home, btts_away = float(btts["home"]), float(btts["away"])
    scored_home, scored_away = float(scored["home"]), float(scored["away"])
    under_home, under_away = float(under["home"]), float(under["away"])
    goals_home, goals_away = float(goals["home"]), float(goals["away"])
    conceded_home, conceded_away = float(conceded["home"]), float(conceded["away"])
    clean_home, clean_away = float(clean["home"]), float(clean["away"])

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
    return Recommendation(
        rule_id=rule["id"], label=rule["label"], score=score, passed=passed,
        reasons=reasons, data_quality=100.0, raw_value=round(btts_mean, 2),
        threshold=threshold, mode="special",
    )


def _evaluate_btts_no(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation:
    """Independent BTTS NO rule; never inferred merely from BTTS YES failing."""
    condition = (rule.get("conditions") or [{}])[0]
    names = [
        "Both Teams to Score", "Team scored", "Under 2.5 goals",
        "Goals scored per game", "Goals conceded per game", "Clean sheets",
    ]
    values = {name: core._find_metric(stats, name) for name in names}
    missing = [name for name, value in values.items() if value is None]
    maximum_btts = float(condition.get("maximum_btts", 40))
    if missing:
        return Recommendation(
            rule_id=rule["id"], label=rule["label"], score=0.0, passed=False,
            reasons=["Brak danych: " + ", ".join(missing)], data_quality=0.0,
            raw_value=None, threshold=maximum_btts, mode="special",
        )

    btts = values["Both Teams to Score"]
    scored = values["Team scored"]
    under = values["Under 2.5 goals"]
    goals = values["Goals scored per game"]
    conceded = values["Goals conceded per game"]
    clean = values["Clean sheets"]
    assert btts and scored and under and goals and conceded and clean

    btts_mean = (float(btts["home"]) + float(btts["away"])) / 2
    under_mean = (float(under["home"]) + float(under["away"])) / 2
    maximum_team_scored = float(condition.get("maximum_weak_team_scored", 50))
    maximum_weak_goals = float(condition.get("maximum_weak_goals", 0.9))
    minimum_opponent_clean = float(condition.get("minimum_opponent_clean_sheets", 35))
    maximum_opponent_conceded = float(condition.get("maximum_opponent_conceded", 1.1))
    minimum_under25 = float(condition.get("minimum_under25", 60))

    home_weak = (
        float(scored["home"]) <= maximum_team_scored
        and float(goals["home"]) <= maximum_weak_goals
        and float(clean["away"]) >= minimum_opponent_clean
        and float(conceded["away"]) <= maximum_opponent_conceded
    )
    away_weak = (
        float(scored["away"]) <= maximum_team_scored
        and float(goals["away"]) <= maximum_weak_goals
        and float(clean["home"]) >= minimum_opponent_clean
        and float(conceded["home"]) <= maximum_opponent_conceded
    )
    weak_attack_confirmed = home_weak or away_weak

    checks = [
        (btts_mean <= maximum_btts, f"Średnia BTTS {btts_mean:.1f}% ≤ {maximum_btts:g}%"),
        (weak_attack_confirmed, "Potwierdzona słaba ofensywa jednej strony i defensywa rywala"),
        (under_mean >= minimum_under25, f"Średni Under 2.5 {under_mean:.1f}% ≥ {minimum_under25:g}%"),
    ]
    passed = all(ok for ok, _ in checks)
    score = round(sum([
        core._strength(btts_mean, maximum_btts, "<="),
        120.0 if weak_attack_confirmed else 0.0,
        core._strength(under_mean, minimum_under25, ">="),
    ]) / 3, 1)
    reasons = [("TAK: " if ok else "NIE: ") + text for ok, text in checks]
    if home_weak:
        reasons.append("Słaba ofensywa A jest blokowana przez defensywę B")
    if away_weak:
        reasons.append("Słaba ofensywa B jest blokowana przez defensywę A")
    return Recommendation(
        rule_id=rule["id"], label=rule["label"], score=score, passed=passed,
        reasons=reasons, data_quality=100.0, raw_value=round(100.0 - btts_mean, 2),
        threshold=100.0 - maximum_btts, mode="special",
    )


def selection_telemetry(recommendations: list[Recommendation]) -> list[dict[str, Any]]:
    """Return machine-readable diagnostics for every evaluated recommendation."""
    rows: list[dict[str, Any]] = []
    for rec in recommendations:
        level = "rejected"
        for reason in rec.reasons:
            if "Poziom selekcji: główny typ" in reason:
                level = "main"
                break
            if "Poziom selekcji: dodatkowy sygnał" in reason:
                level = "additional"
                break
        threshold_margin = None
        if rec.raw_value is not None and rec.threshold is not None:
            threshold_margin = round(float(rec.raw_value) - float(rec.threshold), 2)
        rows.append({
            "algorithm_version": ALGORITHM_VERSION,
            "rule_id": rec.rule_id,
            "label": rec.label,
            "selected_level": level,
            "passed": bool(rec.passed),
            "raw_value": rec.raw_value,
            "threshold": rec.threshold,
            "threshold_margin": threshold_margin,
            "score": rec.score,
            "data_quality": rec.data_quality,
            "mode": rec.mode,
            "reasons": list(rec.reasons),
        })
    return rows


def analyze_match(match: dict[str, Any], config: dict[str, Any]) -> list[Recommendation]:
    source_stats = match.get("stats", {})
    stats, goal_total_warnings = _canonicalize_goal_totals(source_stats)
    recommendations = []
    for rule in config["recommendations"].get("rules", []):
        if not rule.get("enabled", True):
            continue
        rule_id = str(rule.get("id") or "")
        if rule_id == "btts":
            rec = _evaluate_btts(stats, rule)
        elif rule_id == "btts_no":
            rec = _evaluate_btts_no(stats, rule)
        elif rule_id in HTFT_RULE_IDS:
            rec = _evaluate_htft(stats, rule)
        else:
            rec = core.evaluate_rule(stats, rule)

        if goal_total_warnings and rule_id in {"total4", "total4plus"}:
            rec = replace(
                rec,
                reasons=[
                    *rec.reasons,
                    "Normalizacja sum goli: " + " | ".join(goal_total_warnings),
                ],
            )
        recommendations.append(rec)

    return apply_final_selection(recommendations, config)


def analyze_match_report(match: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    recommendations = analyze_match(match, config)
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "recommendations": recommendations,
        "telemetry": selection_telemetry(recommendations),
    }
