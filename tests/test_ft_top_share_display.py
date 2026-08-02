from exact_score import ft_profile_diagnostics, rank_exact_scores_ft


WSG_STURM = {
    "Goals scored per game": {"home": 1.2, "away": 2.1},
    "Goals conceded per game": {"home": 1.6, "away": 1.0},
    "Clean sheets": {"home": 30, "away": 30},
    "Team scored": {"home": 80, "away": 90},
    "Team scored twice": {"home": 30, "away": 60},
    "Win": {"home": 30, "away": 50},
    "Draw": {"home": 40, "away": 40},
    "Lose": {"home": 30, "away": 10},
    "Team win first half": {"home": 20, "away": 50},
    "Team draw at half time": {"home": 30, "away": 30},
    "Team lost first half": {"home": 50, "away": 20},
    "Both Teams to Score": {"home": 60, "away": 60},
    "BTTS in first-half": {"home": 30, "away": 30},
    "Win and BTTS": {"home": 10, "away": 20},
    "Draw and BTTS": {"home": 30, "away": 40},
    "Lose and BTTS": {"home": 20, "away": 0},
    "Match total goals 0": {"home": 10, "away": 0},
    "Match total goals 1": {"home": 10, "away": 10},
    "Match total goals 2": {"home": 30, "away": 50},
    "Match total goals 3": {"home": 10, "away": 10},
    "Match total goals 4": {"home": 30, "away": 10},
    "Under 1.5 goals": {"home": 20, "away": 10},
    "Over 2.5 goals": {"home": 50, "away": 40},
    "Over 3.5 goals": {"home": 40, "away": 30},
    "Under 3.5 goals": {"home": 60, "away": 70},
    "Over 0.5 goals at half-time": {"home": 80, "away": 80},
    "Over 1.5 goals at half-time": {"home": 40, "away": 30},
    "Over 2.5 goals at half-time": {"home": 20, "away": 20},
}


def test_ft_display_share_is_renormalized_inside_returned_top_three():
    picks = rank_exact_scores_ft(WSG_STURM, limit=3)

    assert [pick.score for pick in picks] == ["1:1", "0:2", "2:2"]
    assert 99.9 <= sum(pick.model_share for pick in picks) <= 100.1
    assert picks[0].model_share > 40.0
    assert [pick.raw_score for pick in picks] == [4.57, 3.63, 3.91]


def test_ft_diagnostics_describe_display_normalization_scope():
    selection = ft_profile_diagnostics(WSG_STURM)["selection"]

    assert selection["goal_totals"] == [2, 4, 5]
    assert selection["retained_high_tail_alternatives"] is True
    assert selection["model_share_scope"] == "renormalized_within_displayed_ft_top_scores"
