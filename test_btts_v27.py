from engine import ALGORITHM_VERSION, evaluate_rule
from evaluation import STATUS_BORDERLINE, STATUS_FORMAL, recommendation_status


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
            # Celowo stara wartość: silnik 2.7.1 musi wymusić twardy blok od 60.
            "strong_clean_sheet_base": 55,
        }],
    }


def clean_sheet_rule():
    return {
        "id": "clean_sheets",
        "label": "Czyste konto",
        "mode": "special",
        "conditions": [{
            "metric": "Clean sheets",
            "operator": ">=",
            "threshold_home": 45,
            "threshold_away": 45,
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


def test_algorithm_version_271():
    assert ALGORITHM_VERSION == "2.7.1"


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


def test_btts_does_not_hard_block_clean_base_55():
    stats = balanced_stats()
    stats["Clean sheets"]["home"] = 80
    stats["Team scored"]["away"] = 70
    result = evaluate_rule(stats, btts_rule())
    assert result.passed is True
    assert any("twardy blok od 60" in reason for reason in result.reasons)
    assert any("brak twardego konfliktu clean sheet=TAK" in reason for reason in result.reasons)


def test_btts_rejects_clean_base_60_or_more():
    stats = balanced_stats()
    stats["Clean sheets"]["home"] = 90
    stats["Team scored"]["away"] = 70
    result = evaluate_rule(stats, btts_rule())
    assert result.passed is False
    assert any("brak twardego konfliktu clean sheet=NIE" in reason for reason in result.reasons)


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


def test_clean_sheet_base_50_is_borderline():
    stats = {
        "Clean sheets": {"home": 60, "away": 10},
        "Team scored": {"home": 90, "away": 60},
    }
    result = evaluate_rule(stats, clean_sheet_rule())
    assert result.raw_value == 50
    assert result.passed is True
    assert result.score == 104.9
    assert recommendation_status(result.to_dict()) == STATUS_BORDERLINE


def test_clean_sheet_base_55_is_formal_not_strong():
    stats = {
        "Clean sheets": {"home": 60, "away": 10},
        "Team scored": {"home": 90, "away": 50},
    }
    result = evaluate_rule(stats, clean_sheet_rule())
    assert result.raw_value == 55
    assert result.passed is True
    assert recommendation_status(result.to_dict()) == STATUS_FORMAL
    assert any("FORMAL" in reason for reason in result.reasons)


def test_clean_sheet_base_60_is_strong():
    stats = {
        "Clean sheets": {"home": 70, "away": 10},
        "Team scored": {"home": 90, "away": 50},
    }
    result = evaluate_rule(stats, clean_sheet_rule())
    assert result.raw_value == 60
    assert result.passed is True
    assert any("STRONG" in reason for reason in result.reasons)
