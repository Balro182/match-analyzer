from exact_score import ft_profile_diagnostics, ht_profile_diagnostics, rank_exact_scores_ft, rank_exact_scores_ht


PIAST_WISLA = {
    "Goals scored per game": {"home": 1.6, "away": 1.2},
    "Goals conceded per game": {"home": 1.7, "away": 1.4},
    "Clean sheets": {"home": 20, "away": 20},
    "Team scored": {"home": 70, "away": 90},
    "Team scored twice": {"home": 40, "away": 20},
    "Win": {"home": 40, "away": 20},
    "Draw": {"home": 20, "away": 60},
    "Lose": {"home": 40, "away": 20},
    "Team win first half": {"home": 30, "away": 10},
    "Team draw at half time": {"home": 50, "away": 50},
    "Team lost first half": {"home": 20, "away": 40},
    "Both Teams to Score": {"home": 60, "away": 80},
    "BTTS in first-half": {"home": 30, "away": 30},
    "Win and BTTS": {"home": 30, "away": 10},
    "Draw and BTTS": {"home": 10, "away": 50},
    "Lose and BTTS": {"home": 20, "away": 20},
    "Match total goals 0": {"home": 10, "away": 10},
    "Match total goals 1": {"home": 10, "away": 10},
    "Match total goals 2": {"home": 20, "away": 50},
    "Match total goals 3": {"home": 0, "away": 10},
    "Match total goals 4": {"home": 40, "away": 0},
    "Under 1.5 goals": {"home": 20, "away": 20},
    "Over 2.5 goals": {"home": 60, "away": 30},
    "Over 3.5 goals": {"home": 60, "away": 20},
    "Under 3.5 goals": {"home": 40, "away": 80},
    "Over 0.5 goals at half-time": {"home": 70, "away": 70},
    "Over 1.5 goals at half-time": {"home": 50, "away": 30},
    "Over 2.5 goals at half-time": {"home": 20, "away": 10},
}


def test_flat_ht_distribution_keeps_actual_two_one_available():
    profile = ht_profile_diagnostics(PIAST_WISLA)["selection"]
    scores = [pick.score for pick in rank_exact_scores_ht(PIAST_WISLA, limit=25)]

    assert profile["goal_bucket"] == "0"
    assert profile["goal_buckets"] == ["0", "1", "2", "3+"]
    assert profile["retained_flat_distribution_alternatives"] is True
    assert "2:1" in scores


def test_strong_high_tail_keeps_extended_ft_scores_available():
    profile = ft_profile_diagnostics(PIAST_WISLA)["selection"]
    scores = [pick.score for pick in rank_exact_scores_ft(PIAST_WISLA, limit=100)]

    assert profile["goal_total"] == 2
    assert profile["goal_totals"] == [2, 4, 5]
    assert profile["high_tail_share"] == 40.0
    assert profile["retained_high_tail_alternatives"] is True
    assert profile["extended_ft_score_grid"] is True
    assert "2:2" in scores
    assert "3:2" in scores
    assert "4:3" in scores
