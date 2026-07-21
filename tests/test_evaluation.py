from evaluation import (
    OUTCOME_FALSE_NEGATIVE,
    OUTCOME_FALSE_POSITIVE,
    OUTCOME_HIT,
    STATUS_BORDERLINE,
    STATUS_FORMAL,
    STATUS_LOW_DATA_QUALITY,
    STATUS_OBSERVATIONAL,
    build_evaluation_report,
    classify_outcome,
    enrich_recommendation,
    recommendation_status,
    score_bucket,
)
from settlement import settle_recommendations


def test_recommendation_statuses_are_unambiguous():
    assert recommendation_status({"passed": True, "score": 112, "data_quality": 100}) == STATUS_FORMAL
    assert recommendation_status({"passed": True, "score": 102, "data_quality": 100}) == STATUS_BORDERLINE
    assert recommendation_status({"passed": False, "score": 96, "data_quality": 100}) == STATUS_OBSERVATIONAL
    assert recommendation_status({"passed": True, "score": 120, "data_quality": 80}) == STATUS_LOW_DATA_QUALITY


def test_score_buckets_cover_calibration_ranges():
    assert score_bucket(99.9) == "<100"
    assert score_bucket(100) == "100–104"
    assert score_bucket(109.9) == "105–109"
    assert score_bucket(119.9) == "110–119"
    assert score_bucket(129.9) == "120–129"
    assert score_bucket(130) == "130+"


def test_outcome_classification_includes_false_negatives():
    assert classify_outcome(True, True) == OUTCOME_HIT
    assert classify_outcome(True, False) == OUTCOME_FALSE_POSITIVE
    assert classify_outcome(False, True) == OUTCOME_FALSE_NEGATIVE


def test_settlement_persists_status_buckets_and_outcome_class():
    recommendation = enrich_recommendation(
        {
            "rule_id": "over25",
            "label": "Powyżej 2,5 gola",
            "score": 108,
            "data_quality": 100,
            "passed": True,
        }
    )
    row = settle_recommendations([recommendation], 1, 1)[0]
    assert row["status"] == STATUS_FORMAL
    assert row["score_bucket"] == "105–109"
    assert row["quality_bucket"] == "100"
    assert row["outcome_class"] == OUTCOME_FALSE_POSITIVE


def test_evaluation_report_groups_market_score_quality_status_and_version():
    records = [
        {
            "label": "Under 3,5",
            "score": 112,
            "score_bucket": "110–119",
            "data_quality": 100,
            "quality_bucket": "100",
            "status": STATUS_FORMAL,
            "algorithm_version": "3.0.0",
            "league": "Test League",
            "predicted": True,
            "actual": True,
            "outcome_class": OUTCOME_HIT,
        },
        {
            "label": "Under 3,5",
            "score": 105,
            "score_bucket": "105–109",
            "data_quality": 100,
            "quality_bucket": "100",
            "status": STATUS_FORMAL,
            "algorithm_version": "3.0.0",
            "league": "Test League",
            "predicted": True,
            "actual": False,
            "outcome_class": OUTCOME_FALSE_POSITIVE,
        },
    ]
    report = build_evaluation_report(records)
    market = report["by_market"][0]
    assert market["recommendations"] == 2
    assert market["hits"] == 1
    assert market["misses"] == 1
    assert market["hit_rate"] == 50.0
    assert report["by_algorithm_version"][0]["algorithm_version"] == "3.0.0"
