from exact_score import ht_profile_diagnostics, rank_exact_scores_ht


ZNICZ_LEGIA_II = {
    "Goals scored per game": {"home": 1.8, "away": 1.2},
    "Goals conceded per game": {"home": 2.1, "away": 1.1},
    "Team win first half": {"home": 30, "away": 30},
    "Team draw at half time": {"home": 40, "away": 40},
    "Team lost first half": {"home": 30, "away": 30},
    "BTTS in first-half": {"home": 40, "away": 10},
    "Over 0.5 goals at half-time": {"home": 70, "away": 70},
    "Over 1.5 goals at half-time": {"home": 50, "away": 10},
    "Over 2.5 goals at half-time": {"home": 30, "away": 0},
}


STRONG_ONE_GOAL = {
    "Goals scored per game": {"home": 1.4, "away": 1.0},
    "Goals conceded per game": {"home": 0.9, "away": 1.3},
    "Team win first half": {"home": 40, "away": 20},
    "Team draw at half time": {"home": 30, "away": 40},
    "Team lost first half": {"home": 30, "away": 40},
    "BTTS in first-half": {"home": 10, "away": 10},
    "Over 0.5 goals at half-time": {"home": 80, "away": 80},
    "Over 1.5 goals at half-time": {"home": 20, "away": 20},
    "Over 2.5 goals at half-time": {"home": 0, "away": 0},
}


def test_close_ht_total_keeps_draw_bucket_when_draw_is_dominant():
    picks = rank_exact_scores_ht(ZNICZ_LEGIA_II, limit=3)
    scores = [pick.score for pick in picks]
    selection = ht_profile_diagnostics(ZNICZ_LEGIA_II)["selection"]

    assert selection["goal_bucket"] == "1"
    assert selection["goal_buckets"] == ["0", "1"]
    assert selection["dominant_observed_outcome"] == "draw"
    assert selection["retained_outcome_conflict_alternatives"] is True
    assert set(scores) == {"0:0", "1:0", "0:1"}
    assert 99.9 <= sum(pick.model_share for pick in picks) <= 100.1


def test_clear_total_margin_keeps_hard_single_bucket_filter():
    picks = rank_exact_scores_ht(STRONG_ONE_GOAL, limit=5)
    selection = ht_profile_diagnostics(STRONG_ONE_GOAL)["selection"]

    assert selection["goal_bucket"] == "1"
    assert selection["goal_buckets"] == ["1"]
    assert selection["retained_outcome_conflict_alternatives"] is False
    assert {pick.score for pick in picks} == {"1:0", "0:1"}
