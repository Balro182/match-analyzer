from exact_score import ft_profile_diagnostics, rank_exact_scores_ft


STAL_TYCHY = {
    "Goals scored per game": {"home": 1.1, "away": 0.8},
    "Goals conceded per game": {"home": 1.0, "away": 1.2},
    "Win": {"home": 20, "away": 40}, "Draw": {"home": 50, "away": 20}, "Lose": {"home": 30, "away": 40},
    "Team win first half": {"home": 30, "away": 10}, "Team draw at half time": {"home": 50, "away": 50}, "Team lost first half": {"home": 20, "away": 40},
    "Both Teams to Score": {"home": 50, "away": 30}, "BTTS in first-half": {"home": 10, "away": 10},
    "Team scored twice": {"home": 40, "away": 20},
    "Match total goals 0": {"home": 20, "away": 10}, "Match total goals 1": {"home": 20, "away": 40},
    "Match total goals 2": {"home": 10, "away": 20}, "Match total goals 3": {"home": 30, "away": 10},
    "Match total goals 4": {"home": 20, "away": 10},
    "Under 1.5 goals": {"home": 40, "away": 50}, "Under 3.5 goals": {"home": 80, "away": 80},
    "Over 0.5 goals at half-time": {"home": 60, "away": 60},
    "Over 1.5 goals at half-time": {"home": 10, "away": 20},
    "Over 2.5 goals at half-time": {"home": 0, "away": 10},
}


def test_ft_spread_retains_close_three_goal_total_and_actual_score():
    profile = ft_profile_diagnostics(STAL_TYCHY)["selection"]
    picks = rank_exact_scores_ft(STAL_TYCHY, limit=8)
    scores = [pick.score for pick in picks]

    assert profile["goal_total"] == 1
    assert profile["goal_totals"] == [1, 3]
    assert profile["retained_close_total_alternatives"] is True
    assert "1:2" in scores
    assert "2:1" in scores
    assert all(sum(map(int, score.split(":"))) in {1, 3} for score in scores)


def test_ft_spread_does_not_change_hard_total_profiles():
    hard = dict(STAL_TYCHY)
    hard["Match total goals 1"] = {"home": 70, "away": 70}
    hard["Match total goals 3"] = {"home": 10, "away": 10}

    profile = ft_profile_diagnostics(hard)["selection"]
    assert profile["goal_totals"] == [1]
    assert profile["retained_close_total_alternatives"] is False
