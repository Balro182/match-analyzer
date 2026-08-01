from engine import ALGORITHM_VERSION, evaluate_rule


def btts_rule():
    return {
        "id": "btts",
        "label": "BTTS TAK",
        "mode": "special",
        "conditions": [{
            "threshold_home": 55,
            "minimum_btts": 50,
            "minimum_team_scored": 70,
            "maximum_under25": 65,
            "dominance_min_goals": 2.0,
            "dominance_min_gap": 1.0,
            "dominance_min_clean_sheets": 40,
            "dominance_max_weaker_goals": 1.2,
            "dominance_escape_team_scored": 90,
            "dominance_escape_btts": 70,
        }],
    }


def stats(home_goals=1.7, away_goals=1.5, home_clean=20, away_clean=20):
    return {
        "Both Teams to Score": {"home": 70, "away": 70},
        "Team scored": {"home": 90, "away": 90},
        "Under 2.5 goals": {"home": 30, "away": 30},
        "Goals scored per game": {"home": home_goals, "away": away_goals},
        "Goals conceded per game": {"home": 1.3, "away": 1.4},
        "Clean sheets": {"home": home_clean, "away": away_clean},
    }


def test_algorithm_version_is_current():
    assert ALGORITHM_VERSION == "2.12.0"


def test_unilateral_dominance_blocks_btts():
    data = stats(home_goals=3.1, away_goals=1.2, home_clean=40)
    data["Both Teams to Score"]["away"] = 60
    data["Team scored"]["away"] = 80
    result = evaluate_rule(data, btts_rule())
    assert result.passed is False
    assert any("blok dominacji" in reason and reason.startswith("NIE:") for reason in result.reasons)


def test_balanced_profile_keeps_btts():
    result = evaluate_rule(stats(), btts_rule())
    assert result.passed is True


def test_dominance_escape_keeps_reliable_weaker_attack():
    data = stats(home_goals=2.6, away_goals=1.2, home_clean=40)
    data["Both Teams to Score"]["away"] = 70
    data["Team scored"]["away"] = 90
    result = evaluate_rule(data, btts_rule())
    assert result.passed is True


def test_missing_extended_metrics_reduce_quality():
    result = evaluate_rule({
        "Both Teams to Score": {"home": 70, "away": 70},
        "Team scored": {"home": 80, "away": 80},
    }, btts_rule())
    assert result.passed is False
    assert result.data_quality < 100
