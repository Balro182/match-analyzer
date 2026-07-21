from engine import evaluate_rule


def rule(rule_id: str, metric: str, threshold: float):
    return {
        "id": rule_id,
        "label": rule_id,
        "mode": "mean",
        "conditions": [
            {
                "metric": metric,
                "operator": ">=",
                "threshold_home": threshold,
                "threshold_away": threshold,
            }
        ],
    }


def inconsistent_thun_dinamo_stats():
    return {
        "Goals scored per game": {"home": 2.3, "away": 4.2},
        "Over 2.5 goals": {"home": 70, "away": 90},
        "Over 3.5 goals": {"home": 50, "away": 80},
        "Under 3.5 goals": {"home": 50, "away": 20},
        "Match total goals 4": {"home": 20, "away": 20},
        "Match total goals 4+": {"home": 0, "away": 0},
        "Match total goals 2": {"home": 10, "away": 10},
    }


def test_inconsistent_distribution_caps_over25_quality():
    result = evaluate_rule(
        inconsistent_thun_dinamo_stats(),
        rule("over25", "Over 2.5 goals", 67.5),
        {"maximum_4plus_gap": 20, "over_quality_cap": 80},
    )
    assert result.passed is True
    assert result.data_quality == 80
    assert any("Niespójność danych bramkowych" in reason for reason in result.reasons)


def test_inconsistent_distribution_caps_over35_quality_and_warns_about_extreme_average():
    result = evaluate_rule(
        inconsistent_thun_dinamo_stats(),
        rule("over35", "Over 3.5 goals", 47.5),
        {"maximum_4plus_gap": 20, "over_quality_cap": 80, "extreme_goals_warning": 3.0},
    )
    assert result.passed is True
    assert result.data_quality == 80
    assert any("ekstremalna średnia goli" in reason for reason in result.reasons)


def test_inconsistent_distribution_rejects_exact_total_market():
    result = evaluate_rule(
        inconsistent_thun_dinamo_stats(),
        rule("total2", "Match total goals 2", 10),
        {"maximum_4plus_gap": 20},
    )
    assert result.passed is False
    assert result.data_quality == 0


def test_consistent_distribution_preserves_full_quality():
    stats = {
        "Goals scored per game": {"home": 1.8, "away": 2.0},
        "Over 2.5 goals": {"home": 70, "away": 70},
        "Under 3.5 goals": {"home": 60, "away": 50},
        "Match total goals 4": {"home": 20, "away": 20},
        "Match total goals 4+": {"home": 40, "away": 50},
    }
    result = evaluate_rule(
        stats,
        rule("over25", "Over 2.5 goals", 67.5),
        {"maximum_4plus_gap": 20, "over_quality_cap": 80},
    )
    assert result.passed is True
    assert result.data_quality == 100
    assert not any("Niespójność danych bramkowych" in reason for reason in result.reasons)


def test_missing_distribution_data_does_not_penalize_market():
    stats = {"Over 2.5 goals": {"home": 80, "away": 80}}
    result = evaluate_rule(stats, rule("over25", "Over 2.5 goals", 67.5))
    assert result.passed is True
    assert result.data_quality == 100
