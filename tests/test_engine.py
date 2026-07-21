from engine import evaluate_rule


def test_home_win_uses_win_a_and_lose_b_average():
    stats = {
        "Win": {"home": 80, "away": 100},
        "Draw": {"home": 0, "away": 0},
        "Lose": {"home": 20, "away": 0},
    }
    rule = {
        "id": "home_win",
        "label": "Wygra A",
        "mode": "special",
        "conditions": [{"metric": "Win", "operator": ">=", "threshold_home": 55, "threshold_away": 55}],
    }
    result = evaluate_rule(stats, rule)
    assert result.raw_value == 40
    assert result.passed is False
    assert round(result.score, 1) == 72.7


def test_away_win_uses_win_b_and_lose_a_average():
    stats = {
        "Win": {"home": 80, "away": 100},
        "Draw": {"home": 0, "away": 0},
        "Lose": {"home": 20, "away": 0},
    }
    rule = {
        "id": "away_win",
        "label": "Wygra B",
        "mode": "special",
        "conditions": [{"metric": "Win", "operator": ">=", "threshold_home": 55, "threshold_away": 55}],
    }
    result = evaluate_rule(stats, rule)
    assert result.raw_value == 60
    assert result.passed is True
    assert result.score > 100


def test_continuous_score_distinguishes_small_and_large_margin():
    rule = {
        "id": "over25",
        "label": "Over 2.5",
        "mode": "mean",
        "conditions": [{"metric": "Over 2.5 goals", "operator": ">=", "threshold_home": 60, "threshold_away": 60}],
    }
    weak = evaluate_rule({"Over 2.5 goals": {"home": 61, "away": 61}}, rule)
    strong = evaluate_rule({"Over 2.5 goals": {"home": 90, "away": 90}}, rule)
    assert weak.passed and strong.passed
    assert strong.score > weak.score


def test_missing_metric_reduces_data_quality():
    rule = {
        "id": "missing",
        "label": "Missing",
        "mode": "mean",
        "conditions": [{"metric": "Unknown metric", "operator": ">=", "threshold_home": 50, "threshold_away": 50}],
    }
    result = evaluate_rule({}, rule)
    assert result.data_quality == 0
    assert result.passed is False


def btts_rule():
    return {
        "id": "btts",
        "label": "Obie drużyny strzelą",
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
            }
        ],
    }


def test_btts_accepts_balanced_60_50_profile():
    stats = {
        "Both Teams to Score": {"home": 60, "away": 50},
        "Team scored": {"home": 90, "away": 90},
        "Under 2.5 goals": {"home": 40, "away": 40},
    }
    result = evaluate_rule(stats, btts_rule())
    assert result.raw_value == 55
    assert result.passed is True
    assert result.data_quality == 100


def test_btts_accepts_asymmetric_50_90_profile():
    stats = {
        "Both Teams to Score": {"home": 50, "away": 90},
        "Team scored": {"home": 90, "away": 90},
        "Under 2.5 goals": {"home": 40, "away": 10},
    }
    result = evaluate_rule(stats, btts_rule())
    assert result.raw_value == 70
    assert result.passed is True


def test_btts_rejects_80_30_despite_mean_55():
    stats = {
        "Both Teams to Score": {"home": 80, "away": 30},
        "Team scored": {"home": 90, "away": 90},
        "Under 2.5 goals": {"home": 40, "away": 40},
    }
    result = evaluate_rule(stats, btts_rule())
    assert result.raw_value == 55
    assert result.passed is False


def test_btts_rejects_high_under25_profile():
    stats = {
        "Both Teams to Score": {"home": 70, "away": 50},
        "Team scored": {"home": 80, "away": 80},
        "Under 2.5 goals": {"home": 70, "away": 70},
    }
    result = evaluate_rule(stats, btts_rule())
    assert result.passed is False


def test_btts_requires_all_supporting_metrics():
    stats = {
        "Both Teams to Score": {"home": 60, "away": 60},
        "Team scored": {"home": 80, "away": 80},
    }
    result = evaluate_rule(stats, btts_rule())
    assert result.passed is False
    assert round(result.data_quality, 1) == 66.7
