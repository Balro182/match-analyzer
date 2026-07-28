from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable


OUTCOME_IDS = {"home_win", "draw", "away_win"}
HALF_OUTCOME_IDS = {"home_win_ht", "draw_ht", "away_win_ht"}
FULL_TIME_GOALS_IDS = {
    "btts", "clean_sheets", "over15", "over25", "over35",
    "under15", "under25", "under35",
}
TEAM_GOALS_IDS = {"team_scored_twice", "scored_both_halves"}
FIRST_HALF_GOALS_IDS = {"btts_ht1", "over05ht", "over15ht", "over25ht"}
TIMING_IDS = {"goal_both_halves", "btts_ht2"}
EXACT_TOTAL_IDS = {"total0", "total1", "total2", "total3", "total4", "total01", "total23", "total4plus"}
HTFT_IDS = {"win_win", "win_draw", "win_lose", "draw_win", "draw_draw", "draw_lose", "lose_win", "lose_draw", "lose_lose"}

HTFT_REQUIREMENTS = {
    "win_win": ("home_win_ht", "home_win"),
    "win_draw": ("home_win_ht", "draw"),
    "win_lose": ("home_win_ht", "away_win"),
    "draw_win": ("draw_ht", "home_win"),
    "draw_draw": ("draw_ht", "draw"),
    "draw_lose": ("draw_ht", "away_win"),
    "lose_win": ("away_win_ht", "home_win"),
    "lose_draw": ("away_win_ht", "draw"),
    "lose_lose": ("away_win_ht", "away_win"),
}

CONTRADICTION_GROUPS = (
    {"btts", "clean_sheets"},
    {"over15", "under15"},
    {"over25", "under25"},
    {"over35", "under35"},
)

ROBUSTNESS_FACTORS = {
    "over15": 1.00,
    "under35": 1.00,
    "home_win": 0.97,
    "draw": 0.97,
    "away_win": 0.97,
    "btts": 0.95,
    "clean_sheets": 0.95,
    "goal_both_halves": 0.95,
    "team_scored_twice": 0.95,
    "scored_both_halves": 0.94,
    "over25": 0.94,
    "under25": 0.94,
    "home_win_ht": 0.93,
    "draw_ht": 0.93,
    "away_win_ht": 0.93,
    "over05ht": 0.93,
    "btts_ht1": 0.90,
    "btts_ht2": 0.90,
    "over15ht": 0.90,
    "over35": 0.90,
    "under15": 0.90,
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
    tags = {
        "home_win": {"ft_home", "home_control"},
        "draw": {"ft_draw", "draw_scenario"},
        "away_win": {"ft_away", "away_control"},
        "home_win_ht": {"ht_home", "home_control"},
        "draw_ht": {"ht_draw", "draw_scenario"},
        "away_win_ht": {"ht_away", "away_control"},
        "btts": {"both_score", "open_game"},
        "clean_sheets": {"clean_sheet", "low_scoring"},
    }
    if rule_id in tags:
        return set(tags[rule_id])
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
    if rule_id in EXACT_TOTAL_IDS:
        return 0.85
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
    return max(candidates, key=lambda rec: (
        float(rec.score),
        float(rec.data_quality),
        float(rec.raw_value if rec.raw_value is not None else -1),
    ))


def _base_selection_score(rec: Any) -> float:
    quality_factor = max(0.0, min(1.0, float(rec.data_quality) / 100.0))
    return float(rec.score) * quality_factor * _robustness(str(rec.rule_id))


def _adjusted_selection_score(rec: Any, selected: list[Any], penalty_per_shared_tag: float) -> float:
    tags = _scenario_tags(str(rec.rule_id))
    shared = sum(len(tags & _scenario_tags(str(item.rule_id))) for item in selected)
    penalty = min(0.50, max(0.0, penalty_per_shared_tag) * shared)
    return _base_selection_score(rec) * (1.0 - penalty)


def _pick_independent(
    candidates: list[Any],
    limit: int,
    already_selected: list[Any],
    penalty_per_shared_tag: float,
    minimum_adjusted_score: float,
) -> list[tuple[Any, float]]:
    remaining = list(candidates)
    selected = list(already_selected)
    picks: list[tuple[Any, float]] = []
    while remaining and len(picks) < limit:
        ranked = [
            (
                _adjusted_selection_score(rec, selected, penalty_per_shared_tag),
                float(rec.score),
                float(rec.data_quality),
                float(rec.raw_value if rec.raw_value is not None else -1),
                rec,
            )
            for rec in remaining
        ]
        adjusted, _, _, _, best = max(ranked, key=lambda item: item[:4])
        if adjusted < minimum_adjusted_score:
            break
        picks.append((best, adjusted))
        selected.append(best)
        remaining = [rec for rec in remaining if str(rec.rule_id) != str(best.rule_id)]
    return picks


def _apply_half_outcome_lead_filter(
    current: list[Any],
    minimum_score: float,
    minimum_quality: float,
    minimum_lead: float,
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
    best_raw = float(ordered[0].raw_value)
    second_raw = float(ordered[1].raw_value)
    lead = best_raw - second_raw
    leaders = [rec for rec in half_outcomes if float(rec.raw_value) == best_raw]
    unique_leader_id = str(leaders[0].rule_id) if len(leaders) == 1 else None

    result = list(current)
    for index, rec in enumerate(result):
        if str(rec.rule_id) not in HALF_OUTCOME_IDS or not _candidate(rec, minimum_score, minimum_quality):
            continue
        if unique_leader_id is None:
            result[index] = _reject(rec, f"brak jednoznacznego lidera 1X2 HT; najlepsze bazy są równe ({best_raw:g}%)")
        elif str(rec.rule_id) != unique_leader_id:
            result[index] = _reject(rec, f"nie jest najwyższą surową bazą 1X2 HT; lider ma {best_raw:g}%")
        elif lead < minimum_lead:
            result[index] = _reject(rec, f"przewaga bazy 1X2 HT tylko {lead:g} pp; wymagane minimum {minimum_lead:g} pp")
    return result


def apply_final_selection(recommendations: list[Any], config: dict[str, Any]) -> list[Any]:
    """Build up to three main picks and two additional, diversified signals."""
    rec_cfg = config.get("recommendations", {})
    selection = rec_cfg.get("selection", {})
    if not bool(selection.get("enabled", True)):
        return recommendations

    minimum_score = float(rec_cfg.get("min_score", 100))
    minimum_quality = float(rec_cfg.get("min_data_quality", 100))
    max_main = max(0, int(selection.get("max_main_recommendations", 3)))
    max_additional = max(0, int(selection.get("max_additional_signals", 2)))
    max_total = max(0, int(selection.get("max_recommendations", max_main + max_additional)))
    max_additional = min(max_additional, max(0, max_total - max_main))
    max_per_category = max(1, int(selection.get("max_per_category", 1)))
    minimum_half_outcome_lead = max(0.0, float(selection.get("minimum_half_outcome_lead", 7.5)))
    independence_penalty = max(0.0, float(selection.get("independence_penalty_per_shared_tag", 0.12)))
    main_min_adjusted = max(0.0, float(selection.get("main_min_adjusted_score", 90)))
    additional_min_adjusted = max(0.0, float(selection.get("additional_min_adjusted_score", 82)))
    four_plus_min_raw = max(0.0, float(selection.get("four_plus_min_raw_value", 50)))
    four_plus_main_allowed = bool(selection.get("four_plus_main_allowed", False))

    current = _apply_half_outcome_lead_filter(
        list(recommendations), minimum_score, minimum_quality, minimum_half_outcome_lead
    )

    def index_by_id() -> dict[str, Any]:
        return {str(rec.rule_id): rec for rec in current}

    indexed = index_by_id()
    for index, rec in enumerate(current):
        requirements = HTFT_REQUIREMENTS.get(str(rec.rule_id))
        if not requirements or not _candidate(rec, minimum_score, minimum_quality):
            continue
        missing = [
            rule_id for rule_id in requirements
            if rule_id not in indexed or not _candidate(indexed[rule_id], minimum_score, minimum_quality)
        ]
        if missing:
            current[index] = _reject(rec, "HT/FT bez potwierdzenia składowych: " + ", ".join(missing))

    for group, label in ((OUTCOME_IDS, "1X2"), (HALF_OUTCOME_IDS, "wynik pierwszej połowy")):
        candidates = [rec for rec in current if rec.rule_id in group and _candidate(rec, minimum_score, minimum_quality)]
        keep = _winner(candidates)
        if keep is None:
            continue
        for index, rec in enumerate(current):
            if rec.rule_id in group and rec.rule_id != keep.rule_id and _candidate(rec, minimum_score, minimum_quality):
                current[index] = _reject(rec, f"słabszy, wzajemnie wykluczający się sygnał ({label}); wybrano {keep.label}")

    for group in CONTRADICTION_GROUPS:
        candidates = [rec for rec in current if rec.rule_id in group and _candidate(rec, minimum_score, minimum_quality)]
        keep = _winner(candidates)
        if keep is None or len(candidates) < 2:
            continue
        for index, rec in enumerate(current):
            if rec.rule_id in group and rec.rule_id != keep.rule_id and _candidate(rec, minimum_score, minimum_quality):
                current[index] = _reject(rec, f"sprzeczny z silniejszym rynkiem {keep.label}")

    for index, rec in enumerate(current):
        if str(rec.rule_id) != "total4plus" or not _candidate(rec, minimum_score, minimum_quality):
            continue
        raw = float(rec.raw_value if rec.raw_value is not None else -1)
        if raw < four_plus_min_raw:
            current[index] = _reject(
                rec,
                f"4+ to agresywny scenariusz; baza {raw:.1f}% < wymagane {four_plus_min_raw:g}%",
            )

    categories = sorted({_category(str(rec.rule_id)) for rec in current})
    for category in categories:
        candidates = [
            rec for rec in current
            if _category(str(rec.rule_id)) == category and _candidate(rec, minimum_score, minimum_quality)
        ]
        ordered = sorted(
            candidates,
            key=lambda rec: (_base_selection_score(rec), float(rec.score), float(rec.data_quality)),
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
        if four_plus_main_allowed or str(rec.rule_id) != "total4plus"
    ]
    main_picks = _pick_independent(
        main_candidates, max_main, [], independence_penalty, main_min_adjusted
    )
    main_ids = {str(rec.rule_id) for rec, _ in main_picks}
    remaining = [rec for rec in surviving if str(rec.rule_id) not in main_ids]
    additional_picks = _pick_independent(
        remaining,
        max_additional,
        [rec for rec, _ in main_picks],
        independence_penalty,
        additional_min_adjusted,
    )
    additional_ids = {str(rec.rule_id) for rec, _ in additional_picks}
    score_by_id = {
        str(rec.rule_id): adjusted
        for rec, adjusted in [*main_picks, *additional_picks]
    }

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
            current[index] = _reject(
                rec,
                f"poza końcową listą: maks. {max_main} główne + {max_additional} dodatkowe, z karą za korelację",
            )

    return current
