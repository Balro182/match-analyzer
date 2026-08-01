from engine import ALGORITHM_VERSION, analyze_match_report, evaluate_rule


def btts_no_rule():
    return {
        "id": "btts_no",
        "label": "BTTS NIE",
        "mode": "special",
        "conditions": [{
            "maximum_btts": 40,
            "maximum_weak_team_scored": 50,
            "maximum_weak_goals": 0.9,
            "minimum_opponent_clean_sheets": 35,
            "maximum_opponent_conceded": 1.1,
            "minimum_under25": 60,
        }],
    }


def defensive_stats():
    return {
        "Both Teams to Score": {"home": 30, "away": 30},
        "Team scored": {"home": 80, "away": 40},
        "Under 2.5 goals": {"home": 70, "away": 90},
        "Goals scored per game": {"home": 1.5, "away": 0.5},
        "Goals conceded per game": {"home": 1.1, "away": 0.8},
        "Clean sheets": {"home": 40, "away": 30},
    }


def test_btts_no_accepts_low_btts_with_weak_attack_and_defensive_support():
    result = evaluate_rule(defensive_stats(), btts_no_rule())
    assert result.passed is True
    assert result.raw_value == 70.0
    assert any("Słaba ofensywa B" in reason for reason in result.reasons)


def test_btts_no_is_not_plain_negation_of_failed_btts_yes():
    stats = defensive_stats()
    stats["Under 2.5 goals"] = {"home": 40, "away": 40}
    result = evaluate_rule(stats, btts_no_rule())
    assert result.passed is False


def test_report_contains_machine_readable_selection_telemetry():
    config = {
        "recommendations": {
            "min_score": 100,
            "min_data_quality": 100,
            "selection": {
                "enabled": True,
                "max_recommendations": 5,
                "max_main_recommendations": 3,
                "max_additional_signals": 2,
                "max_per_category": 1,
                "minimum_half_outcome_lead": 7.5,
                "independence_penalty_per_shared_tag": 0.12,
                "main_min_adjusted_score": 90,
                "additional_min_adjusted_score": 82,
                "point_totals_main_allowed": False,
            },
            "btts_no": {"enabled": True},
            "rules": [],
        }
    }
    report = analyze_match_report({"stats": defensive_stats()}, config)
    assert report["algorithm_version"] == ALGORITHM_VERSION
    assert report["telemetry"]
    row = report["telemetry"][0]
    assert row["rule_id"] == "btts_no"
    assert row["threshold_margin"] == 10.0
    assert row["selected_level"] in {"main", "additional", "rejected"}
