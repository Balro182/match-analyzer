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
