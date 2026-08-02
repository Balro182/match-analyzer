from exact_score import ht_profile_diagnostics, rank_exact_scores_ht


WIECZYSTA_LECH = {
    "Goals scored per game": {"home": 1.50, "away": 1.80},
    "Goals conceded per game": {"home": 1.40, "away": 0.70},
    "Team win first half": {"home": 20, "away": 80},
    "Team draw at half time": {"home": 70, "away": 20},
    "Team lost first half": {"home": 10, "away": 0},
    "BTTS in first-half": {"home": 40, "away": 20},
    "Over 0.5 goals at half-time": {"home": 50, "away": 90},
    "Over 1.5 goals at half-time": {"home": 40, "away": 60},
    "Over 2.5 goals at half-time": {"home": 20, "away": 10},
}


def test_dominant_two_goal_class_excludes_other_goal_counts():
    picks = rank_exact_scores_ht(WIECZYSTA_LECH, limit=5)
    scores = [pick.score for pick in picks]

    assert scores == ["0:2", "1:1", "2:0"]
    assert all(sum(int(value) for value in score.split(":")) == 2 for score in scores)
    assert "0:0" not in scores
    assert "0:1" not in scores


def test_selected_class_shares_are_conditional_and_raw_scores_are_absolute():
    picks = rank_exact_scores_ht(WIECZYSTA_LECH, limit=5)

    assert 99.9 <= sum(pick.model_share for pick in picks) <= 100.1
    assert 32.5 <= sum(pick.raw_score for pick in picks) <= 37.5
    assert picks[0].score == "0:2"
    assert picks[0].model_share > 50.0


def test_ipf_preserves_goal_and_btts_margins():
    profile = ht_profile_diagnostics(WIECZYSTA_LECH)
    totals = profile["total_goals"]

    assert abs(totals["0"] - 30.0) <= 2.5
    assert abs(totals["1"] - 20.0) <= 2.5
    assert abs(totals["2"] - 35.0) <= 2.5
    assert abs(totals["3+"] - 15.0) <= 2.5
    assert abs((totals["2"] + totals["3+"]) - 50.0) <= 2.5
    assert abs(profile["btts"]["yes"] - 30.0) <= 2.5


def test_profile_reports_selected_goal_class_and_scope():
    profile = ht_profile_diagnostics(WIECZYSTA_LECH)

    assert profile["selection"]["goal_bucket"] == "2"
    assert profile["selection"]["goal_buckets"] == ["2"]
    assert abs(profile["selection"]["bucket_share"] - 35.0) <= 2.5
    assert profile["selection"]["model_share_scope"] == "conditional_within_selected_goal_buckets"


def test_outcome_is_soft_not_forced_to_raw_average():
    profile = ht_profile_diagnostics(WIECZYSTA_LECH)
    outcome = profile["outcome"]

    assert outcome["away"] > outcome["home"]
    assert abs(outcome["draw"] - 42.9) > 0.1
