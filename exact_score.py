from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp
from typing import Any


@dataclass(frozen=True)
class ExactScorePick:
    score: str
    model_share: float
    raw_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    ordered = sorted(items, key=lambda item: (item[1], item[0]), reverse=True)[:limit]
    total = sum(max(0.0, value) for _, value in ordered)
    if total <= 0:
        return []

    shares = [round(value / total * 100.0) for _, value in ordered]
    difference = 100 - sum(shares)
    if shares:
        shares[0] += difference

    return [
        ExactScorePick(score=score, model_share=float(share), raw_score=round(value, 2))
        for (score, value), share in zip(ordered, shares)
    ]


def _outcome_fit(home_goals: int, away_goals: int, home: float, draw: float, away: float) -> float:
    if home_goals > away_goals:
        return home
    if home_goals == away_goals:
        return draw
    return away


def _team_goal_fit(home_goals: int, away_goals: int, expected_home: float, expected_away: float) -> float:
    distance = abs(home_goals - expected_home) + abs(away_goals - expected_away)
    return 100.0 * exp(-0.7 * distance)


def _ft_total_distribution(stats: dict[str, Any]) -> dict[int, float]:
    exact = {
        goals: _mean_metric(stats, f"Match total goals {goals}")
        for goals in range(5)
    }
    four_plus = _mean_metric(stats, "Match total goals 4+", 100.0 - _mean_metric(stats, "Under 3.5 goals", 100.0))
    exact[4] = max(exact[4], four_plus * 0.65)
    exact[5] = max(0.0, four_plus - exact[4])
    return exact


def _ht_total_distribution(stats: dict[str, Any]) -> dict[int, float]:
    over05 = _mean_metric(stats, "Over 0.5 goals at half-time")
    over15 = _mean_metric(stats, "Over 1.5 goals at half-time")
    over25 = _mean_metric(stats, "Over 2.5 goals at half-time")
    return {
        0: _clamp(100.0 - over05),
        1: _clamp(over05 - over15),
        2: _clamp(over15 - over25),
        3: _clamp(over25),
    }


def _ft_outcomes(stats: dict[str, Any]) -> tuple[float, float, float]:
    win = _metric(stats, "Win") or (0.0, 0.0)
    lose = _metric(stats, "Lose") or (0.0, 0.0)
    draw = _metric(stats, "Draw") or (0.0, 0.0)
    home = (win[0] + lose[1]) / 2
    away = (win[1] + lose[0]) / 2
    draw_value = sum(draw) / 2
    total = home + draw_value + away
    if total <= 0:
        return 33.3, 33.4, 33.3
    return home / total * 100, draw_value / total * 100, away / total * 100


def _ht_outcomes(stats: dict[str, Any]) -> tuple[float, float, float]:
    win = _metric(stats, "Team win first half") or (0.0, 0.0)
    lose = _metric(stats, "Team lost first half") or (0.0, 0.0)
    draw = _metric(stats, "Team draw at half time") or (0.0, 0.0)
    home = (win[0] + lose[1]) / 2
    away = (win[1] + lose[0]) / 2
    draw_value = sum(draw) / 2
    total = home + draw_value + away
    if total <= 0:
        return 33.3, 33.4, 33.3
    return home / total * 100, draw_value / total * 100, away / total * 100


def rank_exact_scores_ht(stats: dict[str, Any], limit: int = 3) -> list[ExactScorePick]:
    totals = _ht_total_distribution(stats)
    home_outcome, draw_outcome, away_outcome = _ht_outcomes(stats)
    btts_ht = _mean_metric(stats, "BTTS in first-half")

    goals_scored = _metric(stats, "Goals scored per game") or (1.0, 1.0)
    expected_home = min(1.5, goals_scored[0] * 0.45)
    expected_away = min(1.5, goals_scored[1] * 0.45)

    candidates: list[tuple[str, float]] = []
    for home_goals in range(4):
        for away_goals in range(4):
            total = home_goals + away_goals
            if total > 3:
                continue
            total_fit = totals.get(total, 0.0)
            outcome_fit = _outcome_fit(home_goals, away_goals, home_outcome, draw_outcome, away_outcome)
            btts_fit = btts_ht if home_goals > 0 and away_goals > 0 else 100.0 - btts_ht
            team_fit = _team_goal_fit(home_goals, away_goals, expected_home, expected_away)
            raw = 0.40 * total_fit + 0.35 * outcome_fit + 0.15 * btts_fit + 0.10 * team_fit
            candidates.append((f"{home_goals}:{away_goals}", raw))

    return _normalize_top(candidates, limit)


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

    candidates: list[tuple[str, float]] = []
    for home_goals in range(6):
        for away_goals in range(6):
            total = home_goals + away_goals
            if total > 5:
                continue
            total_fit = totals.get(total, 0.0)
            outcome_fit = _outcome_fit(home_goals, away_goals, home_outcome, draw_outcome, away_outcome)
            is_btts = home_goals > 0 and away_goals > 0
            btts_fit = btts if is_btts else 100.0 - btts
            team_fit = _team_goal_fit(home_goals, away_goals, expected_home, expected_away)

            if home_goals > away_goals:
                result_btts_fit = (win_btts[0] + lose_btts[1]) / 2 if is_btts else 100.0 - (win_btts[0] + lose_btts[1]) / 2
            elif home_goals == away_goals:
                result_btts_fit = sum(draw_btts) / 2 if is_btts else 100.0 - sum(draw_btts) / 2
            else:
                result_btts_fit = (lose_btts[0] + win_btts[1]) / 2 if is_btts else 100.0 - (lose_btts[0] + win_btts[1]) / 2

            raw = (
                0.30 * total_fit
                + 0.25 * btts_fit
                + 0.20 * outcome_fit
                + 0.15 * team_fit
                + 0.10 * result_btts_fit
            )
            candidates.append((f"{home_goals}:{away_goals}", raw))

    return _normalize_top(candidates, limit)


def exact_score_diagnostics(stats: dict[str, Any], limit: int = 3) -> dict[str, list[dict[str, Any]]]:
    return {
        "ht": [pick.to_dict() for pick in rank_exact_scores_ht(stats, limit)],
        "ft": [pick.to_dict() for pick in rank_exact_scores_ft(stats, limit)],
    }
