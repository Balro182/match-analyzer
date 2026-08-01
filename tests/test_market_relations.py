from engine_core import Recommendation
from selection import apply_final_selection, market_cluster, market_relation


def rec(rule_id: str, score: float, raw: float = 90, threshold: float = 60) -> Recommendation:
    return Recommendation(
        rule_id=rule_id,
        label=rule_id,
        score=score,
        passed=True,
        reasons=["reguła bazowa przeszła"],
        data_quality=100,
        raw_value=raw,
        threshold=threshold,
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
                "main_min_adjusted_score": 90,
                "additional_min_adjusted_score": 82,
                "equivalent_market_penalty": 0.12,
                "nested_market_penalty": 0.06,
                "same_cluster_shared_tag_penalty": 0.02,
                "exact_totals_main_allowed": False,
                "four_plus_main_allowed": False,
            },
        }
    }


def selected_level(item: Recommendation) -> str | None:
    text = " | ".join(item.reasons)
    if "Poziom selekcji: główny typ" in text:
        return "main"
    if "Poziom selekcji: dodatkowy sygnał" in text:
        return "additional"
    return None


def test_market_relation_matrix_distinguishes_conflict_nested_and_independent():
    assert market_relation("btts", "btts_no") == "conflict"
    assert market_relation("total3", "under35") == "nested"
    assert market_relation("over15", "under35") == "independent"
    assert market_relation("goal_both_halves", "under35") == "independent"
    assert market_cluster("total3") == "exact_total"
    assert market_cluster("goal_both_halves") == "match_timing"


def test_separate_goal_markets_are_not_removed_by_category_limit():
    result = apply_final_selection(
        [
            rec("over15", 130),
            rec("under35", 125),
            rec("over25", 120),
            rec("goal_both_halves", 118),
            rec("total3", 150, raw=45, threshold=22.5),
        ],
        config(),
    )
    levels = {item.rule_id: selected_level(item) for item in result}

    assert levels["over15"] == "main"
    assert levels["under35"] == "main"
    assert levels["over25"] == "main"
    assert levels["goal_both_halves"] == "additional"
    assert levels["total3"] == "additional"
    assert all(any(reason.startswith("Klaster rynku:") for reason in item.reasons) for item in result if levels[item.rule_id])


def test_hard_conflicts_are_still_rejected():
    result = apply_final_selection([rec("over25", 130), rec("under25", 120)], config())
    selected = [item.rule_id for item in result if selected_level(item)]
    rejected = {item.rule_id: " | ".join(item.reasons) for item in result if not item.passed}

    assert selected == ["over25"]
    assert "sprzeczny" in rejected["under25"]
