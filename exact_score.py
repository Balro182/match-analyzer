from __future__ import annotations

from exact_score_v2 import *
from exact_score_v2 import _ft_total_distribution
import exact_score_v2 as _impl


def _score_tuple(score: str) -> tuple[int, int]:
    return tuple(int(value) for value in score.split(":"))


def _score_outcome(score: str) -> str:
    home, away = _score_tuple(score)
    return "home" if home > away else "draw" if home == away else "away"


def _total_bucket(score: str) -> str:
    total = sum(_score_tuple(score))
    return str(total) if total < 3 else "3+"


def _normalize_matrix(matrix: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, value) for value in matrix.values())
    if total <= 0:
        return matrix
    return {score: max(0.0, value) / total for score, value in matrix.items()}


def _scale_group(
    matrix: dict[str, float],
    classifier,
    target: dict[str, float],
) -> dict[str, float]:
    current = {
        key: sum(value for score, value in matrix.items() if classifier(score) == key)
        for key in target
    }
    scaled = dict(matrix)
    for score, value in matrix.items():
        key = classifier(score)
        if key not in target:
            continue
        denominator = current.get(key, 0.0)
        factor = target[key] / denominator if denominator > 1e-12 else 1.0
        scaled[score] = value * factor
    return _normalize_matrix(scaled)


def _target_total_buckets(stats) -> dict[str, float]:
    totals = _impl._ht_total_distribution(stats)
    return {
        "0": totals.get(0, 0.0) / 100.0,
        "1": totals.get(1, 0.0) / 100.0,
        "2": totals.get(2, 0.0) / 100.0,
        "3+": totals.get(3, 0.0) / 100.0,
    }


def _target_btts(stats) -> dict[str, float]:
    yes = _impl._clamp(_impl._mean_metric(stats, "BTTS in first-half")) / 100.0
    return {"yes": yes, "no": 1.0 - yes}


def _btts_class(score: str) -> str:
    home, away = _score_tuple(score)
    return "yes" if home > 0 and away > 0 else "no"


def _soft_outcome_targets(matrix: dict[str, float], stats) -> dict[str, float]:
    observed_home, observed_draw, observed_away = _impl._ht_outcomes(stats)
    observed = {
        "home": observed_home / 100.0,
        "draw": observed_draw / 100.0,
        "away": observed_away / 100.0,
    }
    base = {
        key: sum(value for score, value in matrix.items() if _score_outcome(score) == key)
        for key in observed
    }
    # A/X/B remains a soft constraint: 35% observed history, 65% Poisson base.
    blended = {key: 0.65 * base[key] + 0.35 * observed[key] for key in observed}
    total = sum(blended.values()) or 1.0
    return {key: value / total for key, value in blended.items()}


def _ipf_ht_matrix(stats, iterations: int = 60) -> dict[str, float]:
    base_picks = _impl.rank_exact_scores_ht(stats, limit=25)
    matrix = _normalize_matrix({pick.score: max(0.0, pick.raw_score) / 100.0 for pick in base_picks})
    total_targets = _target_total_buckets(stats)
    btts_targets = _target_btts(stats)
    outcome_targets = _soft_outcome_targets(matrix, stats)

    for _ in range(iterations):
        matrix = _scale_group(matrix, _total_bucket, total_targets)
        matrix = _scale_group(matrix, _btts_class, btts_targets)
        matrix = _scale_group(matrix, _score_outcome, outcome_targets)

    return _normalize_matrix(matrix)


def rank_exact_scores_ht(stats, limit: int = 3):
    matrix = _ipf_ht_matrix(stats)
    return _impl._normalize_top(list(matrix.items()), limit)


def ht_profile_diagnostics(stats) -> dict[str, dict[str, float]]:
    matrix = _ipf_ht_matrix(stats)
    totals = {
        key: round(sum(value for score, value in matrix.items() if _total_bucket(score) == key) * 100.0, 1)
        for key in ("0", "1", "2", "3+")
    }
    outcomes = {
        key: round(sum(value for score, value in matrix.items() if _score_outcome(score) == key) * 100.0, 1)
        for key in ("home", "draw", "away")
    }
    btts_yes = round(sum(value for score, value in matrix.items() if _btts_class(score) == "yes") * 100.0, 1)
    return {
        "total_goals": totals,
        "btts": {"yes": btts_yes, "no": round(100.0 - btts_yes, 1)},
        "outcome": outcomes,
    }


def exact_score_diagnostics(stats, limit: int = 3):
    return {
        "ht": [pick.to_dict() for pick in rank_exact_scores_ht(stats, limit)],
        "ft": [pick.to_dict() for pick in rank_exact_scores_ft(stats, limit)],
        "ht_profile": ht_profile_diagnostics(stats),
    }
