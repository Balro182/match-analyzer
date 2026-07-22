from __future__ import annotations

from dataclasses import replace
from typing import Any

import engine_core as core
from selection import apply_final_selection

ALGORITHM_VERSION = "2.8.0"
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
    if missing:
        return Recommendation(
            rule["id"], rule["label"], 0.0, False,
            ["Brak danych do zabezpieczonej formuły BTTS: " + ", ".join(missing)],
            100.0 * (len(names) - len(missing)) / len(names), mode="special",
        )

    btts = values["Both Teams to Score"]
    team_scored = values["Team scored"]
    under25 = values["Under 2.5 goals"]
    goals = values["Goals scored per game"]
    conceded = values["Goals conceded per game"]
    clean = values["Clean sheets"]
    assert btts and team_scored and under25 and goals and conceded and clean

    bh, ba = float(btts["home"]), float(btts["away"])
    tsh, tsa = float(team_scored["home"]), float(team_scored["away"])
    gh, ga = float(goals["home"]), float(goals["away"])
    ch, ca = float(conceded["home"]), float(conceded["away"])
    csh, csa = float(clean["home"]), float(clean["away"])
    btts_mean, btts_min = (bh + ba) / 2, min(bh, ba)
    under_mean = (float(under25["home"]) + float(under25["away"])) / 2
    th, ta = core._thresholds(condition)
    mean_threshold = (th + ta) / 2

    minimum_btts = max(50.0, float(condition.get("minimum_btts", 50)))
    minimum_team_scored = max(70.0, float(condition.get("minimum_team_scored", 70)))
    minimum_side_goals = max(1.0, float(condition.get("minimum_side_goals", 1.0)))
    minimum_strong_goals = max(1.4, float(condition.get("minimum_strong_side_goals", 1.4)))
    maximum_under25 = min(65.0, float(condition.get("maximum_under25", 65)))
    minimum_scoring_base = max(60.0, float(condition.get("minimum_scoring_base", 60)))
    strong_clean_base = max(60.0, float(condition.get("strong_clean_sheet_base", 60)))

    scoring_home = (tsh + bh + (100 - csa) + _conceding_support(ca)) / 4
    scoring_away = (tsa + ba + (100 - csh) + _conceding_support(ch)) / 4
    clean_base_home = (csh + (100 - tsa)) / 2
    clean_base_away = (csa + (100 - tsh)) / 2
    no_clean_conflict = max(clean_base_home, clean_base_away) < strong_clean_base

    dominant = "home" if gh >= ga else "away"
    weaker = "away" if dominant == "home" else "home"
    dominant_goals, weaker_goals = float(goals[dominant]), float(goals[weaker])
    dominance = (
        dominant_goals >= float(condition.get("dominance_min_goals", 2.0))
        and dominant_goals - weaker_goals >= float(condition.get("dominance_min_gap", 1.0))
        and float(clean[dominant]) >= float(condition.get("dominance_min_clean_sheets", 40))
        and weaker_goals <= float(condition.get("dominance_max_weaker_goals", 1.2))
    )
    escape = (
        float(team_scored[weaker]) >= float(condition.get("dominance_escape_team_scored", 90))
        and float(btts[weaker]) >= float(condition.get("dominance_escape_btts", 70))
    )
    no_dominance_block = not dominance or escape

    defensive_home = csh >= 50 and ch <= 0.8 and ga <= 1.0
    defensive_away = csa >= 50 and ca <= 0.8 and gh <= 1.0
    no_defensive_block = not defensive_home and not defensive_away

    checks = {
        "średnia BTTS": btts_mean >= mean_threshold,
        "minimum BTTS": btts_min >= minimum_btts,
        "Team scored A": tsh >= minimum_team_scored,
        "Team scored B": tsa >= minimum_team_scored,
        "gole A": gh >= minimum_side_goals,
        "gole B": ga >= minimum_side_goals,
        "mocniejsza ofensywa": max(gh, ga) >= minimum_strong_goals,
        "średni Under 2,5": under_mean < maximum_under25,
        "scoring base A": scoring_home >= minimum_scoring_base,
        "scoring base B": scoring_away >= minimum_scoring_base,
        "brak twardego konfliktu clean sheet": no_clean_conflict,
        "brak bloku defensywnego": no_defensive_block,
        "brak bloku dominacji jednostronnej": no_dominance_block,
    }
    scores = [
        core._strength(btts_mean, mean_threshold, ">="), core._strength(btts_min, minimum_btts, ">="),
        core._strength(tsh, minimum_team_scored, ">="), core._strength(tsa, minimum_team_scored, ">="),
        core._strength(gh, minimum_side_goals, ">="), core._strength(ga, minimum_side_goals, ">="),
        core._strength(max(gh, ga), minimum_strong_goals, ">="), core._strength(under_mean, maximum_under25, "<"),
        core._strength(scoring_home, minimum_scoring_base, ">="), core._strength(scoring_away, minimum_scoring_base, ">="),
        100.0 if no_clean_conflict else 0.0, 100.0 if no_defensive_block else 0.0, 100.0 if no_dominance_block else 0.0,
    ]
    reasons = [
        f"BTTS średnia: {btts_mean:.1f}, próg {mean_threshold:g}; minimum strony {btts_min:.1f}/{minimum_btts:g}",
        f"Team scored: A {tsh:.1f}, B {tsa:.1f}; minimum {minimum_team_scored:g}",
        f"Gole na mecz: A {gh:.2f}, B {ga:.2f}; minimum obu {minimum_side_goals:g}, jednej {minimum_strong_goals:g}",
        f"Scoring base A: {scoring_home:.1f}, B: {scoring_away:.1f}; minimum {minimum_scoring_base:g}",
        f"Baza clean sheet A: {clean_base_home:.1f}, B: {clean_base_away:.1f}; twardy blok od {strong_clean_base:g}",
        f"Blok defensywny: A={'TAK' if defensive_home else 'NIE'}, B={'TAK' if defensive_away else 'NIE'}",
        f"Blok dominacji jednostronnej: {'TAK' if dominance and not escape else 'NIE'}",
        f"Średni Under 2,5: {under_mean:.1f}, wymagane poniżej {maximum_under25:g}",
        "Warunki: " + ", ".join(f"{name}={'TAK' if ok else 'NIE'}" for name, ok in checks.items()),
    ]
    return Recommendation(rule["id"], rule["label"], round(sum(scores) / len(scores), 1), all(checks.values()), reasons, 100.0, btts_mean, mean_threshold, "special")


def _evaluate_clean_sheets(stats: dict[str, dict[str, float]], rule: dict[str, Any]) -> Recommendation:
    condition = (rule.get("conditions") or [{}])[0]
    clean = core._find_metric(stats, "Clean sheets")
    scored = core._find_metric(stats, "Team scored")
    missing = [name for name, value in (("Clean sheets", clean), ("Team scored", scored)) if value is None]
    if missing:
        return Recommendation(rule["id"], rule["label"], 0.0, False, ["Brak danych do zabezpieczonej formuły czystego konta: " + ", ".join(missing)], 100.0 * (2 - len(missing)) / 2, mode="special")
    assert clean and scored
    th, ta = core._thresholds(condition)
    threshold = float(condition.get("minimum_clean_sheet_base", (th + ta) / 2))
    home = (float(clean["home"]) + 100 - float(scored["away"])) / 2
    away = (float(clean["away"]) + 100 - float(scored["home"])) / 2
    raw = max(home, away)
    passed = raw >= threshold
    score = round(core._strength(raw, threshold, ">="), 1)

    if passed and raw < 55.0:
        score = min(score, 104.9)
        tier = "BORDERLINE"
    elif raw < 60.0:
        tier = "FORMAL"
    else:
        tier = "STRONG"

    reasons = [
        f"Baza czystego konta A: {home:.1f}",
        f"Baza czystego konta B: {away:.1f}",
        f"Najlepsza baza {raw:.1f}, próg {threshold:g}",
        f"Poziom sygnału clean sheet: {tier} (45–54,9 graniczny; 55–59,9 formalny; 60+ mocny)",
    ]
    return Recommendation(rule["id"], rule["label"], score, passed, reasons, 100.0, raw, threshold, "special")


def _goal_data_conflicts(stats: dict[str, dict[str, float]], settings: dict[str, Any] | None = None) -> list[str]:
    settings = settings or {}
    under = core._find_metric(stats, "Under 3.5 goals")
    reported = core._find_metric(stats, "Match total goals 4+")
    exact = core._find_metric(stats, "Match total goals 4")
    if under is None or reported is None:
        return []
    conflicts = []
    for side, label in (("home", "A"), ("away", "B")):
        derived, shown = 100 - float(under[side]), float(reported[side])
        gap = abs(derived - shown)
        if gap > float(settings.get("maximum_4plus_gap", 20)):
            conflicts.append(f"strona {label}: oczekiwane 4+ {derived:.1f}%, podane {shown:.1f}%, różnica {gap:.1f} pp")
        if exact is not None and float(exact[side]) > shown:
            conflicts.append(f"strona {label}: dokładnie 4 gole {float(exact[side]):.1f}% przekracza 4+ {shown:.1f}%")
    return conflicts


def _apply_goal_data_quality(stats: dict[str, dict[str, float]], rule: dict[str, Any], result: Recommendation, settings: dict[str, Any] | None = None) -> Recommendation:
    settings = settings or {}
    rule_id = str(rule.get("id") or "")
    reasons = list(result.reasons)
    goals = core._find_metric(stats, "Goals scored per game")
    extreme = float(settings.get("extreme_goals_warning", 3.0))
    if goals is not None and max(float(goals["home"]), float(goals["away"])) >= extreme and rule_id in OVER_QUALITY_RULE_IDS:
        reasons.append(f"Ostrzeżenie: ekstremalna średnia goli ≥ {extreme:g}; możliwy wpływ wyników odstających.")
    conflicts = _goal_data_conflicts(stats, settings)
    if not conflicts:
        return replace(result, reasons=reasons)
    reasons.append("Niespójność danych bramkowych: " + " | ".join(conflicts))
    if rule_id in EXACT_TOTAL_RULE_IDS:
        return replace(result, passed=False, data_quality=0.0, reasons=reasons)
    if rule_id in TOTAL_QUALITY_RULE_IDS:
        cap = float(settings.get("total_quality_cap", settings.get("over_quality_cap", 80)))
        return replace(result, data_quality=min(result.data_quality, cap), reasons=reasons)
    return replace(result, reasons=reasons)


def evaluate_rule(stats: dict[str, dict[str, float]], rule: dict[str, Any], consistency_config: dict[str, Any] | None = None) -> Recommendation:
    rule_id = str(rule.get("id") or "")
    result = _evaluate_btts(stats, rule) if rule_id == "btts" else _evaluate_clean_sheets(stats, rule) if rule_id == "clean_sheets" else core.evaluate_rule(stats, rule)
    return _apply_goal_data_quality(stats, rule, result, consistency_config)


def analyze_match(match: dict[str, Any], config: dict[str, Any]) -> list[Recommendation]:
    recommendations = config.get("recommendations", {})
    settings = recommendations.get("goal_data_consistency", {})
    raw = [evaluate_rule(match.get("stats", {}), rule, settings) for rule in recommendations.get("rules", []) if rule.get("enabled", True)]
    return apply_final_selection(raw, config)
