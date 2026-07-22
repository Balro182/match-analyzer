from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable


OUTCOME_IDS = {"home_win", "draw", "away_win"}
HALF_OUTCOME_IDS = {"home_win_ht", "draw_ht", "away_win_ht"}
FULL_TIME_GOALS_IDS = {
    "btts", "clean_sheets", "team_scored_twice", "over15", "over25", "over35",
    "under15", "under25", "under35",
}
FIRST_HALF_GOALS_IDS = {"btts_ht1", "over05ht", "over15ht", "over25ht"}
TIMING_IDS = {"scored_both_halves", "goal_both_halves", "btts_ht2"}
EXACT_TOTAL_IDS = {"total0", "total1", "total2", "total3", "total4", "total01", "total23", "total4plus"}
HTFT_IDS = {"win_win", "win_draw", "win_lose", "draw_win", "draw_draw", "draw_lose", "lose_win", "lose_draw", "lose_lose"}

# Każdy rynek HT/FT musi być potwierdzony przez niezależny rynek pierwszej połowy
# i niezależny rynek wyniku końcowego. Zapobiega to typom takim jak X/B przy
# jednoczesnym odrzuceniu zwycięstwa gościa.
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


def _category(rule_id: str) -> str:
    if rule_id in OUTCOME_IDS:
        return "outcome"
    if rule_id in HALF_OUTCOME_IDS:
        return "half_outcome"
    if rule_id in FULL_TIME_GOALS_IDS:
        return "full_time_goals"
    if rule_id in FIRST_HALF_GOALS_IDS:
        return "first_half_goals"
    if rule_id in TIMING_IDS:
        return "timing"
    if rule_id in EXACT_TOTAL_IDS:
        return "exact_total"
    if rule_id in HTFT_IDS:
        return "htft"
    return "other"


def _candidate(rec: Any, minimum_score: float, minimum_quality: float) -> bool:
    return (
        bool(rec.passed)
        and float(rec.score) >= minimum_score
        and float(rec.data_quality) >= minimum_quality
    )


def _reject(rec: Any, reason: str) -> Any:
    return replace(rec, passed=False, reasons=[*rec.reasons, f"Selekcja końcowa: {reason}"])


def _winner(items: Iterable[Any]) -> Any | None:
    candidates = list(items)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda rec: (
            float(rec.score),
            float(rec.data_quality),
            float(rec.raw_value if rec.raw_value is not None else -1),
        ),
    )


def apply_final_selection(recommendations: list[Any], config: dict[str, Any]) -> list[Any]:
    """Turns independent rule hits into a small, coherent final betting shortlist.

    Raw values and scores remain available, but ``passed`` after this function means
    that the market survived cross-market consistency, contradiction checks,
    category competition and the final shortlist limit.
    """
    rec_cfg = config.get("recommendations", {})
    selection = rec_cfg.get("selection", {})
    if not bool(selection.get("enabled", True)):
        return recommendations

    minimum_score = float(rec_cfg.get("min_score", 100))
    minimum_quality = float(rec_cfg.get("min_data_quality", 100))
    max_recommendations = max(1, int(selection.get("max_recommendations", 3)))
    max_per_category = max(1, int(selection.get("max_per_category", 1)))

    current = list(recommendations)

    def index_by_id() -> dict[str, Any]:
        return {str(rec.rule_id): rec for rec in current}

    # 1. HT/FT: wymagamy niezależnego potwierdzenia obu składowych.
    indexed = index_by_id()
    for index, rec in enumerate(current):
        requirements = HTFT_REQUIREMENTS.get(str(rec.rule_id))
        if not requirements or not _candidate(rec, minimum_score, minimum_quality):
            continue
        missing = [rule_id for rule_id in requirements if rule_id not in indexed or not _candidate(indexed[rule_id], minimum_score, minimum_quality)]
        if missing:
            current[index] = _reject(rec, "HT/FT bez potwierdzenia składowych: " + ", ".join(missing))

    # 2. Rynki wzajemnie wykluczające się: zostaje tylko najsilniejszy sygnał.
    for group, label in ((OUTCOME_IDS, "1X2"), (HALF_OUTCOME_IDS, "wynik pierwszej połowy")):
        candidates = [rec for rec in current if rec.rule_id in group and _candidate(rec, minimum_score, minimum_quality)]
        keep = _winner(candidates)
        if keep is None:
            continue
        for index, rec in enumerate(current):
            if rec.rule_id in group and rec.rule_id != keep.rule_id and _candidate(rec, minimum_score, minimum_quality):
                current[index] = _reject(rec, f"słabszy, wzajemnie wykluczający się sygnał ({label}); wybrano {keep.label}")

    # 3. Jawne sprzeczności, np. BTTS i clean sheet lub Over i Under tej samej linii.
    for group in CONTRADICTION_GROUPS:
        candidates = [rec for rec in current if rec.rule_id in group and _candidate(rec, minimum_score, minimum_quality)]
        keep = _winner(candidates)
        if keep is None or len(candidates) < 2:
            continue
        for index, rec in enumerate(current):
            if rec.rule_id in group and rec.rule_id != keep.rule_id and _candidate(rec, minimum_score, minimum_quality):
                current[index] = _reject(rec, f"sprzeczny z silniejszym rynkiem {keep.label}")

    # 4. W jednej kategorii nie pokazujemy wielu silnie skorelowanych odmian tego samego pomysłu.
    categories = sorted({_category(str(rec.rule_id)) for rec in current})
    for category in categories:
        candidates = [rec for rec in current if _category(str(rec.rule_id)) == category and _candidate(rec, minimum_score, minimum_quality)]
        ordered = sorted(candidates, key=lambda rec: (float(rec.score), float(rec.data_quality)), reverse=True)
        keep_ids = {str(rec.rule_id) for rec in ordered[:max_per_category]}
        for index, rec in enumerate(current):
            if _category(str(rec.rule_id)) == category and _candidate(rec, minimum_score, minimum_quality) and str(rec.rule_id) not in keep_ids:
                current[index] = _reject(rec, f"słabszy, skorelowany rynek w kategorii {category}")

    # 5. Końcowa krótka lista. Wyżej stawiamy score, potem jakość i surową wartość.
    surviving = [rec for rec in current if _candidate(rec, minimum_score, minimum_quality)]
    ordered = sorted(
        surviving,
        key=lambda rec: (
            float(rec.score),
            float(rec.data_quality),
            float(rec.raw_value if rec.raw_value is not None else -1),
        ),
        reverse=True,
    )
    keep_ids = {str(rec.rule_id) for rec in ordered[:max_recommendations]}
    for index, rec in enumerate(current):
        if _candidate(rec, minimum_score, minimum_quality) and str(rec.rule_id) not in keep_ids:
            current[index] = _reject(rec, f"poza końcowym TOP {max_recommendations}")

    return current
