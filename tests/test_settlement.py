import pytest

from settlement import settle_recommendations, validate_scoreline


def rec(rule_id: str, passed: bool = True) -> dict:
    return {"rule_id": rule_id, "label": rule_id, "score": 110, "passed": passed, "data_quality": 100}


def result(rule_id: str, home: int, away: int, home_ht=None, away_ht=None) -> dict:
    return settle_recommendations([rec(rule_id)], home, away, home_ht, away_ht)[0]


def test_team_scored_twice_requires_at_least_one_team_not_both():
    assert result("team_scored_twice", 2, 0)["actual"] is True
    assert result("team_scored_twice", 1, 1)["actual"] is False


def test_directional_win_over_15_markets_are_distinct():
    assert result("win_over15", 2, 1)["actual"] is True
    assert result("lose_over15", 2, 1)["actual"] is False
    assert result("win_over15", 1, 3)["actual"] is False
    assert result("lose_over15", 1, 3)["actual"] is True


def test_htft_is_home_perspective_and_unambiguous():
    assert result("win_win", 3, 1, 2, 0)["actual"] is True
    assert result("lose_lose", 3, 1, 2, 0)["actual"] is False
    assert result("lose_win", 3, 1, 0, 1)["actual"] is True


def test_false_prediction_is_not_counted_as_hit():
    row = settle_recommendations([rec("draw", passed=False)], 2, 1)[0]
    assert row["result"] == "brak typu"


def test_invalid_half_time_score_is_rejected():
    valid, message = validate_scoreline(1, 0, 2, 0)
    assert valid is False
    assert "do przerwy" in message
    with pytest.raises(ValueError):
        settle_recommendations([rec("over15")], 1, 0, 2, 0)
