from pathlib import Path

import pytest

from backtest_store import (
    aggregate_dashboard,
    export_csv,
    list_matches,
    recommendation_rows,
    save_analysis,
    settle_match,
)
from engine_core import Recommendation


def rec(rule_id: str, level: str, raw: float = 80, threshold: float = 70) -> Recommendation:
    reason = (
        "Poziom selekcji: główny typ; selection score 101.5"
        if level == "main"
        else "Poziom selekcji: dodatkowy sygnał; selection score 88.0"
    )
    return Recommendation(rule_id, rule_id, 110, True, [reason], 100, raw, threshold, "mean")


def match() -> dict:
    return {"home_team": "A", "away_team": "B", "stats": {"Win": {"home": 70, "away": 20}}}


def test_save_analysis_persists_match_and_telemetry(tmp_path: Path):
    db = tmp_path / "backtest.db"
    match_id = save_analysis(match(), [rec("home_win", "main")], "2.12.0", "1:0", "2:0", path=db)

    matches = list_matches(db)
    rows = recommendation_rows(db)

    assert matches[0]["id"] == match_id
    assert matches[0]["predicted_ht"] == "1:0"
    assert rows[0]["selected_level"] == "main"
    assert rows[0]["threshold_margin"] == 10
    assert rows[0]["selection_score"] == 101.5


def test_settle_match_grades_supported_markets_and_profit(tmp_path: Path):
    db = tmp_path / "backtest.db"
    recommendations = [
        rec("home_win", "main"), rec("under35", "main"), rec("goal_both_halves", "main"),
        rec("total3", "additional"), rec("btts_no", "additional"), rec("win_win", "additional"),
    ]
    match_id = save_analysis(match(), recommendations, "2.12.0", path=db)

    result = settle_match(
        match_id, "2:0", "3:0",
        {"home_win": 1.50, "under35": 1.40, "goal_both_halves": 1.60, "total3": 3.00, "btts_no": 1.70, "win_win": 2.00},
        db,
    )
    rows = {row["rule_id"]: row for row in recommendation_rows(db, selected_only=True)}

    assert result == {"settled": 6, "skipped": 0}
    assert all(row["hit"] == 1 for row in rows.values())
    assert rows["total3"]["profit"] == 2.0
    assert rows["home_win"]["profit"] == 0.5


def test_settlement_rejects_impossible_progression(tmp_path: Path):
    db = tmp_path / "backtest.db"
    match_id = save_analysis(match(), [rec("home_win", "main")], "2.12.0", path=db)
    with pytest.raises(ValueError, match="progresja"):
        settle_match(match_id, "0:1", "2:0", path=db)


def test_dashboard_groups_levels_scores_margins_and_roi(tmp_path: Path):
    db = tmp_path / "backtest.db"
    first = save_analysis(match(), [rec("home_win", "main", 80, 70)], "2.12.0", path=db)
    second = save_analysis(
        {"home_team": "C", "away_team": "D", "stats": {}},
        [rec("away_win", "additional", 71, 70)],
        "2.12.0",
        analyzed_at="2026-08-02T12:00:00+00:00",
        path=db,
    )
    settle_match(first, "1:0", "2:0", {"home_win": 2.0}, db)
    settle_match(second, "0:0", "1:0", {"away_win": 2.0}, db)

    dashboard = aggregate_dashboard(db)

    assert dashboard["overall"]["total"] == 2
    assert dashboard["overall"]["hits"] == 1
    assert dashboard["overall"]["hit_rate"] == 50.0
    assert dashboard["overall"]["roi"] == 0.0
    assert dashboard["by_level"]["main"]["hit_rate"] == 100.0
    assert dashboard["by_level"]["additional"]["hit_rate"] == 0.0
    assert "10+ pp" in dashboard["by_margin"]
    assert "0–2,5 pp" in dashboard["by_margin"]


def test_csv_export_contains_header_and_selected_rows(tmp_path: Path):
    db = tmp_path / "backtest.db"
    save_analysis(match(), [rec("home_win", "main")], "2.12.0", path=db)
    content = export_csv(db, selected_only=True).decode("utf-8-sig")
    assert "match_id" in content
    assert "home_win" in content
