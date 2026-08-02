from exact_score import ft_profile_diagnostics, rank_exact_scores_ft


SLASK_RAKOW = {
    "Goals scored per game": {"home": 2.3, "away": 1.8},
    "Goals conceded per game": {"home": 0.7, "away": 1.6},
    "Clean sheets": {"home": 50, "away": 10},
    "Team scored": {"home": 80, "away": 90},
    "Team scored twice": {"home": 70, "away": 50},
    "Win": {"home": 60, "away": 30},
    "Draw": {"home": 40, "away": 30},
    "Lose": {"home": 0, "away": 40},
    "Team win first half": {"home": 50, "away": 30},
    "Team draw at half time": {"home": 30, "away": 60},
    "Team lost first half": {"home": 20, "away": 10},
    "Both Teams to Score": {"home": 50, "away": 80},
    "BTTS in first-half": {"home": 10, "away": 30},
    "Win and BTTS": {"home": 30, "away": 20},
    "Draw and BTTS": {"home": 20, "away": 30},
    "Lose and BTTS": {"home": 0, "away": 30},
    "Match total goals 0": {"home": 20, "away": 0},
    "Match total goals 1": {"home": 10, "away": 0},
    "Match total goals 2": {"home": 0, "away": 40},
    "Match total goals 3": {"home": 20, "away": 20},
    "Match total goals 4": {"home": 30, "away": 20},
    "Under 1.5 goals": {"home": 30, "away": 0},
    "Over 2.5 goals": {"home": 70, "away": 60},
    "Over 3.5 goals": {"home": 50, "away": 40},
    "Under 3.5 goals": {"home": 50, "away": 60},
    "Over 0.5 goals at half-time": {"home": 70, "away": 70},
    "Over 1.5 goals at half-time": {"home": 40, "away": 50},
    "Over 2.5 goals at half-time": {"home": 10, "away": 30},
}


def test_close_three_and_four_goal_totals_are_both_retained():
    selection = ft_profile_diagnostics(SLASK_RAKOW)["selection"]
    scores = [pick.score for pick in rank_exact_scores_ft(SLASK_RAKOW, limit=10)]

    assert selection["goal_total"] == 4
    assert selection["goal_totals"] == [3, 4]
    assert selection["retained_adjacent_high_total_alternative"] is True
    assert selection["retained_high_tail_alternatives"] is False
    assert "2:1" in scores
    assert all(sum(int(value) for value in score.split(":")) in {3, 4} for score in scores)


def test_adjacent_high_total_requires_twenty_percent_support():
    weak_three = {key: dict(value) for key, value in SLASK_RAKOW.items()}
    weak_three["Match total goals 3"] = {"home": 10, "away": 20}

    selection = ft_profile_diagnostics(weak_three)["selection"]

    assert selection["goal_total"] == 4
    assert selection["goal_totals"] == [4]
    assert selection["retained_adjacent_high_total_alternative"] is False
