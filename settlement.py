from __future__ import annotations

from typing import Any


def _side_states(home: int, away: int) -> tuple[str, str]:
    if home > away:
        return "win", "lose"
    if home < away:
        return "lose", "win"
    return "draw", "draw"


def _actual_by_rule(
    rule_id: str,
    home: int,
    away: int,
    home_ht: int | None,
    away_ht: int | None,
) -> bool | None:
    total = home + away
    btts = home > 0 and away > 0
    home_ft, away_ft = _side_states(home, away)

    # Wskaźniki opisowe nie są samodzielnymi zdarzeniami meczowymi.
    if rule_id in {"avg_scored", "avg_conceded"}:
        return None

    if rule_id == "clean_sheets":
        return home == 0 or away == 0
    if rule_id == "team_scored":
        return btts
    if rule_id == "team_scored_twice":
        return home >= 2 and away >= 2

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
        "win_over15": home != away and total > 1,
        "lose_over15": home != away and total > 1,
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
    home_ht_state, away_ht_state = _side_states(home_ht, away_ht)
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

    # Ogólne HT/FT są spełnione, gdy układ wystąpił z perspektywy jednej z drużyn.
    htft_map = {
        "win_win": ("win", "win"),
        "win_draw": ("win", "draw"),
        "win_lose": ("win", "lose"),
        "draw_win": ("draw", "win"),
        "draw_draw": ("draw", "draw"),
        "draw_lose": ("draw", "lose"),
        "lose_win": ("lose", "win"),
        "lose_draw": ("lose", "draw"),
        "lose_lose": ("lose", "lose"),
    }
    expected = htft_map.get(rule_id)
    if expected is not None:
        return (home_ht_state, home_ft) == expected or (away_ht_state, away_ft) == expected

    return None


def settle_recommendations(
    recommendations: list[dict[str, Any]],
    home: int,
    away: int,
    home_ht: int | None = None,
    away_ht: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for recommendation in recommendations:
        predicted = bool(recommendation.get("passed"))
        rule_id = str(recommendation.get("rule_id") or "")
        actual = _actual_by_rule(rule_id, home, away, home_ht, away_ht)

        if actual is None:
            result = "brak danych"
        elif not predicted:
            # FALSE nie jest typem przeciwnym. Oznacza tylko, że aplikacja nie poleciła rynku.
            result = "brak typu"
        else:
            result = "trafiona" if actual else "nietrafiona"

        rows.append(
            {
                "rule_id": rule_id,
                "label": recommendation.get("label"),
                "score": recommendation.get("score"),
                "predicted": predicted,
                "actual": actual,
                "result": result,
            }
        )
    return rows
