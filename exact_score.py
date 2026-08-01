from __future__ import annotations

from exact_score_v2 import *
from exact_score_v2 import _ft_total_distribution
import exact_score_v2 as _impl


def _ht_outcome_targets(stats):
    home, draw, away = _impl._ht_outcomes(stats)
    return {"home": home, "draw": draw, "away": away}


def _score_outcome(score: str) -> str:
    home, away = (int(value) for value in score.split(":"))
    return "home" if home > away else "draw" if home == away else "away"


def _post_calibration_factor(score: str, stats) -> float:
    targets = _ht_outcome_targets(stats)
    maximum = max(targets.values()) or 1.0
    ordered = sorted(targets.values(), reverse=True)
    outcome = _score_outcome(score)
    factor = max(0.20, targets[outcome] / maximum) ** 0.85

    # A clear HT leader should dominate exact directional scores, while draw
    # remains available but no longer receives an automatic free pass.
    if ordered[0] - ordered[1] >= 7.5:
        leader = max(targets, key=targets.get)
        if outcome == leader:
            factor *= 1.20
        elif outcome == "draw":
            factor *= 0.85

    home, away = (int(value) for value in score.split(":"))
    is_btts = home > 0 and away > 0
    btts_target = _impl._clamp(_impl._mean_metric(stats, "BTTS in first-half")) / 100.0
    class_target = btts_target if is_btts else 1.0 - btts_target
    factor *= max(0.25, class_target / 0.50) ** 0.35
    return factor


def rank_exact_scores_ht(stats, limit: int = 3):
    full = _impl.rank_exact_scores_ht(stats, limit=25)
    reranked = [
        (pick.score, max(0.0, pick.raw_score / 100.0) * _post_calibration_factor(pick.score, stats))
        for pick in full
    ]
    return _impl._normalize_top(reranked, limit)


def exact_score_diagnostics(stats, limit: int = 3):
    return {
        "ht": [pick.to_dict() for pick in rank_exact_scores_ht(stats, limit)],
        "ft": [pick.to_dict() for pick in rank_exact_scores_ft(stats, limit)],
    }
