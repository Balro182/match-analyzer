from exact_score import _ft_market_alignment, ft_profile_diagnostics


def _stats(home_twice: float, away_twice: float):
    return {
        "Goals scored per game": {"home": 1.4, "away": 1.0},
        "Goals conceded per game": {"home": 0.9, "away": 1.5},
        "Team scored twice": {"home": home_twice, "away": away_twice},
        "Win": {"home": 40, "away": 30},
        "Draw": {"home": 40, "away": 10},
        "Lose": {"home": 20, "away": 60},
        "Both Teams to Score": {"home": 60, "away": 30},
        "Match total goals 0": {"home": 10, "away": 0},
        "Match total goals 1": {"home": 20, "away": 20},
        "Match total goals 2": {"home": 30, "away": 40},
        "Match total goals 3": {"home": 20, "away": 20},
        "Match total goals 4": {"home": 20, "away": 10},
        "Under 3.5 goals": {"home": 80, "away": 80},
        "Team win first half": {"home": 30, "away": 30},
        "Team draw at half time": {"home": 50, "away": 30},
        "Team lost first half": {"home": 20, "away": 40},
        "BTTS in first-half": {"home": 30, "away": 20},
        "Over 0.5 goals at half-time": {"home": 70, "away": 80},
        "Over 1.5 goals at half-time": {"home": 50, "away": 50},
        "Over 2.5 goals at half-time": {"home": 10, "away": 10},
    }


def test_standard_team_twice_signal_uses_reduced_weight():
    profile = ft_profile_diagnostics(_stats(30, 30))["selection"]
    assert profile["team_scored_twice_active_weight"] == 7.5
    assert profile["team_scored_twice_default_weight"] == 7.5


def test_strong_directional_edge_keeps_full_weight():
    profile = ft_profile_diagnostics(_stats(50, 80))["selection"]
    assert profile["team_scored_twice_active_weight"] == 15.0
    assert profile["team_scored_twice_strong_edge_threshold"] == 20.0


def test_reduced_weight_limits_one_one_bias():
    balanced = _stats(30, 30)
    no_signal = _stats(50, 50)
    balanced_gap = _ft_market_alignment("1:1", balanced) - _ft_market_alignment("2:0", balanced)
    neutral_gap = _ft_market_alignment("1:1", no_signal) - _ft_market_alignment("2:0", no_signal)
    assert balanced_gap - neutral_gap < 0.02
