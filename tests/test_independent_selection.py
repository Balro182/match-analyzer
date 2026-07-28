from engine_core import Recommendation
from selection import apply_final_selection


def rec(rule_id: str, score: float, raw_value: float = 70.0) -> Recommendation:
    return Recommendation(
        rule_id=rule_id,
        label=rule_id,
        score=score,
        passed=True,
        reasons=[],
        data_quality=100.0,
        raw_value=raw_value,
        threshold=50.0,
        mode="test",
    )


def config(**selection_overrides):
    selection = {
        "enabled": True,
        "max_recommendations": 5,
        "max_main_recommendations": 3,
        "max_additional_signals": 2,
        "max_per_category": 1,
        "minimum_half_outcome_lead": 0,
        "independence_penalty_per_shared_tag": 0.12,
        "main_min_adjusted_score": 0,
        "additional_min_adjusted_score": 0,
    }
    selection.update(selection_overrides)
    return {
        "recommendations": {
            "min_score": 100,
            "min_data_quality": 100,
            "selection": selection,
        }
    }


def level(item: Recommendation) -> str:
    return " | ".join(item.reasons)


def test_selection_returns_at_most_three_main_and_two_additional():
    items = [
        rec("over15", 135),
        rec("home_win", 132),
        rec("goal_both_halves", 130),
        rec("team_scored_twice", 128),
        rec("over05ht", 126),
        rec("total4", 124),
    ]

    result = apply_final_selection(items, config())
    selected = [item for item in result if item.passed]
    main = [item for item in selected if "główny typ" in level(item)]
    additional = [item for item in selected if "dodatkowy sygnał" in level(item)]

    assert len(main) <= 3
    assert len(additional) <= 2
    assert len(selected) <= 5


def test_selection_does_not_fill_slots_below_adjusted_minimum():
    items = [rec("over15", 110), rec("home_win", 108), rec("goal_both_halves", 105)]

    result = apply_final_selection(
        items,
        config(main_min_adjusted_score=120, additional_min_adjusted_score=115),
    )

    assert not any(item.passed for item in result)


def test_independent_market_beats_correlated_market_with_similar_score():
    items = [
        rec("home_win", 135),
        rec("home_win_ht", 134, raw_value=70),
        rec("goal_both_halves", 132),
        rec("total4", 131),
    ]

    result = apply_final_selection(
        items,
        config(max_main_recommendations=2, max_additional_signals=0),
    )
    selected_ids = {item.rule_id for item in result if item.passed}

    assert "home_win" in selected_ids
    assert "goal_both_halves" in selected_ids
    assert "home_win_ht" not in selected_ids


def test_exact_total_is_less_robust_than_broad_goal_market():
    items = [rec("total4", 120), rec("over15", 120)]

    result = apply_final_selection(
        items,
        config(max_main_recommendations=1, max_additional_signals=0),
    )

    selected_ids = {item.rule_id for item in result if item.passed}
    assert selected_ids == {"over15"}
