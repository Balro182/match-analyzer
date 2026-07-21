from engine import evaluate_rule


def winner_rule(rule_id: str):
    return {
        "id": rule_id,
        "label": "Wygra A" if rule_id == "home_win" else "Wygra B",
        "mode": "special",
        "conditions": [
            {
                "metric": "Win",
                "operator": ">=",
                "threshold_home": 60,
                "threshold_away": 60,
                "minimum_own_win": 50,
                "minimum_opponent_lose": 50,
                "minimum_own_goals": 1.4,
                "minimum_opponent_conceded": 1.3,
                "volatility_opponent_goals": 1.5,
                "volatility_team_scored": 80,
            }
        ],
    }


def test_home_win_accepts_corvinul_profile():
    stats = {
        "Win": {"home": 60, "away": 20},
        "Lose": {"home": 10, "away": 60},
        "Goals scored per game": {"home": 1.5, "away": 0.8},
        "Goals conceded per game": {"home": 0.6, "away": 1.8},
        "Team scored": {"home": 90, "away": 60},
        "Both Teams to Score": {"home": 40, "away": 50},
        "Under 2.5 goals": {"home": 70, "away": 50},
    }
    result = evaluate_rule(stats, winner_rule("home_win"))
    assert result.raw_value == 60
    assert result.passed is True
    assert result.data_quality == 100


def test_home_win_blocks_turku_profile_due_to_opponent_volatility():
    stats = {
        "Win": {"home": 70, "away": 20},
        "Lose": {"home": 20, "away": 50},
        "Goals scored per game": {"home": 1.8, "away": 1.7},
        "Goals conceded per game": {"home": 0.9, "away": 2.0},
        "Team scored": {"home": 100, "away": 80},
        "Both Teams to Score": {"home": 50, "away": 70},
        "Under 2.5 goals": {"home": 40, "away": 20},
    }
    result = evaluate_rule(stats, winner_rule("home_win"))
    assert result.raw_value == 60
    assert result.passed is False
    assert any("Blokada zmienności: TAK" in reason for reason in result.reasons)


def test_away_win_is_symmetric():
    stats = {
        "Win": {"home": 20, "away": 60},
        "Lose": {"home": 60, "away": 20},
        "Goals scored per game": {"home": 0.8, "away": 1.5},
        "Goals conceded per game": {"home": 1.8, "away": 0.6},
        "Team scored": {"home": 60, "away": 90},
        "Both Teams to Score": {"home": 40, "away": 50},
        "Under 2.5 goals": {"home": 50, "away": 70},
    }
    result = evaluate_rule(stats, winner_rule("away_win"))
    assert result.raw_value == 60
    assert result.passed is True


def test_guarded_winner_requires_supporting_metrics():
    stats = {
        "Win": {"home": 70, "away": 20},
        "Lose": {"home": 20, "away": 60},
    }
    result = evaluate_rule(stats, winner_rule("home_win"))
    assert result.passed is False
    assert result.data_quality < 100


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


def draw_rule():
    return {
        "id": "draw",
        "label": "Remis",
        "mode": "special",
        "conditions": [
            {
                "metric": "Draw",
                "operator": ">=",
                "threshold_home": 35,
                "threshold_away": 35,
                "primary_draw": 35,
                "primary_max_gap": 25,
                "low_draw": 30,
                "low_under35": 70,
                "low_draw_ht": 45,
                "maximum_winner_base": 55,
                "guarded_winner_threshold": 60,
            }
        ],
    }


def test_draw_accepts_jaro_inter_through_primary_path():
    stats = {
        "Draw": {"home": 50, "away": 40},
        "Win": {"home": 20, "away": 50},
        "Lose": {"home": 30, "away": 10},
        "Under 3.5 goals": {"home": 70, "away": 60},
        "Team draw at half time": {"home": 30, "away": 30},
    }
    result = evaluate_rule(stats, draw_rule())
    assert result.raw_value == 45
    assert result.passed is True
    assert any("A — podstawowa" in reason for reason in result.reasons)


def test_draw_accepts_botev_cherno_more_through_low_scoring_path():
    stats = {
        "Draw": {"home": 30, "away": 30},
        "Win": {"home": 60, "away": 40},
        "Lose": {"home": 10, "away": 30},
        "Under 3.5 goals": {"home": 80, "away": 90},
        "Team draw at half time": {"home": 70, "away": 50},
    }
    result = evaluate_rule(stats, draw_rule())
    assert result.raw_value == 30
    assert result.passed is True
    assert any("B — niskobramkowa" in reason for reason in result.reasons)


def test_draw_rejects_low_draw_without_defensive_support():
    stats = {
        "Draw": {"home": 30, "away": 30},
        "Win": {"home": 50, "away": 40},
        "Lose": {"home": 30, "away": 30},
        "Under 3.5 goals": {"home": 50, "away": 50},
        "Team draw at half time": {"home": 30, "away": 30},
    }
    result = evaluate_rule(stats, draw_rule())
    assert result.passed is False


def test_draw_requires_all_supporting_metrics():
    stats = {
        "Draw": {"home": 40, "away": 40},
        "Win": {"home": 30, "away": 30},
        "Lose": {"home": 30, "away": 30},
    }
    result = evaluate_rule(stats, draw_rule())
    assert result.passed is False
    assert result.data_quality < 100
