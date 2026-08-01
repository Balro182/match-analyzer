from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial
from typing import Any


@dataclass(frozen=True)
class ExactScorePick:
    score: str
    model_share: float
    raw_score: float

    def to_dict(self) -> dict[str, Any]:
        return {"score": self.score, "model_share": self.model_share, "raw_score": self.raw_score}


def _metric(stats: dict[str, Any], name: str) -> tuple[float, float] | None:
    normalized = name.casefold().strip()
    for key, values in stats.items():
        if key.casefold().strip() != normalized:
            continue
        if isinstance(values, dict):
            return float(values["home"]), float(values["away"])
        return float(values[0]), float(values[1])
    return None


def _mean_metric(stats: dict[str, Any], name: str, default: float = 0.0) -> float:
    values = _metric(stats, name)
    return default if values is None else sum(values) / 2


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _normalize_top(items: list[tuple[str, float]], limit: int = 3) -> list[ExactScorePick]:
    ordered_all = sorted(items, key=lambda item: (item[1], item[0]), reverse=True)
    total = sum(max(0.0, value) for _, value in ordered_all)
    if total <= 0:
        return []
    return [
        ExactScorePick(
            score=score,
            model_share=round(max(0.0, value) / total * 100.0, 1),
            raw_score=round(value * 100.0, 2),
        )
        for score, value in ordered_all[:limit]
    ]


def is_valid_score_progression(ht_home: int, ht_away: int, ft_home: int, ft_away: int) -> bool:
    return min(ht_home, ht_away, ft_home, ft_away) >= 0 and ft_home >= ht_home and ft_away >= ht_away


def _poisson(goals: int, expected: float) -> float:
    return exp(-expected) * expected**goals / factorial(goals)


def _outcome_key(home_goals: int, away_goals: int) -> str:
    return "home" if home_goals > away_goals else "draw" if home_goals == away_goals else "away"


def _ft_total_distribution(stats: dict[str, Any]) -> dict[int, float]:
    exact = {goals: _mean_metric(stats, f"Match total goals {goals}") for goals in range(5)}
    canonical_four_plus = _clamp(100.0 - _mean_metric(stats, "Under 3.5 goals", 100.0))
    exact_four = min(exact[4], canonical_four_plus)
    exact[4] = exact_four
    exact[5] = max(0.0, canonical_four_plus - exact_four)
    return exact


def _ht_total_distribution(stats: dict[str, Any]) -> dict[int, float]:
    over05 = _clamp(_mean_metric(stats, "Over 0.5 goals at half-time"))
    over15 = min(over05, _clamp(_mean_metric(stats, "Over 1.5 goals at half-time")))
    over25 = min(over15, _clamp(_mean_metric(stats, "Over 2.5 goals at half-time")))
    return {
        0: 100.0 - over05,
        1: over05 - over15,
        2: over15 - over25,
        3: over25,
    }


def _ft_outcomes(stats: dict[str, Any]) -> tuple[float, float, float]:
    win = _metric(stats, "Win") or (0.0, 0.0)
    lose = _metric(stats, "Lose") or (0.0, 0.0)
    draw = _metric(stats, "Draw") or (0.0, 0.0)
    home, away, draw_value = (win[0] + lose[1]) / 2, (win[1] + lose[0]) / 2, sum(draw) / 2
    total = home + draw_value + away
    return (33.3, 33.4, 33.3) if total <= 0 else (home / total * 100, draw_value / total * 100, away / total * 100)


def _ht_outcomes(stats: dict[str, Any]) -> tuple[float, float, float]:
    win = _metric(stats, "Team win first half") or (0.0, 0.0)
    lose = _metric(stats, "Team lost first half") or (0.0, 0.0)
    draw = _metric(stats, "Team draw at half time") or (0.0, 0.0)
    home, away, draw_value = (win[0] + lose[1]) / 2, (win[1] + lose[0]) / 2, sum(draw) / 2
    total = home + draw_value + away
    return (33.3, 33.4, 33.3) if total <= 0 else (home / total * 100, draw_value / total * 100, away / total * 100)


def _fit_ht_total_lambda(stats: dict[str, Any]) -> float:
    targets = (
        _clamp(_mean_metric(stats, "Over 0.5 goals at half-time")) / 100.0,
        _clamp(_mean_metric(stats, "Over 1.5 goals at half-time")) / 100.0,
        _clamp(_mean_metric(stats, "Over 2.5 goals at half-time")) / 100.0,
    )
    if not any(targets):
        return 0.95

    best_error = float("inf")
    best_lambda = 0.95
    for step in range(20, 351):
        value = step / 100.0
        p0 = _poisson(0, value)
        p1 = _poisson(1, value)
        p2 = _poisson(2, value)
        predicted = (1.0 - p0, 1.0 - p0 - p1, 1.0 - p0 - p1 - p2)
        error = sum((actual - expected) ** 2 for actual, expected in zip(predicted, targets))
        if error < best_error:
            best_error, best_lambda = error, value
    return best_lambda


def _ht_team_lambdas(stats: dict[str, Any], total_lambda: float) -> tuple[float, float]:
    scored = _metric(stats, "Goals scored per game") or (1.0, 1.0)
    conceded = _metric(stats, "Goals conceded per game") or (1.0, 1.0)
    attack_home = max(0.05, (scored[0] + conceded[1]) / 2.0)
    attack_away = max(0.05, (scored[1] + conceded[0]) / 2.0)
    attack_total = attack_home + attack_away
    attack_home_share = attack_home / attack_total

    ht_home, _, ht_away = _ht_outcomes(stats)
    directional_total = ht_home + ht_away
    directional_home_share = attack_home_share if directional_total <= 0 else ht_home / directional_total

    # Team scoring strength remains primary, while directional HT history can
    # move the allocation enough to distinguish 0:1 from 0:0 in asymmetric games.
    home_share = 0.50 * attack_home_share + 0.50 * directional_home_share
    home_share = max(0.15, min(0.85, home_share))
    return total_lambda * home_share, total_lambda * (1.0 - home_share)


def _safe_ratio(target: float, current: float, floor: float = 0.20, ceiling: float = 5.0) -> float:
    if target <= 0:
        return floor
    return max(floor, min(ceiling, target / max(current, 1e-9)))


def rank_exact_scores_ht(stats: dict[str, Any], limit: int = 3) -> list[ExactScorePick]:
    total_lambda = _fit_ht_total_lambda(stats)
    home_lambda, away_lambda = _ht_team_lambdas(stats, total_lambda)
    target_totals = _ht_total_distribution(stats)
    home_outcome, draw_outcome, away_outcome = _ht_outcomes(stats)
    target_outcomes = {
        "home": home_outcome / 100.0,
        "draw": draw_outcome / 100.0,
        "away": away_outcome / 100.0,
    }
    target_btts = _clamp(_mean_metric(stats, "BTTS in first-half")) / 100.0

    base: dict[tuple[int, int], float] = {}
    for home_goals in range(5):
        for away_goals in range(5):
            if home_goals + away_goals > 4:
                continue
            base[(home_goals, away_goals)] = _poisson(home_goals, home_lambda) * _poisson(away_goals, away_lambda)

    base_total = sum(base.values())
    base = {score: value / base_total for score, value in base.items()}
    model_totals = {
        total: sum(value for (home_goals, away_goals), value in base.items() if home_goals + away_goals == total)
        for total in range(5)
    }
    model_outcomes = {
        key: sum(value for (home_goals, away_goals), value in base.items() if _outcome_key(home_goals, away_goals) == key)
        for key in ("home", "draw", "away")
    }
    model_btts = sum(value for (home_goals, away_goals), value in base.items() if home_goals > 0 and away_goals > 0)

    candidates: list[tuple[str, float]] = []
    for (home_goals, away_goals), probability in base.items():
        total = home_goals + away_goals
        total_target = (target_totals.get(total, 0.0) / 100.0) if total <= 3 else target_totals.get(3, 0.0) / 100.0
        total_model = model_totals.get(total, 0.0)
        outcome = _outcome_key(home_goals, away_goals)
        is_btts = home_goals > 0 and away_goals > 0
        btts_target = target_btts if is_btts else 1.0 - target_btts
        btts_model = model_btts if is_btts else 1.0 - model_btts

        # Poisson is the foundation. Marginal markets only calibrate it and
        # cannot directly manufacture a specific score such as 0:0 or 1:1.
        calibrated = probability
        calibrated *= _safe_ratio(total_target, total_model) ** 0.55
        calibrated *= _safe_ratio(target_outcomes[outcome], model_outcomes[outcome]) ** 0.20
        calibrated *= _safe_ratio(btts_target, btts_model) ** 0.15
        if total > 3:
            calibrated *= 0.65
        candidates.append((f"{home_goals}:{away_goals}", calibrated))

    return _normalize_top(candidates, limit)


def _team_goal_fit(home_goals: int, away_goals: int, expected_home: float, expected_away: float, decay: float = 0.85) -> float:
    distance = abs(home_goals - expected_home) + abs(away_goals - expected_away)
    return 100.0 * exp(-decay * distance)


def _outcome_fit(home_goals: int, away_goals: int, home: float, draw: float, away: float) -> float:
    return home if home_goals > away_goals else draw if home_goals == away_goals else away


def rank_exact_scores_ft(stats: dict[str, Any], limit: int = 3) -> list[ExactScorePick]:
    totals = _ft_total_distribution(stats)
    home_outcome, draw_outcome, away_outcome = _ft_outcomes(stats)
    btts = _mean_metric(stats, "Both Teams to Score")
    goals_scored = _metric(stats, "Goals scored per game") or (1.0, 1.0)
    goals_conceded = _metric(stats, "Goals conceded per game") or (1.0, 1.0)
    expected_home = (goals_scored[0] + goals_conceded[1]) / 2
    expected_away = (goals_scored[1] + goals_conceded[0]) / 2
    win_btts = _metric(stats, "Win and BTTS") or (0.0, 0.0)
    draw_btts = _metric(stats, "Draw and BTTS") or (0.0, 0.0)
    lose_btts = _metric(stats, "Lose and BTTS") or (0.0, 0.0)
    directional = {
        "home": ((win_btts[0] + lose_btts[1]) / 2, home_outcome),
        "draw": (sum(draw_btts) / 2, draw_outcome),
        "away": ((lose_btts[0] + win_btts[1]) / 2, away_outcome),
    }
    clean = _metric(stats, "Clean sheets") or (0.0, 0.0)
    team_scored = _metric(stats, "Team scored") or (0.0, 0.0)
    candidates = []
    for home_goals in range(6):
        for away_goals in range(6):
            total = home_goals + away_goals
            if total > 5:
                continue
            outcome = _outcome_key(home_goals, away_goals)
            result_btts_yes, result_total = directional[outcome]
            is_btts = home_goals > 0 and away_goals > 0
            result_btts_fit = result_btts_yes if is_btts else _clamp(result_total - result_btts_yes)
            btts_fit = btts if is_btts else 100 - btts
            allocation_fit = _team_goal_fit(home_goals, away_goals, expected_home, expected_away)
            if away_goals == 0:
                allocation_fit = (allocation_fit + clean[0] + (100 - team_scored[1])) / 3
            elif home_goals == 0:
                allocation_fit = (allocation_fit + clean[1] + (100 - team_scored[0])) / 3
            raw = (
                0.28 * totals.get(total, 0)
                + 0.20 * btts_fit
                + 0.20 * _outcome_fit(home_goals, away_goals, home_outcome, draw_outcome, away_outcome)
                + 0.24 * allocation_fit
                + 0.08 * result_btts_fit
            )
            candidates.append((f"{home_goals}:{away_goals}", raw / 100.0))
    return _normalize_top(candidates, limit)


def exact_score_diagnostics(stats: dict[str, Any], limit: int = 3) -> dict[str, list[dict[str, Any]]]:
    return {
        "ht": [pick.to_dict() for pick in rank_exact_scores_ht(stats, limit)],
        "ft": [pick.to_dict() for pick in rank_exact_scores_ft(stats, limit)],
    }
