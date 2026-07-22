import json

import engine_core
import storage
from decisions import prepare_recommendation
from settlement import settle_recommendations


def recommendation(**overrides):
    value = {
        "rule_id": "over15",
        "label": "Powyżej 1,5 gola",
        "score": 110.0,
        "passed": True,
        "reasons": [],
        "data_quality": 100.0,
        "raw_value": 80.0,
        "threshold": 75.0,
        "mode": "mean",
    }
    value.update(overrides)
    return value


def test_settlement_uses_frozen_recommended_not_passed():
    rec = recommendation(recommended=False, eligible=False)
    rows = settle_recommendations([rec], 2, 1)

    assert rows[0]["actual"] is True
    assert rows[0]["predicted"] is False
    assert rows[0]["result"] == "brak typu"
    assert rows[0]["outcome_class"] == "FALSE_NEGATIVE"


def test_legacy_settlement_applies_score_and_quality_policy():
    rec = recommendation(score=99.0, passed=True)
    rows = settle_recommendations([rec], 2, 1, minimum_score=100, minimum_quality=100)

    assert rows[0]["predicted"] is False
    assert rows[0]["result"] == "brak typu"


def test_prepare_recommendation_freezes_policy():
    prepared = prepare_recommendation(
        recommendation(score=104.0),
        minimum_score=100,
        minimum_quality=100,
        require_passed=True,
    )

    assert prepared["eligible"] is True
    assert prepared["recommended"] is True
    assert prepared["status"] == "BORDERLINE"
    assert prepared["decision_policy"]["minimum_score"] == 100.0


def test_reprocess_creates_immutable_evaluation_run(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "predictions.db")
    storage.init_db()

    snapshot = {
        "match": {
            "match_date": "2026-07-22",
            "home_team": "A",
            "away_team": "B",
            "url": "https://example.test/a-b",
            "stats": {"Over 1.5 goals": {"home": 80, "away": 80}},
        },
        "recommendations": [recommendation()],
        "minimum_score": 100,
        "minimum_data_quality": 100,
        "require_passed": True,
        "algorithm_version": "legacy-1",
        "config_version": "legacy-config",
    }
    ok, _ = storage.save_match(snapshot)
    assert ok is True
    row = storage.list_matches()[0]

    original_settlement = settle_recommendations(
        json.loads(row["snapshot_json"])["recommendations"], 2, 0
    )
    storage.settle_match(row["id"], 2, 0, None, None, original_settlement)
    before = storage.list_matches("rozliczony")[0]

    monkeypatch.setattr(
        storage,
        "analyze_match",
        lambda match, config: [
            engine_core.Recommendation(
                "over15", "Powyżej 1,5 gola", 120.0, True, ["current"], 100.0, 80.0, 75.0, "mean"
            )
        ],
    )
    config = {
        "recommendations": {
            "min_score": 100,
            "min_data_quality": 100,
            "rules": [],
        }
    }
    ok, message = storage.reprocess_match(row["id"], config)

    assert ok is True
    assert "Oryginalna historia nie została zmieniona" in message
    after = storage.list_matches("rozliczony")[0]
    assert after["settlement_json"] == before["settlement_json"]
    assert after["algorithm_version"] == "legacy-1"

    runs = storage.list_evaluation_runs(row["id"])
    assert len(runs) == 1
    assert runs[0]["algorithm_version"] == storage.ALGORITHM_VERSION
    run_settlement = json.loads(runs[0]["settlement_json"])
    assert run_settlement[0]["predicted"] is True
    assert run_settlement[0]["result"] == "trafiona"
