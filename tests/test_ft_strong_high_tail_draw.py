from exact_score import ft_profile_diagnostics, rank_exact_scores_ft


STAL_PODBESKIDZIE = {
    "Goals scored per game": {"home": 2.10, "away": 1.50},
    "Goals conceded per game": {"home": 1.80, "away": 1.00},
    "Clean sheets": {"home": 20, "away": 20},
    "Team scored": {"home": 100, "away": 90},
    "Team scored twice": {"home": 50, "away": 40},
    "Win": {"home": 50, "away": 40},
    "Draw": {"home": 10, "away": 40},
    "Lose": {"home": 40, "away": 20},
    "Team win first half": {"home": 70, "away": 50},
    "Team draw at half time": {"home": 20, "away": 30},
    "Team lost first half": {"home": 10, "away": 20},
    "Both Teams to Score": {"home": 80, "away": 70},
    "BTTS in first-half": {"home": 40, "away": 20},
    "Win and BTTS": {"home": 30, "away": 20},
    "Draw and BTTS": {"home": 10, "away": 40},
    "Lose and BTTS": {"home": 40, "away": 10},
    "Match total goals 0": {"home": 0, "away": 0},
    "Match total goals 1": {"home": 10, "away": 20},
    "Match total goals 2": {"home": 10, "away": 40},
    "Match total goals 3": {"home": 10, "away": 20},
    "Match total goals 4": {"home": 30, "away": 10},
    "Under 1.5 goals": {"home": 10, "away": 20},
    "Over 2.5 goals": {"home": 80, "away": 40},
    "Over 3.5 goals": {"home": 70, "away": 20},
    "Under 3.5 goals": {"home": 30, "away": 80},
    "Over 0.5 goals at half-time": {"home": 100, "away": 80},
    "Over 1.5 goals at half-time": {"home": 70, "away": 40},
    "Over 2.5 goals at half-time": {"home": 50, "away": 10},
}


def test_strong_high_tail_uses_gentler_decay_and_balanced_draw_bonus():
    profile = ft_profile_diagnostics(STAL_PODBESKIDZIE)["selection"]
    scores = [pick.score for pick in rank_exact_scores_ft(STAL_PODBESKIDZIE, limit=12)]

    assert profile["goal_totals"] == [2, 4, 5]
    assert profile["strong_high_tail_decay"] is True
    assert profile["balanced_high_draw_bonus"] is True
    assert "3:3" in scores


def test_high_draw_bonus_requires_balanced_expected_goals():
    asymmetric = dict(STAL_PODBESKIDZIE)
    asymmetric["Goals scored per game"] = {"home": 3.0, "away": 0.8}
    asymmetric["Goals conceded per game"] = {"home": 0.7, "away": 2.0}

    profile = ft_profile_diagnostics(asymmetric)["selection"]

    assert profile["strong_high_tail_decay"] is True
    assert profile["balanced_high_draw_bonus"] is False
