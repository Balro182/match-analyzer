from engine_core import Recommendation
from selection import apply_final_selection


def rec(rule_id: str, score: float, raw_value: float) -> Recommendation:
    return Recommendation(
        rule_id=rule_id,
        label=rule_id,
        score=score,
        passed=True,
        reasons=[],
        data_quality=100.0,
        raw_value=raw_value,
        threshold=1.0,
        mode="mean",
    )


def config() -> dict:
    return {
        "recommendations": {
            "min_score": 100,
            "min_data_quality": 100,
            "selection": {
                "enabled": True,
                "max_recommendations": 5,
                "max_main_recommendations": 3,
                "max_additional_signals": 2,
                "max_per_category": 1,
                "minimum_half_outcome_lead": 7.5,
                "independence_penalty_per_shared_tag": 0.12,
                "main_min_adjusted_score": 90,
                "additional_min_adjusted_score": 82,
                "four_plus_min_raw_value": 50,
                "four_plus_main_allowed": False,
            },
        }
    }


def test_four_plus_with_40_percent_base_is_rejected_before_ranking():
    result = apply_final_selection(
        [rec("total4plus", 145.5, 40.0), rec("over15", 113.3, 85.0)],
        config(),
    )
    four_plus = next(item for item in result if item.rule_id == "total4plus")
    over15 = next(item for item in result if item.rule_id == "over15")

    assert four_plus.passed is False
    assert any("baza 40.0% < wymagane 50%" in reason for reason in four_plus.reasons)
    assert over15.passed is True
    assert any("główny typ" in reason for reason in over15.reasons)


def test_four_plus_with_50_percent_base_can_only_be_additional():
    result = apply_final_selection(
        [rec("total4plus", 150.0, 50.0), rec("over15", 120.0, 90.0)],
        config(),
    )
    four_plus = next(item for item in result if item.rule_id == "total4plus")

    assert four_plus.passed is True
    assert any("dodatkowy sygnał" in reason for reason in four_plus.reasons)
    assert not any("główny typ" in reason for reason in four_plus.reasons)
