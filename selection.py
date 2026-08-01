from __future__ import annotations

from dataclasses import replace
from itertools import combinations
from typing import Any, Iterable

OUTCOME_IDS = {"home_win", "draw", "away_win"}
HALF_OUTCOME_IDS = {"home_win_ht", "draw_ht", "away_win_ht"}
FULL_TIME_GOALS_IDS = {
    "btts", "btts_no", "clean_sheets", "over15", "over25", "over35",
    "under15", "under25", "under35",
}
TEAM_GOALS_IDS = {"team_scored_twice", "scored_both_halves"}
FIRST_HALF_GOALS_IDS = {"btts_ht1", "over05ht", "over15ht", "over25ht"}
TIMING_IDS = {"goal_both_halves", "btts_ht2"}
EXACT_TOTAL_IDS = {"total0", "total1", "total2", "total3", "total4", "total01", "total23", "total4plus"}
POINT_TOTAL_IDS = {"total0", "total1", "total2", "total3", "total4"}
HTFT_IDS = {"win_win", "win_draw", "win_lose", "draw_win", "draw_draw", "draw_lose", "lose_win", "lose_draw", "lose_lose"}
DRAW_FT_IDS = {"draw", "win_draw", "draw_draw", "lose_draw"}

HTFT_REQUIREMENTS = {
    "win_win": ("home_win_ht", "home_win"), "win_draw": ("home_win_ht", "draw"),
    "win_lose": ("home_win_ht", "away_win"), "draw_win": ("draw_ht", "home_win"),
    "draw_draw": ("draw_ht", "draw"), "draw_lose": ("draw_ht", "away_win"),
    "lose_win": ("away_win_ht", "home_win"), "lose_draw": ("away_win_ht", "draw"),
    "lose_lose": ("away_win_ht", "away_win"),
}

CONTRADICTION_GROUPS = (
    {"btts", "btts_no", "clean_sheets"}, {"over15", "under15"},
    {"over25", "under25"}, {"over35", "under35"},
)

ROBUSTNESS_FACTORS = {
    "over15": 1.00, "under35": 1.00,
    "home_win": 0.97, "draw": 0.97, "away_win": 0.97,
    "btts": 0.94, "btts_no": 0.96, "clean_sheets": 0.95,
    "goal_both_halves": 0.88, "team_scored_twice": 0.90,
    "scored_both_halves": 0.88, "over25": 0.94, "under25": 0.94,
    "home_win_ht": 0.93, "draw_ht": 0.93, "away_win_ht": 0.93,
    "over05ht": 0.93, "btts_ht1": 0.88, "btts_ht2": 0.86,
    "over15ht": 0.90, "over35": 0.90, "under15": 0.90,
}

HTFT_TAGS = {
    "win_win": {"ht_home", "ft_home", "home_control"},
    "win_draw": {"ht_home", "ft_draw", "home_control"},
    "win_lose": {"ht_home", "ft_away", "turnaround"},
    "draw_win": {"ht_draw", "ft_home", "home_control"},
    "draw_draw": {"ht_draw", "ft_draw", "draw_scenario"},
    "draw_lose": {"ht_draw", "ft_away", "away_control"},
    "lose_win": {"ht_away", "ft_home", "turnaround"},
    "lose_draw": {"ht_away", "ft_draw", "away_control"},
    "lose_lose": {"ht_away", "ft_away", "away_control"},
}


def _category(rule_id: str) -> str:
    if rule_id in OUTCOME_IDS:
        return "outcome"
    if rule_id in HALF_OUTCOME_IDS:
        return "half_outcome"
    if rule_id in FULL_TIME_GOALS_IDS:
        return "full_time_goals"
    if rule_id in TEAM_GOALS_IDS:
        return "team_goals"
    if rule_id in FIRST_HALF_GOALS_IDS:
        return "first_half_goals"
    if rule_id in TIMING_IDS:
        return "timing"
    if rule_id in EXACT_TOTAL_IDS:
        return "exact_total"
    if rule_id in HTFT_IDS:
        return "htft"
    return "other"


def _scenario_tags(rule_id: str) -> set[str]:
    direct = {
        "home_win": {"ft_home", "home_control"}, "draw": {"ft_draw", "draw_scenario"},
        "away_win": {"ft_away", "away_control"}, "home_win_ht": {"ht_home", "home_control"},
        "draw_ht": {"ht_draw", "draw_scenario"}, "away_win_ht": {"ht_away", "away_control"},
        "btts": {"both_score", "open_game"}, "btts_no": {"not_both_score", "low_scoring"},
        "clean_sheets": {"clean_sheet", "not_both_score", "low_scoring"},
    }
    if rule_id in direct:
        return set(direct[rule_id])
    if rule_id in HTFT_TAGS:
        return set(HTFT_TAGS[rule_id])
    if rule_id in {"over15", "over25", "over35", "team_scored_twice"}:
        return {"high_scoring", "open_game"}
    if rule_id in {"under15", "under25", "under35"}:
        return {"low_scoring"}
    if rule_id in {"goal_both_halves", "scored_both_halves"}:
        return {"goals_both_halves", "open_game"}
    if rule_id in {"btts_ht1", "btts_ht2"}:
        return {"both_score", "half_goals", "open_game"}
    if rule_id in {"over05ht", "over15ht", "over25ht"}:
        return {"half_goals", "high_scoring"}
    if rule_id in {"total0", "total1", "total01"}:
        return {"low_scoring", "exact_total"}
    if rule_id in {"total2", "total3", "total23"}:
        return {"medium_total", "exact_total"}
    if rule_id in {"total4", "total4plus"}:
        return {"high_scoring", "exact_total", "open_game"}
    return {_category(rule_id)}


def _robustness(rule_id: str) -> float:
    if rule_id in HTFT_IDS:
        return 0.88
    if rule_id in POINT_TOTAL_IDS:
        return 0.78
    if rule_id in {"total01", "total23"}:
        return 0.90
    if rule_id == "total4plus":
        return 0.80
    if rule_id == "over25ht":
        return 0.87
    return ROBUSTNESS_FACTORS.get(rule_id, 0.92)


def _candidate(rec: Any, minimum_score: float, minimum_quality: float) -> bool:
    return bool(rec.passed) and float(rec.score) >= minimum_score and float(rec.data_quality) >= minimum_quality


def _reject(rec: Any, reason: str) -> Any:
    return replace(rec, passed=False, reasons=[*rec.reasons, f"Selekcja końcowa: {reason}"])


def _winner(items: Iterable[Any]) -> Any | None:
    candidates = list(items)
    if not candidates:
        return None
    return max(candidates, key=lambda rec: (float(rec.score), float(rec.data_quality), float(rec.raw_value or -1)))


def _threshold_margin(rec: Any) -> float:
    if rec.raw_value is None or rec.threshold is None:
        return 999.0
    return float(rec.raw_value) - float(rec.threshold)


def _base_selection_score(rec: Any, boundary_margin: float = 0.0, boundary_penalty: float = 0.0) -> float:
    quality_factor = max(0.0, min(1.0, float(rec.data_quality) / 100.0))
    score = float(rec.score) * quality_factor * _robustness(str(rec.rule_id))
    if _threshold_margin(rec) <= boundary_margin:
        score *= max(0.0, 1.0 - boundary_penalty)
    return score


def _hard_conflict(left_id: str, right_id: str) -> bool:
    pair = {left_id, right_id}
    if any(pair <= group for group in CONTRADICTION_GROUPS):
        return True
    if left_id in OUTCOME_IDS and right_id in OUTCOME_IDS and left_id != right_id:
        return True
    if left_id in HALF_OUTCOME_IDS and right_id in HALF_OUTCOME_IDS and left_id != right_id:
        return True
    exact_points = {"total0", "total1", "total2", "total3", "total4"}
    if left_id in exact_points and right_id in exact_points and left_id != right_id:
        return True
    zero_conflicts = {"btts", "team_scored_twice", "scored_both_halves", "goal_both_halves", "btts_ht1", "btts_ht2", "over05ht", "over15ht", "over25ht", "over15", "over25", "over35"}
    if "total0" in pair and bool(pair & zero_conflicts):
        return True
    one_conflicts = {"btts", "team_scored_twice", "scored_both_halves", "goal_both_halves", "btts_ht1", "btts_ht2", "over15ht", "over25ht", "over15", "over25", "over35"}
    if "total1" in pair and bool(pair & one_conflicts):
        return True
    if "total2" in pair and bool(pair & {"over25", "over35"}):
        return True
    if "total3" in pair and bool(pair & DRAW_FT_IDS):
        return True
    if "total1" in pair and bool(pair & DRAW_FT_IDS):
        return True
    if "total0" in pair and bool(pair & {"home_win", "away_win", "win_win", "win_lose", "draw_win", "draw_lose", "lose_win", "lose_lose"}):
        return True
    return False


def _compatible(candidate: Any, selected: list[Any]) -> bool:
    return not any(_hard_conflict(str(candidate.rule_id), str(item.rule_id)) for item in selected)


def _adjusted_selection_score(
    rec: Any,
    selected: list[Any],
    penalty_per_shared_tag: float,
    boundary_margin: float,
    boundary_penalty: float,
) -> float:
    if not _compatible(rec, selected):
        return -1.0
    tags = _scenario_tags(str(rec.rule_id))
    shared = sum(len(tags & _scenario_tags(str(item.rule_id))) for item in selected)
    penalty = min(0.50, max(0.0, penalty_per_shared_tag) * shared)
    return _base_selection_score(rec, boundary_margin, boundary_penalty) * (1.0 - penalty)


def _best_compatible_set(
    candidates: list[Any],
    limit: int,
    already_selected: list[Any],
    penalty_per_shared_tag: float,
    minimum_adjusted_score: float,
    boundary_margin: float,
    boundary_penalty: float,
) -> list[tuple[Any, float]]:
    eligible = [rec for rec in candidates if _compatible(rec, already_selected)]
    best: list[tuple[Any, float]] = []
    best_total = -1.0
    for size in range(1, min(limit, len(eligible)) + 1):
        for combo in combinations(eligible, size):
            chosen = list(already_selected)
            scored: list[tuple[Any, float]] = []
            valid = True
            for rec in sorted(combo, key=lambda item: _base_selection_score(item, boundary_margin, boundary_penalty), reverse=True):
                adjusted = _adjusted_selection_score(rec, chosen, penalty_per_shared_tag, boundary_margin, boundary_penalty)
                if adjusted < minimum_adjusted_score:
                    valid = False
                    break
                scored.append((rec, adjusted))
                chosen.append(rec)
            if valid:
                total = sum(value for _, value in scored)
                if total > best_total:
                    best_total, best = total, scored
    return best


def _apply_half_outcome_lead_filter(
    current: list[Any], minimum_score: float, minimum_quality: float, minimum_lead: float
) -> list[Any]:
    half_outcomes = [
        rec for rec in current
        if str(rec.rule_id) in HALF_OUTCOME_IDS
        and rec.raw_value is not None
        and float(rec.data_quality) >= minimum_quality
    ]
    if len(half_outcomes) < 2:
        return current
    ordered = sorted(half_outcomes, key=lambda rec: float(rec.raw_value), reverse=True)
    best_raw, second_raw = float(ordered[0].raw_value), float(ordered[1].raw_value)
    leaders = [rec for rec in half_outcomes if float(rec.raw_value) == best_raw]
    unique = str(leaders[0].rule_id) if len(leaders) == 1 else None
    result = list(current)
    for index, rec in enumerate(result):
        if str(rec.rule_id) not in HALF_OUTCOME_IDS or not _candidate(rec, minimum_score, minimum_quality):
            continue
        if unique is None:
            result[index] = _reject(rec, f"brak jednoznacznego lidera 1X2 HT; najlepsze bazy są równe ({best_raw:g}%)")
        elif str(rec.rule_id) != unique:
            result[index] = _reject(rec, f"nie jest najwyższą surową bazą 1X2 HT; lider ma {best_raw:g}%")
        elif best_raw - second_raw < minimum_lead:
            result[index] = _reject(rec, f"przewaga bazy 1X2 HT tylko {best_raw-second_raw:g} pp; wymagane minimum {minimum_lead:g} pp")
    return result


def apply_final_selection(recommendations: list[Any], config: dict[str, Any]) -> list[Any]:
    rec_cfg = config.get("recommendations", {})
    selection = rec_cfg.get("selection", {})
    if not bool(selection.get("enabled", True)):
        return recommendations

    minimum_score = float(rec_cfg.get("min_score", 100))
    minimum_quality = float(rec_cfg.get("min_data_quality", 100))
    max_main = max(0, int(selection.get("max_main_recommendations", 3)))
    max_additional = max(0, int(selection.get("max_additional_signals", 2)))
    max_total = max(0, int(selection.get("max_recommendations", max_main + max_additional)))
    max_additional = min(max_additional, max(0, max_total-max_main))
    max_per_category = max(1, int(selection.get("max_per_category", 1)))
    minimum_half_outcome_lead = max(0.0, float(selection.get("minimum_half_outcome_lead", 7.5)))
    independence_penalty = max(0.0, float(selection.get("independence_penalty_per_shared_tag", 0.12)))
    main_min_adjusted = max(0.0, float(selection.get("main_min_adjusted_score", 90)))
    additional_min_adjusted = max(0.0, float(selection.get("additional_min_adjusted_score", 82)))
    four_plus_min_raw = max(0.0, float(selection.get("four_plus_min_raw_value", 50)))
    four_plus_main_allowed = bool(selection.get("four_plus_main_allowed", False))
    exact_totals_main_allowed = bool(selection.get("exact_totals_main_allowed", False))
    boundary_margin = max(0.0, float(selection.get("boundary_margin_pp", 2.5)))
    boundary_penalty = max(0.0, float(selection.get("boundary_penalty", 0.12)))

    current = _apply_half_outcome_lead_filter(
        list(recommendations), minimum_score, minimum_quality, minimum_half_outcome_lead
    )
    indexed = {str(rec.rule_id): rec for rec in current}
    for index, rec in enumerate(current):
        requirements = HTFT_REQUIREMENTS.get(str(rec.rule_id))
        if requirements and _candidate(rec, minimum_score, minimum_quality):
            missing = [
                rule_id for rule_id in requirements
                if rule_id not in indexed or not _candidate(indexed[rule_id], minimum_score, minimum_quality)
            ]
            if missing:
                current[index] = _reject(rec, "HT/FT bez potwierdzenia składowych: " + ", ".join(missing))

    for group, label in ((OUTCOME_IDS, "1X2"), (HALF_OUTCOME_IDS, "wynik pierwszej połowy")):
        candidates = [rec for rec in current if rec.rule_id in group and _candidate(rec, minimum_score, minimum_quality)]
        keep = _winner(candidates)
        if keep:
            for index, rec in enumerate(current):
                if rec.rule_id in group and rec.rule_id != keep.rule_id and _candidate(rec, minimum_score, minimum_quality):
                    current[index] = _reject(rec, f"słabszy, wzajemnie wykluczający się sygnał ({label}); wybrano {keep.label}")

    for group in CONTRADICTION_GROUPS:
        candidates = [rec for rec in current if rec.rule_id in group and _candidate(rec, minimum_score, minimum_quality)]
        keep = _winner(candidates)
        if keep and len(candidates) > 1:
            for index, rec in enumerate(current):
                if rec.rule_id in group and rec.rule_id != keep.rule_id and _candidate(rec, minimum_score, minimum_quality):
                    current[index] = _reject(rec, f"sprzeczny z silniejszym rynkiem {keep.label}")

    for index, rec in enumerate(current):
        if str(rec.rule_id) == "total4plus" and _candidate(rec, minimum_score, minimum_quality):
            raw = float(rec.raw_value or -1)
            if raw < four_plus_min_raw:
                current[index] = _reject(rec, f"4+ to agresywny scenariusz; baza {raw:.1f}% < wymagane {four_plus_min_raw:g}%")

    for category in sorted({_category(str(rec.rule_id)) for rec in current}):
        candidates = [
            rec for rec in current
            if _category(str(rec.rule_id)) == category and _candidate(rec, minimum_score, minimum_quality)
        ]
        ordered = sorted(
            candidates,
            key=lambda rec: (_base_selection_score(rec, boundary_margin, boundary_penalty), float(rec.score), float(rec.data_quality)),
            reverse=True,
        )
        keep_ids = {str(rec.rule_id) for rec in ordered[:max_per_category]}
        for index, rec in enumerate(current):
            if (
                _category(str(rec.rule_id)) == category
                and _candidate(rec, minimum_score, minimum_quality)
                and str(rec.rule_id) not in keep_ids
            ):
                current[index] = _reject(rec, f"słabszy, skorelowany rynek w kategorii {category}")

    surviving = [rec for rec in current if _candidate(rec, minimum_score, minimum_quality)]
    main_candidates = [
        rec for rec in surviving
        if (four_plus_main_allowed or str(rec.rule_id) != "total4plus")
        and (exact_totals_main_allowed or str(rec.rule_id) not in POINT_TOTAL_IDS)
    ]
    main_picks = _best_compatible_set(
        main_candidates, max_main, [], independence_penalty,
        main_min_adjusted, boundary_margin, boundary_penalty,
    )
    main_ids = {str(rec.rule_id) for rec, _ in main_picks}
    remaining = [rec for rec in surviving if str(rec.rule_id) not in main_ids]
    additional_picks = _best_compatible_set(
        remaining, max_additional, [rec for rec, _ in main_picks], independence_penalty,
        additional_min_adjusted, boundary_margin, boundary_penalty,
    )
    additional_ids = {str(rec.rule_id) for rec, _ in additional_picks}
    score_by_id = {str(rec.rule_id): score for rec, score in [*main_picks, *additional_picks]}
    selected = [rec for rec, _ in [*main_picks, *additional_picks]]

    for index, rec in enumerate(current):
        rule_id = str(rec.rule_id)
        if not _candidate(rec, minimum_score, minimum_quality):
            continue
        if rule_id in main_ids:
            current[index] = replace(
                rec,
                reasons=[*rec.reasons, f"Poziom selekcji: główny typ; selection score {score_by_id[rule_id]:.1f}"],
            )
        elif rule_id in additional_ids:
            suffix = "; agresywny rynek 4+" if rule_id == "total4plus" else ""
            current[index] = replace(
                rec,
                reasons=[*rec.reasons, f"Poziom selekcji: dodatkowy sygnał; selection score {score_by_id[rule_id]:.1f}{suffix}"],
            )
        else:
            conflict = next((item for item in selected if _hard_conflict(rule_id, str(item.rule_id))), None)
            reason = (
                f"twardy konflikt logiczny z {conflict.label}"
                if conflict
                else f"poza najlepszym kompatybilnym zestawem: maks. {max_main} główne + {max_additional} dodatkowe"
            )
            current[index] = _reject(rec, reason)

    return current
