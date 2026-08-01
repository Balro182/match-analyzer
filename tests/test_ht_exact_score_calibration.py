from exact_score import rank_exact_scores_ht


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


def test_asymmetric_ht_profile_does_not_overpromote_nil_nil():
    picks = rank_exact_scores_ht(WIECZYSTA_LECH, limit=5)
    scores = [pick.score for pick in picks]

    assert scores[0] == "0:1"
    assert "0:2" in scores[:3]
    assert scores.index("0:0") < scores.index("1:1")
    assert picks[scores.index("0:1")].model_share > picks[scores.index("0:0")].model_share


def test_ht_exact_score_distribution_is_normalized_beyond_top_three():
    picks = rank_exact_scores_ht(WIECZYSTA_LECH, limit=25)
    assert 99.0 <= sum(pick.model_share for pick in picks) <= 100.5
