from __future__ import annotations

from typing import Any

from decisions import is_recommended
from evaluation import (
    classify_outcome,
    quality_bucket,
    recommendation_status,
    score_bucket,
)


def validate_scoreline(home: int, away: int, home_ht: int | None = None, away_ht: int | None = None) -> tuple[bool, str]:
    values = [home, away]
    if home_ht is not None:
        values.append(home_ht)
    if away_ht is not None:
        values.append(away_ht)
    if any(value < 0 for value in values):
        return False, "Liczba goli nie może być ujemna."
    if (home_ht is None) != (away_ht is None):
        return False, "Wynik do przerwy musi zawierać gole obu drużyn."
    if home_ht is not None and away_ht is not None and (home_ht > home or away_ht > away):
        return False, "Wynik do przerwy nie może być wyższy niż wynik końcowy."
    return True, ""


def _state(home: int, away: int) -> str:
    if home > away:
        return "A"
    if home < away:
        return "B"
    return "X"


def _actual_by_rule(
    rule_id: str,
    home: int,
    away: int,
    home_ht: int | None,
    away_ht: int | None,
) -> bool | None:
    total = home + away
    btts = home > 0 and away > 0

    if rule_id in {"avg_scored", "avg_conceded"}:
        return None
    if rule_id == "clean_sheets":
        return home == 0 or away == 0
    if rule_id == "team_scored":
        return btts
    if rule_id == "team_scored_twice":
        return home >= 2 or away >= 2

    if rule_id in {"scored_both_halves", "goal_both_halves"}:
        if home_ht is None or away_ht is None:
            return None
        home_second = home - home_ht
        away_second = away - away_ht
        if rule_id == "scored_both_halves":
            return (home_ht > 0 and home_second > 0) or (away_ht > 0 and away_second > 0)
        return (home_ht + away_ht > 0) and (home_second + away_second > 0)

    direct = {
        "home_win": home > away,
        "draw": home == away,
        "away_win": away > home,
        "win_over15": home > away and total > 1,
        "lose_over15": away > home and total > 1,
        "btts": btts,
        "btts_over15": btts and total > 1,
        "btts_over25": btts and total > 2,
        "home_win_btts": home > away and btts,
        "draw_btts": home == away and btts,
        "away_win_btts": away > home and btts,
        "total0": total == 0,
        "total1": total == 1,
        "total2": total == 2,
        "total3": total == 3,
        "total4": total == 4,
        "total01": total <= 1,
        "total23": 2 <= total <= 3,
        "total4plus": total >= 4,
        "over15": total > 1,
        "over25": total > 2,
        "over35": total > 3,
        "under15": total < 2,
        "under25": total < 3,
        "under35": total < 4,
    }
    if rule_id in direct:
        return direct[rule_id]

    if home_ht is None or away_ht is None:
        return None

    ht_total = home_ht + away_ht
    half_time = {
        "home_win_ht": home_ht > away_ht,
        "draw_ht": home_ht == away_ht,
        "away_win_ht": away_ht > home_ht,
        "btts_ht1": home_ht > 0 and away_ht > 0,
        "btts_ht2": (home - home_ht > 0) and (away - away_ht > 0),
        "over05ht": ht_total > 0,
        "over15ht": ht_total > 1,
        "over25ht": ht_total > 2,
    }
    if rule_id in half_time:
        return half_time[rule_id]

    htft_map = {
        "win_win": ("A", "A"),
        "win_draw": ("A", "X"),
        "win_lose": ("A", "B"),
        "draw_win": ("X", "A"),
        "draw_draw": ("X", "X"),
        "draw_lose": ("X", "B"),
        "lose_win": ("B", "A"),
        "lose_draw": ("B", "X"),
        "lose_lose": ("B", "B"),
    }
    expected = htft_map.get(rule_id)
    if expected is not None:
        return (_state(home_ht, away_ht), _state(home, away)) == expected
    return None


def settle_recommendations(
    recommendations: list[dict[str, Any]],
    home: int,
    away: int,
    home_ht: int | None = None,
    away_ht: int | None = None,
    minimum_score: float = 100.0,
    minimum_quality: float = 100.0,
    require_passed: bool = True,
) -> list[dict[str, Any]]:
    valid, message = validate_scoreline(home, away, home_ht, away_ht)
    if not valid:
        raise ValueError(message)

    rows: list[dict[str, Any]] = []
    for recommendation in recommendations:
        predicted = is_recommended(
            recommendation,
            minimum_score=minimum_score,
            minimum_quality=minimum_quality,
            require_passed=require_passed,
        )
        rule_id = str(recommendation.get("rule_id") or "")
        actual = _actual_by_rule(rule_id, home, away, home_ht, away_ht)
        status = str(recommendation.get("status") or recommendation_status(recommendation))
        outcome_class = classify_outcome(predicted, actual)

        if actual is None:
            result = "brak danych"
        elif not predicted:
            result = "brak typu"
        else:
            result = "trafiona" if actual else "nietrafiona"

        rows.append(
            {
                "rule_id": rule_id,
                "label": recommendation.get("label"),
                "score": recommendation.get("score"),
                "score_bucket": recommendation.get("score_bucket") or score_bucket(recommendation.get("score")),
                "data_quality": recommendation.get("data_quality"),
                "quality_bucket": recommendation.get("quality_bucket") or quality_bucket(recommendation.get("data_quality")),
                "status": status,
                "eligible": recommendation.get("eligible"),
                "predicted": predicted,
                "actual": actual,
                "result": result,
                "outcome_class": outcome_class,
            }
        )
    return rows
