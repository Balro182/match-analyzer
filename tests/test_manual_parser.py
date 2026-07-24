from manual_parser import parse_pasted_stats


def test_parses_home_and_away_values_around_metric() -> None:
    parsed = parse_pasted_stats(
        """
        Main Stats
        Home Team
        Last 10 games home
        Away Team
        Last 10 games away
        1.90    Goals scored per game    1.50
        40.00%  Clean sheets  20.00%
        60.00%  Win  30.00%
        """,
        required_metrics=("Goals scored per game", "Clean sheets", "Win"),
    )

    assert parsed.stats["Goals scored per game"] == {"home": 1.9, "away": 1.5}
    assert parsed.stats["Clean sheets"] == {"home": 40.0, "away": 20.0}
    assert parsed.stats["Win"] == {"home": 60.0, "away": 30.0}
    assert parsed.missing_metrics == []


def test_prefers_long_metric_name_over_win_fragment() -> None:
    parsed = parse_pasted_stats(
        "50.00% Win and Over 1.5 goals 30.00%",
        required_metrics=("Win and Over 1.5 goals",),
    )

    assert parsed.stats == {
        "Win and Over 1.5 goals": {"home": 50.0, "away": 30.0}
    }


def test_reports_missing_and_duplicate_metrics() -> None:
    parsed = parse_pasted_stats(
        "60% Win 30%\n70% Win 20%",
        required_metrics=("Win", "Draw"),
    )

    assert parsed.stats["Win"] == {"home": 70.0, "away": 20.0}
    assert parsed.duplicate_metrics == ["Win"]
    assert parsed.missing_metrics == ["Draw"]
