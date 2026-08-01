from engine_core import Recommendation
from exact_score import is_valid_score_progression
from selection import apply_final_selection


def rec(rule_id: str, score: float = 130, raw: float = 70, threshold: float = 50) -> Recommendation:
    return Recommendation(
        rule_id=rule_id,
        label=rule_id,
        score=score,
        passed=True,
        reasons=[],
        data_quality=100.0,
        raw_value=raw,
        threshold=threshold,
        mode="test",
    )


def config(**overrides):
    selection = {
        "enabled": True,
        "max_recommendations": 5,
        "max_main_recommendations": 3,
        "max_additional_signals": 2,
        "max_per_category": 2,
        "minimum_half_outcome_lead": 0,
        "independence_penalty_per_shared_tag": 0.12,
        "main_min_adjusted_score": 0,
        "additional_min_adjusted_score": 0,
        "exact_totals_main_allowed": False,
        "boundary_margin_pp": 2.5,
        "boundary_penalty": 0.12,
    }
    selection.update(overrides)
    return {"recommendations": {"min_score": 100, "min_data_quality": 100, "selection": selection}}


def selected_ids(items):
    return {item.rule_id for item in items if item.passed}


def test_exact_one_conflicts_with_team_scored_twice():
    result = apply_final_selection([rec("total1", 145), rec("team_scored_twice", 140)], config())
    assert not {"total1", "team_scored_twice"} <= selected_ids(result)


def test_exact_three_conflicts_with_draw_ft():
    result = apply_final_selection([rec("total3", 145), rec("draw", 140)], config())
    assert not {"total3", "draw"} <= selected_ids(result)


def test_best_set_is_compatible_not_greedy():
    result = apply_final_selection(
        [rec("total3", 150), rec("draw", 149), rec("over15", 130), rec("over05ht", 128)],
        config(max_main_recommendations=2, max_additional_signals=0),
    )
    ids = selected_ids(result)
    assert len(ids) == 2
    assert not {"total3", "draw"} <= ids


def test_point_exact_totals_are_additional_only_by_default():
    result = apply_final_selection(
        [rec("total2", 150), rec("over15", 125)],
        config(max_main_recommendations=1, max_additional_signals=1),
    )
    exact = next(item for item in result if item.rule_id == "total2")
    assert exact.passed
    assert any("dodatkowy sygnał" in reason for reason in exact.reasons)


def test_invalid_ht_ft_progression_is_rejected():
    assert not is_valid_score_progression(0, 1, 2, 0)
    assert not is_valid_score_progression(1, 2, 2, 1)
    assert is_valid_score_progression(0, 1, 2, 1)
