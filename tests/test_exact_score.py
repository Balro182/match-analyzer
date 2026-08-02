from exact_score import exact_score_diagnostics, ft_profile_diagnostics, ht_profile_diagnostics, rank_exact_scores_ft, rank_exact_scores_ht


STATS = {
    "Goals scored per game": {"home": 1.3, "away": 1.5},
    "Goals conceded per game": {"home": 1.2, "away": 1.0},
    "Win": {"home": 50, "away": 40}, "Draw": {"home": 20, "away": 40}, "Lose": {"home": 30, "away": 20},
    "Team win first half": {"home": 20, "away": 50}, "Team draw at half time": {"home": 50, "away": 30}, "Team lost first half": {"home": 30, "away": 20},
    "Both Teams to Score": {"home": 70, "away": 70}, "BTTS in first-half": {"home": 10, "away": 20},
    "Win and BTTS": {"home": 40, "away": 20}, "Draw and BTTS": {"home": 20, "away": 40}, "Lose and BTTS": {"home": 10, "away": 10},
    "Match total goals 0": {"home": 0, "away": 0}, "Match total goals 1": {"home": 20, "away": 20},
    "Match total goals 2": {"home": 30, "away": 40}, "Match total goals 3": {"home": 40, "away": 20}, "Match total goals 4": {"home": 0, "away": 10},
    "Under 1.5 goals": {"home": 20, "away": 20}, "Under 3.5 goals": {"home": 90, "away": 80},
    "Over 0.5 goals at half-time": {"home": 60, "away": 80}, "Over 1.5 goals at half-time": {"home": 30, "away": 40}, "Over 2.5 goals at half-time": {"home": 0, "away": 10},
}

TURKU_MARIEHAMN = {
    "Goals scored per game": {"home": 1.8, "away": 1.1}, "Goals conceded per game": {"home": 0.9, "away": 2.0},
    "Team win first half": {"home": 40, "away": 10}, "Team draw at half time": {"home": 30, "away": 30}, "Team lost first half": {"home": 30, "away": 60},
    "BTTS in first-half": {"home": 20, "away": 0}, "Over 0.5 goals at half-time": {"home": 70, "away": 70},
    "Over 1.5 goals at half-time": {"home": 30, "away": 30}, "Over 2.5 goals at half-time": {"home": 30, "away": 10},
}

WIECZYSTA_LECH = {
    "Goals scored per game": {"home": 1.5, "away": 1.8}, "Goals conceded per game": {"home": 1.4, "away": 0.7},
    "Win": {"home": 40, "away": 80}, "Draw": {"home": 20, "away": 10}, "Lose": {"home": 40, "away": 10},
    "Team win first half": {"home": 20, "away": 80}, "Team draw at half time": {"home": 70, "away": 20}, "Team lost first half": {"home": 10, "away": 0},
    "Both Teams to Score": {"home": 60, "away": 60}, "BTTS in first-half": {"home": 40, "away": 20},
    "Win and BTTS": {"home": 40, "away": 60}, "Draw and BTTS": {"home": 20, "away": 10}, "Lose and BTTS": {"home": 20, "away": 10},
    "Team scored twice": {"home": 60, "away": 60}, "Clean sheets": {"home": 20, "away": 40}, "Team scored": {"home": 80, "away": 90},
    "Match total goals 0": {"home": 0, "away": 10}, "Match total goals 1": {"home": 20, "away": 20},
    "Match total goals 2": {"home": 30, "away": 10}, "Match total goals 3": {"home": 20, "away": 40}, "Match total goals 4": {"home": 10, "away": 10},
    "Under 1.5 goals": {"home": 20, "away": 10}, "Under 3.5 goals": {"home": 70, "away": 80},
    "Over 0.5 goals at half-time": {"home": 50, "away": 90}, "Over 1.5 goals at half-time": {"home": 40, "away": 60}, "Over 2.5 goals at half-time": {"home": 20, "away": 10},
}

WISLA_WIDZEW = {
    "Goals scored per game": {"home": 1.5, "away": 0.5}, "Goals conceded per game": {"home": 1.1, "away": 0.8},
    "Win": {"home": 50, "away": 10}, "Draw": {"home": 20, "away": 40}, "Lose": {"home": 30, "away": 50},
    "Team win first half": {"home": 60, "away": 10}, "Team draw at half time": {"home": 30, "away": 70}, "Team lost first half": {"home": 10, "away": 20},
    "Both Teams to Score": {"home": 30, "away": 30}, "BTTS in first-half": {"home": 0, "away": 0},
    "Win and BTTS": {"home": 20, "away": 0}, "Draw and BTTS": {"home": 10, "away": 20}, "Lose and BTTS": {"home": 0, "away": 10},
    "Team scored twice": {"home": 60, "away": 10}, "Clean sheets": {"home": 40, "away": 30}, "Team scored": {"home": 60, "away": 40},
    "Match total goals 0": {"home": 10, "away": 20}, "Match total goals 1": {"home": 20, "away": 40},
    "Match total goals 2": {"home": 10, "away": 30}, "Match total goals 3": {"home": 30, "away": 10}, "Match total goals 4": {"home": 20, "away": 0},
    "Under 1.5 goals": {"home": 30, "away": 60}, "Under 3.5 goals": {"home": 70, "away": 100},
    "Over 0.5 goals at half-time": {"home": 70, "away": 30}, "Over 1.5 goals at half-time": {"home": 20, "away": 0}, "Over 2.5 goals at half-time": {"home": 10, "away": 0},
}


def test_ht_ranking_uses_only_dominant_one_goal_class():
    picks = rank_exact_scores_ht(STATS)
    assert ht_profile_diagnostics(STATS)["selection"]["goal_bucket"] == "1"
    assert [pick.score for pick in picks] == ["0:1", "1:0"]
    assert 99.9 <= sum(pick.model_share for pick in picks) <= 100.1


def test_ht_ranking_preserves_home_direction_inside_selected_class():
    assert [pick.score for pick in rank_exact_scores_ht(TURKU_MARIEHAMN, limit=5)] == ["1:0", "0:1"]


def test_ft_ranking_uses_dominant_total_and_valid_ht_paths():
    picks = rank_exact_scores_ft(WIECZYSTA_LECH, limit=5)
    scores = [pick.score for pick in picks]
    profile = ft_profile_diagnostics(WIECZYSTA_LECH)["selection"]
    assert profile["goal_total"] == 3
    assert profile["goal_totals"] == [3]
    assert profile["retained_zero_goal_alternative"] is False
    assert scores[0] == "1:2"
    assert "0:3" in scores and "1:3" not in scores
    assert all(sum(map(int, score.split(":"))) == 3 for score in scores)
    assert 99.9 <= sum(pick.model_share for pick in picks) <= 100.1


def test_ft_ranking_keeps_existing_two_goal_profile_consistent():
    picks = rank_exact_scores_ft(STATS)
    assert ft_profile_diagnostics(STATS)["selection"]["goal_totals"] == [2]
    assert picks[0].score == "1:1"
    assert {pick.score for pick in picks} == {"1:1", "2:0", "0:2"}


def test_ft_ranking_retains_zero_zero_in_low_total_spread():
    picks = rank_exact_scores_ft(WISLA_WIDZEW, limit=3)
    scores = [pick.score for pick in picks]
    profile = ft_profile_diagnostics(WISLA_WIDZEW)["selection"]

    assert ht_profile_diagnostics(WISLA_WIDZEW)["selection"]["goal_bucket"] == "0"
    assert profile["goal_total"] == 1
    assert profile["goal_totals"] == [0, 1]
    assert profile["retained_zero_goal_alternative"] is True
    assert set(scores) == {"0:0", "1:0", "0:1"}
    assert scores[0] == "1:0"
    assert 99.9 <= sum(pick.model_share for pick in picks) <= 100.1


def test_diagnostics_include_ht_and_ft_selection_profiles():
    result = exact_score_diagnostics(STATS)
    assert set(result) == {"ht", "ft", "ht_profile", "ft_profile"}
    assert set(result["ht_profile"]) == {"total_goals", "btts", "outcome", "selection"}
    assert set(result["ft_profile"]) == {"total_goals", "selection"}
