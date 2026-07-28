from engine import _canonicalize_goal_totals
from exact_score import _ft_total_distribution


def stats_with_inconsistent_four_plus():
    return {
        "Match total goals 4": {"home": 30.0, "away": 30.0},
        "Match total goals 4+": {"home": 0.0, "away": 0.0},
        "Under 3.5 goals": {"home": 70.0, "away": 50.0},
    }


def test_engine_derives_four_plus_from_under35():
    normalized, warnings = _canonicalize_goal_totals(
        stats_with_inconsistent_four_plus()
    )

    assert normalized["Match total goals 4+"] == {
        "home": 30.0,
        "away": 50.0,
    }
    assert normalized["Match total goals 4"] == {
        "home": 30.0,
        "away": 30.0,
    }
    assert warnings


def test_exact_score_splits_exact_four_and_five_plus():
    totals = _ft_total_distribution(stats_with_inconsistent_four_plus())

    assert totals[4] == 30.0
    assert totals[5] == 10.0


def test_exact_four_is_capped_by_canonical_four_plus():
    stats = stats_with_inconsistent_four_plus()
    stats["Match total goals 4"] = {"home": 50.0, "away": 70.0}

    normalized, warnings = _canonicalize_goal_totals(stats)

    assert normalized["Match total goals 4"] == {
        "home": 30.0,
        "away": 50.0,
    }
    assert any("ograniczono" in warning for warning in warnings)
