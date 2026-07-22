from engine_core import Recommendation
from selection import apply_final_selection


def rec(rule_id: str, score: float, passed: bool = True, quality: float = 100.0) -> Recommendation:
    return Recommendation(rule_id, rule_id, score, passed, [], quality, score, 100.0, "special")


def config(max_recommendations: int = 3) -> dict:
    return {
        "recommendations": {
            "min_score": 100,
            "min_data_quality": 100,
            "selection": {
                "enabled": True,
                "max_recommendations": max_recommendations,
                "max_per_category": 1,
            },
        }
    }


def by_id(items: list[Recommendation]) -> dict[str, Recommendation]:
    return {item.rule_id: item for item in items}


def test_htft_requires_both_independent_components() -> None:
    result = by_id(
        apply_final_selection(
            [
                rec("home_win", 108),
                rec("home_win_ht", 95, passed=False),
                rec("draw_ht", 102),
                rec("away_win", 40, passed=False),
                rec("win_win", 120),
                rec("draw_lose", 150),
            ],
            config(),
        )
    )

    assert result["win_win"].passed is False
    assert result["draw_lose"].passed is False
    assert any("HT/FT bez potwierdzenia" in reason for reason in result["win_win"].reasons)
    assert any("HT/FT bez potwierdzenia" in reason for reason in result["draw_lose"].reasons)


def test_only_strongest_mutually_exclusive_outcome_survives() -> None:
    result = by_id(
        apply_final_selection(
            [rec("home_win", 110), rec("draw", 104), rec("away_win", 101)],
            config(),
        )
    )

    assert result["home_win"].passed is True
    assert result["draw"].passed is False
    assert result["away_win"].passed is False


def test_correlated_goal_markets_are_reduced_to_one() -> None:
    result = by_id(
        apply_final_selection(
            [rec("over15", 120), rec("over25", 104), rec("under35", 103)],
            config(),
        )
    )

    assert result["over15"].passed is True
    assert result["over25"].passed is False
    assert result["under35"].passed is False


def test_final_shortlist_is_limited() -> None:
    result = apply_final_selection(
        [
            rec("home_win", 115),
            rec("over15", 120),
            rec("over05ht", 110),
            rec("goal_both_halves", 105),
            rec("total3", 104),
        ],
        config(max_recommendations=3),
    )

    assert sum(item.passed for item in result) == 3
