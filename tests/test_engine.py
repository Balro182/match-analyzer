from engine import evaluate_rule


def mean_rule():
    return {
        "id": "over25",
        "label": "Over 2.5",
        "mode": "mean",
        "conditions": [{"metric": "Over 2.5 goals", "operator": ">=", "threshold_home": 60, "threshold_away": 60}],
    }


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
        }],
    }


def btts_stats(home_btts=60, away_btts=60, home_goals=1.6, away_goals=1.5):
    return {
        "Both Teams to Score": {"home": home_btts, "away": away_btts},
        "Team scored": {"home": 90, "away": 90},
        "Under 2.5 goals": {"home": 40, "away": 40},
        "Goals scored per game": {"home": home_goals, "away": away_goals},
        "Goals conceded per game": {"home": 1.4, "away": 1.5},
        "Clean sheets": {"home": 20, "away": 20},
    }


def test_continuous_score_distinguishes_small_and_large_margin():
    weak = evaluate_rule({"Over 2.5 goals": {"home": 61, "away": 61}}, mean_rule())
    strong = evaluate_rule({"Over 2.5 goals": {"home": 90, "away": 90}}, mean_rule())
    assert weak.passed and strong.passed
    assert strong.score > weak.score


def test_missing_metric_reduces_data_quality():
    result = evaluate_rule({}, mean_rule())
    assert result.data_quality == 0
    assert result.passed is False


def test_btts_accepts_balanced_supported_profile():
    result = evaluate_rule(btts_stats(), btts_rule())
    assert result.raw_value == 60
    assert result.passed is True
    assert result.data_quality == 100


def test_btts_rejects_weak_side_despite_mean_threshold():
    result = evaluate_rule(btts_stats(home_btts=80, away_btts=30), btts_rule())
    assert result.raw_value == 55
    assert result.passed is False


def test_btts_rejects_weak_offense():
    result = evaluate_rule(btts_stats(away_goals=0.8), btts_rule())
    assert result.passed is False


def test_btts_requires_extended_supporting_metrics():
    result = evaluate_rule({
        "Both Teams to Score": {"home": 60, "away": 60},
        "Team scored": {"home": 80, "away": 80},
    }, btts_rule())
    assert result.passed is False
    assert result.data_quality < 100
