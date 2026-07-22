from engine import evaluate_rule
from evaluation import STATUS_LOW_DATA_QUALITY, recommendation_status


def mean_rule(rule_id: str, metric: str, threshold: float):
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


def clean_sheet_rule():
    return {
        "id": "clean_sheets",
        "label": "Przynajmniej jedna drużyna zachowa czyste konto",
        "mode": "special",
        "conditions": [
            {
                "metric": "Clean sheets",
                "operator": ">=",
                "threshold_home": 45,
                "threshold_away": 45,
                "minimum_clean_sheet_base": 45,
            }
        ],
    }


def inconsistent_goal_distribution():
    return {
        "Under 3.5 goals": {"home": 70, "away": 80},
        "Match total goals 4+": {"home": 0, "away": 0},
        "Match total goals 4": {"home": 10, "away": 0},
    }


def test_under25_quality_is_capped_when_goal_distribution_conflicts():
    stats = {
        **inconsistent_goal_distribution(),
        "Under 2.5 goals": {"home": 60, "away": 60},
    }
    result = evaluate_rule(
        stats,
        mean_rule("under25", "Under 2.5 goals", 57.5),
        {"maximum_4plus_gap": 20, "total_quality_cap": 80},
    )
    assert result.passed is True
    assert result.data_quality == 80
    assert recommendation_status(result.to_dict()) == STATUS_LOW_DATA_QUALITY


def test_under35_quality_is_capped_when_its_own_distribution_conflicts():
    stats = inconsistent_goal_distribution()
    result = evaluate_rule(
        stats,
        mean_rule("under35", "Under 3.5 goals", 67.5),
        {"maximum_4plus_gap": 20, "total_quality_cap": 80},
    )
    assert result.passed is True
    assert result.data_quality == 80
    assert any("Niespójność danych bramkowych" in reason for reason in result.reasons)


def test_consistent_under_market_keeps_full_quality():
    stats = {
        "Under 3.5 goals": {"home": 70, "away": 80},
        "Match total goals 4+": {"home": 30, "away": 20},
        "Match total goals 4": {"home": 10, "away": 0},
        "Under 2.5 goals": {"home": 60, "away": 60},
    }
    result = evaluate_rule(
        stats,
        mean_rule("under25", "Under 2.5 goals", 57.5),
        {"maximum_4plus_gap": 20, "total_quality_cap": 80},
    )
    assert result.passed is True
    assert result.data_quality == 100


def test_seoul_pohang_clean_sheet_profile_is_rejected():
    stats = {
        "Clean sheets": {"home": 60, "away": 40},
        "Team scored": {"home": 60, "away": 90},
    }
    result = evaluate_rule(stats, clean_sheet_rule())
    assert result.raw_value == 40
    assert result.passed is False
    assert any("Baza czystego konta A" in reason for reason in result.reasons)


def test_clean_sheet_profile_requires_defensive_and_opponent_support():
    stats = {
        "Clean sheets": {"home": 70, "away": 20},
        "Team scored": {"home": 80, "away": 50},
    }
    result = evaluate_rule(stats, clean_sheet_rule())
    assert result.raw_value == 60
    assert result.passed is True


def test_clean_sheet_rule_requires_team_scored_metric():
    result = evaluate_rule(
        {"Clean sheets": {"home": 70, "away": 20}},
        clean_sheet_rule(),
    )
    assert result.passed is False
    assert result.data_quality == 50
