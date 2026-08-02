from exact_score import ft_profile_diagnostics, rank_exact_scores_ft


SILKEBORG_COPENHAGEN = {
    "Goals scored per game": {"home": 2.30, "away": 2.50},
    "Goals conceded per game": {"home": 1.70, "away": 1.50},
    "Clean sheets": {"home": 20, "away": 10},
    "Team scored": {"home": 70, "away": 100},
    "Team scored twice": {"home": 50, "away": 80},
    "Win": {"home": 40, "away": 50},
    "Draw": {"home": 20, "away": 40},
    "Lose": {"home": 40, "away": 10},
    "Team win first half": {"home": 40, "away": 20},
    "Team draw at half time": {"home": 10, "away": 50},
    "Team lost first half": {"home": 50, "away": 30},
    "Both Teams to Score": {"home": 50, "away": 90},
    "BTTS in first-half": {"home": 10, "away": 40},
    "Win and BTTS": {"home": 20, "away": 40},
    "Draw and BTTS": {"home": 20, "away": 40},
    "Lose and BTTS": {"home": 10, "away": 10},
    "Match total goals 0": {"home": 0, "away": 0},
    "Match total goals 1": {"home": 10, "away": 0},
    "Match total goals 2": {"home": 20, "away": 10},
    "Match total goals 3": {"home": 10, "away": 30},
    "Match total goals 4": {"home": 40, "away": 30},
    "Under 1.5 goals": {"home": 10, "away": 0},
    "Over 2.5 goals": {"home": 70, "away": 90},
    "Over 3.5 goals": {"home": 60, "away": 60},
    "Under 3.5 goals": {"home": 40, "away": 40},
    "Over 0.5 goals at half-time": {"home": 90, "away": 80},
    "Over 1.5 goals at half-time": {"home": 40, "away": 50},
    "Over 2.5 goals at half-time": {"home": 10, "away": 20},
}


def test_directional_scoring_edge_disables_draw_bonus_and_promotes_favorite():
    profile = ft_profile_diagnostics(SILKEBORG_COPENHAGEN)["selection"]
    scores = [pick.score for pick in rank_exact_scores_ft(SILKEBORG_COPENHAGEN, limit=3)]

    assert profile["high_draw_directional_margin"] == 15.0
    assert profile["high_draw_team_twice_edge"] == 30.0
    assert profile["directional_high_draw_guard"] is True
    assert profile["balanced_high_draw_bonus"] is False
    assert scores[0] == "1:3"
    assert "2:2" in scores


def test_draw_bonus_remains_when_scoring_edge_is_small():
    balanced = dict(SILKEBORG_COPENHAGEN)
    balanced["Team scored twice"] = {"home": 50, "away": 60}

    profile = ft_profile_diagnostics(balanced)["selection"]

    assert profile["high_draw_directional_margin"] == 15.0
    assert profile["high_draw_team_twice_edge"] == 10.0
    assert profile["directional_high_draw_guard"] is False
    assert profile["balanced_high_draw_bonus"] is True
