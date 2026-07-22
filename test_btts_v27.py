from engine import ALGORITHM_VERSION, evaluate_rule


def btts_rule():
    return {
        "id": "btts",
        "label": "BTTS TAK",
        "mode": "special",
        "conditions": [{
            "metric": "Both Teams to Score",
            "operator": ">=",
            "threshold_home": 55,
            "threshold_away": 55,
            "minimum_btts": 50,
            "minimum_team_scored": 70,
            "minimum_side_goals": 1.0,
            "minimum_strong_side_goals": 1.4,
            "maximum_under25": 65,
            "minimum_scoring_base": 60,
            "strong_clean_sheet_base": 55,
        }],
    }


def balanced_stats():
    return {
        "Both Teams to Score": {"home": 70, "away": 70},
        "Team scored": {"home": 90, "away": 90},
        "Under 2.5 goals": {"home": 30, "away": 30},
        "Goals scored per game": {"home": 1.6, "away": 1.5},
        "Goals conceded per game": {"home": 1.4, "away": 1.5},
        "Clean sheets": {"home": 20, "away": 20},
    }


def test_algorithm_version_27():
    assert ALGORITHM_VERSION == "2.7.0"


def test_btts_accepts_balanced_supported_profile():
    result = evaluate_rule(balanced_stats(), btts_rule())
    assert result.passed is True
    assert result.data_quality == 100
    assert any("Scoring base A" in reason for reason in result.reasons)


def test_btts_rejects_weak_offense_even_when_historic_btts_is_high():
    stats = balanced_stats()
    stats["Goals scored per game"]["away"] = 0.8
    result = evaluate_rule(stats, btts_rule())
    assert result.passed is False
    assert any("gole B=NIE" in reason for reason in result.reasons)


def test_btts_rejects_strong_clean_sheet_conflict():
    stats = balanced_stats()
    stats["Clean sheets"]["home"] = 60
    stats["Team scored"]["away"] = 70
    result = evaluate_rule(stats, btts_rule())
    assert result.passed is False
    assert any("brak silnego konfliktu clean sheet=NIE" in reason for reason in result.reasons)


def test_btts_rejects_side_below_minimum_btts():
    stats = balanced_stats()
    stats["Both Teams to Score"] = {"home": 80, "away": 40}
    result = evaluate_rule(stats, btts_rule())
    assert result.passed is False
    assert any("minimum BTTS=NIE" in reason for reason in result.reasons)


def test_btts_requires_complete_offense_defense_data():
    stats = balanced_stats()
    del stats["Goals conceded per game"]
    result = evaluate_rule(stats, btts_rule())
    assert result.passed is False
    assert result.data_quality < 100
