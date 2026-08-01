from backtest_store import Scoreline, _hit
from engine import ALGORITHM_VERSION, analyze_match, evaluate_rule


def stats() -> dict:
    return {
        "Team scored twice": {"home": 60, "away": 20},
        "Goals scored per game": {"home": 1.8, "away": 0.8},
        "Goals conceded per game": {"home": 0.9, "away": 1.5},
        "Team scored": {"home": 90, "away": 60},
        "Clean sheets": {"home": 40, "away": 20},
        "Scored in both halves": {"home": 55, "away": 20},
        "Under 3.5 goals": {"home": 70, "away": 70},
    }


def minimal_config() -> dict:
    return {
        "recommendations": {
            "min_score": 0,
            "min_data_quality": 0,
            "selection": {
                "enabled": True,
                "max_recommendations": 5,
                "max_main_recommendations": 3,
                "max_additional_signals": 2,
                "minimum_half_outcome_lead": 0,
                "main_min_adjusted_score": 0,
                "additional_min_adjusted_score": 0,
            },
            "rules": [
                {"id": "team_scored_twice", "label": "stary rynek", "enabled": True, "mode": "any", "conditions": [{"metric": "Team scored twice", "operator": ">=", "threshold_home": 50, "threshold_away": 50}]},
                {"id": "scored_both_halves", "label": "stary rynek czasu", "enabled": True, "mode": "any", "conditions": [{"metric": "Scored in both halves", "operator": ">=", "threshold_home": 50, "threshold_away": 50}]},
            ],
            "btts_no": {"enabled": False},
        }
    }


def test_directional_over15_identifies_the_team() -> None:
    rule = {
        "id": "home_team_over15",
        "label": "A over 1.5",
        "conditions": [{
            "minimum_team_scored_twice": 50,
            "minimum_own_goals": 1.5,
            "minimum_opponent_conceded": 1.2,
            "minimum_team_scored": 80,
            "maximum_opponent_clean_sheets": 30,
            "minimum_supports": 2,
        }],
    }
    home = evaluate_rule(stats(), rule)
    away = evaluate_rule(stats(), {**rule, "id": "away_team_over15", "label": "B over 1.5"})
    assert home.passed is True
    assert away.passed is False


def test_analyze_match_replaces_non_bettable_collective_rules() -> None:
    result = analyze_match(
        {"home_team": "Turku PS", "away_team": "Mariehamn", "stats": stats()},
        minimal_config(),
    )
    ids = {item.rule_id for item in result}
    labels = {item.label for item in result}
    assert "team_scored_twice" not in ids
    assert "scored_both_halves" not in ids
    assert "home_team_over15" in ids
    assert "away_team_over15" in ids
    assert "Turku PS strzeli powyżej 1,5 gola" in labels
    assert "Mariehamn strzeli powyżej 1,5 gola" in labels
    assert ALGORITHM_VERSION == "2.12.0"


def test_directional_markets_settle_for_the_named_side() -> None:
    ht = Scoreline(1, 0)
    ft = Scoreline(3, 0)
    assert _hit("home_team_over15", ht, ft) is True
    assert _hit("away_team_over15", ht, ft) is False
    assert _hit("home_score_both_halves", ht, ft) is True
    assert _hit("away_score_both_halves", ht, ft) is False
    assert _hit("under35", ht, ft) is True
