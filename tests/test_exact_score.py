from exact_score import exact_score_diagnostics, rank_exact_scores_ft, rank_exact_scores_ht


STATS = {
    "Goals scored per game": {"home": 1.3, "away": 1.5},
    "Goals conceded per game": {"home": 1.2, "away": 1.0},
    "Win": {"home": 50, "away": 40},
    "Draw": {"home": 20, "away": 40},
    "Lose": {"home": 30, "away": 20},
    "Team win first half": {"home": 20, "away": 50},
    "Team draw at half time": {"home": 50, "away": 30},
    "Team lost first half": {"home": 30, "away": 20},
    "Both Teams to Score": {"home": 70, "away": 70},
    "BTTS in first-half": {"home": 10, "away": 20},
    "Win and BTTS": {"home": 40, "away": 20},
    "Draw and BTTS": {"home": 20, "away": 40},
    "Lose and BTTS": {"home": 10, "away": 10},
    "Match total goals 0": {"home": 0, "away": 0},
    "Match total goals 1": {"home": 20, "away": 20},
    "Match total goals 2": {"home": 30, "away": 40},
    "Match total goals 3": {"home": 40, "away": 20},
    "Match total goals 4": {"home": 0, "away": 10},
    "Under 3.5 goals": {"home": 90, "away": 80},
    "Over 0.5 goals at half-time": {"home": 60, "away": 80},
    "Over 1.5 goals at half-time": {"home": 30, "away": 40},
    "Over 2.5 goals at half-time": {"home": 0, "away": 10},
}


TURKU_MARIEHAMN = {
    "Goals scored per game": {"home": 1.8, "away": 1.1},
    "Goals conceded per game": {"home": 0.9, "away": 2.0},
    "Team win first half": {"home": 40, "away": 10},
    "Team draw at half time": {"home": 30, "away": 30},
    "Team lost first half": {"home": 30, "away": 60},
    "BTTS in first-half": {"home": 20, "away": 0},
    "Over 0.5 goals at half-time": {"home": 70, "away": 70},
    "Over 1.5 goals at half-time": {"home": 30, "away": 30},
    "Over 2.5 goals at half-time": {"home": 30, "away": 10},
}


def test_ht_ranking_prefers_away_one_goal_profile():
    picks = rank_exact_scores_ht(STATS)
    assert len(picks) == 3
    assert picks[0].score == "0:1"
    assert 0 < sum(pick.model_share for pick in picks) < 100


def test_ht_ranking_does_not_promote_opposite_direction_for_clear_home_leader():
    picks = rank_exact_scores_ht(TURKU_MARIEHAMN)
    scores = [pick.score for pick in picks]
    assert scores[0] == "1:0"
    assert "0:1" not in scores
    assert "3:0" not in scores
    assert "2:0" in scores


def test_ft_ranking_prefers_one_one_profile():
    picks = rank_exact_scores_ft(STATS)
    assert len(picks) == 3
    assert picks[0].score == "1:1"
    assert {pick.score for pick in picks} == {"1:1", "2:1", "1:2"}
    assert 0 < sum(pick.model_share for pick in picks) < 100


def test_diagnostics_are_separate_from_betting_recommendations():
    result = exact_score_diagnostics(STATS)
    assert set(result) == {"ht", "ft"}
    assert all("model_share" in row for row in result["ht"] + result["ft"])
