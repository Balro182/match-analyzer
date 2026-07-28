from engine import _evaluate_htft


def rule(rule_id: str, threshold: float):
    return {
        "id": rule_id,
        "label": rule_id,
        "mode": "mean",
        "conditions": [
            {
                "metric": "unused",
                "operator": ">=",
                "threshold_home": threshold,
                "threshold_away": threshold,
            }
        ],
    }


def stats():
    return {
        "Win HT - Win FT": {"home": 10.0, "away": 30.0},
        "Win HT - Draw FT": {"home": 10.0, "away": 10.0},
        "Win HT - Lose FT": {"home": 0.0, "away": 10.0},
        "Draw HT - Win FT": {"home": 40.0, "away": 10.0},
        "Draw HT - Draw FT": {"home": 0.0, "away": 20.0},
        "Draw HT - Lose FT": {"home": 10.0, "away": 0.0},
        "Lose HT - Win FT": {"home": 0.0, "away": 0.0},
        "Lose HT - Draw FT": {"home": 10.0, "away": 10.0},
        "Lose HT - Lose FT": {"home": 20.0, "away": 10.0},
    }


def test_home_home_uses_home_win_win_and_away_lose_lose():
    result = _evaluate_htft(stats(), rule("win_win", 5.0))
    assert result.raw_value == 10.0
    assert result.passed is True


def test_draw_home_uses_home_draw_win_and_away_draw_lose():
    result = _evaluate_htft(stats(), rule("draw_win", 10.0))
    assert result.raw_value == 20.0
    assert result.passed is True


def test_away_draw_uses_home_lose_draw_and_away_win_draw():
    result = _evaluate_htft(stats(), rule("lose_draw", 12.5))
    assert result.raw_value == 10.0
    assert result.passed is False


def test_away_away_uses_home_lose_lose_and_away_win_win():
    result = _evaluate_htft(stats(), rule("lose_lose", 20.0))
    assert result.raw_value == 25.0
    assert result.passed is True
