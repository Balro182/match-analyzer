from engine import ALGORITHM_VERSION, evaluate_rule


def btts_rule():
    return {
        "id": "btts",
        "label": "BTTS TAK — obie drużyny strzelą",
        "mode": "special",
        "conditions": [
            {
                "metric": "Both Teams to Score",
                "operator": ">=",
                "threshold_home": 55,
                "threshold_away": 55,
                "minimum_btts": 45,
                "minimum_team_scored": 70,
                "maximum_under25": 65,
                "dominance_min_goals": 2.0,
                "dominance_min_gap": 1.0,
                "dominance_min_clean_sheets": 40,
                "dominance_max_weaker_goals": 1.2,
                "dominance_escape_team_scored": 90,
                "dominance_escape_btts": 70,
            }
        ],
    }


def test_algorithm_version_is_2_4_0():
    assert ALGORITHM_VERSION == "2.4.0"


def test_hammarby_degerfors_is_blocked_by_unilateral_dominance():
    stats = {
        "Both Teams to Score": {"home": 60, "away": 60},
        "Team scored": {"home": 100, "away": 80},
        "Under 2.5 goals": {"home": 20, "away": 40},
        "Goals scored per game": {"home": 3.1, "away": 1.2},
        "Clean sheets": {"home": 40, "away": 20},
    }
    result = evaluate_rule(stats, btts_rule())
    assert result.passed is False
    assert any("blok=TAK" in reason for reason in result.reasons)


def test_elfsborg_sirius_keeps_btts_recommendation():
    stats = {
        "Both Teams to Score": {"home": 80, "away": 80},
        "Team scored": {"home": 100, "away": 100},
        "Under 2.5 goals": {"home": 50, "away": 0},
        "Goals scored per game": {"home": 1.7, "away": 2.5},
        "Clean sheets": {"home": 20, "away": 20},
    }
    result = evaluate_rule(stats, btts_rule())
    assert result.passed is True
    assert any("blok=NIE" in reason for reason in result.reasons)


def test_dominance_escape_preserves_exceptionally_reliable_weaker_attack():
    stats = {
        "Both Teams to Score": {"home": 80, "away": 70},
        "Team scored": {"home": 100, "away": 90},
        "Under 2.5 goals": {"home": 20, "away": 30},
        "Goals scored per game": {"home": 2.6, "away": 1.2},
        "Clean sheets": {"home": 40, "away": 10},
    }
    result = evaluate_rule(stats, btts_rule())
    assert result.passed is True
    assert any("blok=NIE" in reason for reason in result.reasons)


def test_missing_dominance_metrics_does_not_reduce_legacy_data_quality():
    stats = {
        "Both Teams to Score": {"home": 70, "away": 70},
        "Team scored": {"home": 80, "away": 80},
    }
    result = evaluate_rule(stats, btts_rule())
    assert result.passed is False
    assert round(result.data_quality, 1) == 66.7
