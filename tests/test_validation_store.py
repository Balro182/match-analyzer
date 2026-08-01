from pathlib import Path

import pytest

import validation_store
from engine_core import Recommendation


def recommendation(rule_id: str = "home_win") -> Recommendation:
    return Recommendation(
        rule_id, rule_id, 110.0, True,
        ["Poziom selekcji: główny typ; selection score 101.5"],
        100.0, 80.0, 70.0, "mean",
    )


def test_sqlite_fallback_saves_prediction_odds_and_prevents_duplicate(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    db = tmp_path / "validation.db"
    match = {"home_team": "A", "away_team": "B", "stats": {}}

    match_id = validation_store.save_analysis(
        match, [recommendation()], "2.11.0", path=db,
        match_date="2026-08-01", odds_by_rule={"home_win": 1.8},
    )
    rows = validation_store.recommendation_rows(db, selected_only=True)

    assert validation_store.backend_name() == "SQLite (fallback)"
    assert rows[0]["match_id"] == match_id
    assert rows[0]["odds"] == 1.8

    with pytest.raises(ValueError, match="istnieje"):
        validation_store.save_analysis(
            match, [recommendation()], "2.11.0", path=db,
            match_date="2026-08-01",
        )


def test_return_existing_duplicate_policy(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    db = tmp_path / "validation.db"
    match = {"home_team": "A", "away_team": "B", "stats": {}}
    first = validation_store.save_analysis(match, [recommendation()], "2.11.0", path=db)
    second = validation_store.save_analysis(
        match, [recommendation()], "2.11.0", path=db,
        duplicate_policy="return_existing",
    )
    assert first == second


def test_settlement_reuses_prediction_odds(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    db = tmp_path / "validation.db"
    match_id = validation_store.save_analysis(
        {"home_team": "A", "away_team": "B", "stats": {}},
        [recommendation()], "2.11.0", path=db,
        odds_by_rule={"home_win": 2.0},
    )
    validation_store.settle_match(match_id, "1:0", "2:0", path=db)
    row = validation_store.recommendation_rows(db, selected_only=True)[0]
    assert row["hit"] == 1
    assert row["profit"] == 1.0
