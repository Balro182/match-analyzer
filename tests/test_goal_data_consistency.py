from engine import analyze_match


def config(rule_id: str, metric: str, threshold: float):
    return {
        "recommendations": {
            "min_score": 0,
            "min_data_quality": 0,
            "selection": {"enabled": False},
            "btts_no": {"enabled": False},
            "rules": [{
                "id": rule_id,
                "label": rule_id,
                "enabled": True,
                "mode": "mean",
                "conditions": [{
                    "metric": metric,
                    "operator": ">=",
                    "threshold_home": threshold,
                    "threshold_away": threshold,
                }],
            }],
        }
    }


def test_source_four_plus_is_replaced_by_under35_complement():
    match = {"stats": {
        "Under 3.5 goals": {"home": 70, "away": 80},
        "Match total goals 4+": {"home": 0, "away": 0},
    }}
    result = analyze_match(match, config("total4plus", "Match total goals 4+", 20))[0]
    assert result.raw_value == 25
    assert result.passed is True
    assert any("źródłowe 4+" in reason for reason in result.reasons)


def test_exact_four_is_capped_by_canonical_four_plus():
    match = {"stats": {
        "Under 3.5 goals": {"home": 90, "away": 80},
        "Match total goals 4": {"home": 60, "away": 30},
    }}
    result = analyze_match(match, config("total4", "Match total goals 4", 10))[0]
    assert result.raw_value == 15
    assert any("ograniczono" in reason for reason in result.reasons)


def test_missing_distribution_data_does_not_penalize_regular_market():
    match = {"stats": {"Over 2.5 goals": {"home": 80, "away": 80}}}
    result = analyze_match(match, config("over25", "Over 2.5 goals", 67.5))[0]
    assert result.passed is True
    assert result.data_quality == 100
