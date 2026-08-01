from __future__ import annotations

from dataclasses import dataclass
from math import exp
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
        ExactScorePick(score=score, model_share=round(max(0.0, value) / total * 100.0, 1), raw_score=round(value, 2))
        for score, value in ordered_all[:limit]
    ]


def is_valid_score_progression(ht_home: int, ht_away: int, ft_home: int, ft_away: int) -> bool:
    return min(ht_home, ht_away, ft_home, ft_away) >= 0 and ft_home >= ht_home and ft_away >= ht_away


def _outcome_fit(home_goals: int, away_goals: int, home: float, draw: float, away: float) -> float:
    return home if home_goals > away_goals else draw if home_goals == away_goals else away


def _team_goal_fit(home_goals: int, away_goals: int, expected_home: float, expected_away: float) -> float:
    distance = abs(home_goals - expected_home) + abs(away_goals - expected_away)
    return 100.0 * exp(-0.85 * distance)


def _ft_total_distribution(stats: dict[str, Any]) -> dict[int, float]:
    exact = {goals: _mean_metric(stats, f"Match total goals {goals}") for goals in range(5)}
    canonical_four_plus = _clamp(100.0 - _mean_metric(stats, "Under 3.5 goals", 100.0))
    exact_four = min(exact[4], canonical_four_plus)
    exact[4] = exact_four
    exact[5] = max(0.0, canonical_four_plus - exact_four)
    return exact


def _ht_total_distribution(stats: dict[str, Any]) -> dict[int, float]:
    over05 = _mean_metric(stats, "Over 0.5 goals at half-time")
    over15 = _mean_metric(stats, "Over 1.5 goals at half-time")
    over25 = _mean_metric(stats, "Over 2.5 goals at half-time")
    return {0: _clamp(100-over05), 1: _clamp(over05-over15), 2: _clamp(over15-over25), 3: _clamp(over25)}


def _ft_outcomes(stats: dict[str, Any]) -> tuple[float, float, float]:
    win = _metric(stats, "Win") or (0.0, 0.0)
    lose = _metric(stats, "Lose") or (0.0, 0.0)
    draw = _metric(stats, "Draw") or (0.0, 0.0)
    home, away, draw_value = (win[0]+lose[1])/2, (win[1]+lose[0])/2, sum(draw)/2
    total = home+draw_value+away
    return (33.3,33.4,33.3) if total <= 0 else (home/total*100, draw_value/total*100, away/total*100)


def _ht_outcomes(stats: dict[str, Any]) -> tuple[float, float, float]:
    win = _metric(stats, "Team win first half") or (0.0, 0.0)
    lose = _metric(stats, "Team lost first half") or (0.0, 0.0)
    draw = _metric(stats, "Team draw at half time") or (0.0, 0.0)
    home, away, draw_value = (win[0]+lose[1])/2, (win[1]+lose[0])/2, sum(draw)/2
    total = home+draw_value+away
    return (33.3,33.4,33.3) if total <= 0 else (home/total*100, draw_value/total*100, away/total*100)


def rank_exact_scores_ht(stats: dict[str, Any], limit: int = 3) -> list[ExactScorePick]:
    totals = _ht_total_distribution(stats)
    home_outcome, draw_outcome, away_outcome = _ht_outcomes(stats)
    btts_ht = _mean_metric(stats, "BTTS in first-half")
    goals_scored = _metric(stats, "Goals scored per game") or (1.0,1.0)
    expected_home, expected_away = min(1.5, goals_scored[0]*0.45), min(1.5, goals_scored[1]*0.45)
    candidates=[]
    for hg in range(4):
        for ag in range(4):
            total=hg+ag
            if total>3:
                continue
            raw=(
                0.40*totals.get(total,0)
                +0.35*_outcome_fit(hg,ag,home_outcome,draw_outcome,away_outcome)
                +0.15*(btts_ht if hg and ag else 100-btts_ht)
                +0.10*_team_goal_fit(hg,ag,expected_home,expected_away)
            )
            candidates.append((f"{hg}:{ag}",raw))
    return _normalize_top(candidates,limit)


def rank_exact_scores_ft(stats: dict[str, Any], limit: int = 3) -> list[ExactScorePick]:
    totals = _ft_total_distribution(stats)
    home_outcome, draw_outcome, away_outcome = _ft_outcomes(stats)
    btts = _mean_metric(stats, "Both Teams to Score")
    goals_scored = _metric(stats, "Goals scored per game") or (1.0,1.0)
    goals_conceded = _metric(stats, "Goals conceded per game") or (1.0,1.0)
    expected_home, expected_away = (goals_scored[0]+goals_conceded[1])/2, (goals_scored[1]+goals_conceded[0])/2
    win_btts = _metric(stats, "Win and BTTS") or (0.0,0.0)
    draw_btts = _metric(stats, "Draw and BTTS") or (0.0,0.0)
    lose_btts = _metric(stats, "Lose and BTTS") or (0.0,0.0)
    directional = {
        "home": ((win_btts[0]+lose_btts[1])/2, home_outcome),
        "draw": (sum(draw_btts)/2, draw_outcome),
        "away": ((lose_btts[0]+win_btts[1])/2, away_outcome),
    }
    clean = _metric(stats, "Clean sheets") or (0.0,0.0)
    team_scored = _metric(stats, "Team scored") or (0.0,0.0)
    candidates=[]
    for hg in range(6):
        for ag in range(6):
            total=hg+ag
            if total>5:
                continue
            outcome_key = "home" if hg>ag else "draw" if hg==ag else "away"
            result_btts_yes, result_total = directional[outcome_key]
            is_btts = hg>0 and ag>0
            result_btts_fit = result_btts_yes if is_btts else _clamp(result_total-result_btts_yes)
            btts_fit = btts if is_btts else 100-btts
            allocation_fit = _team_goal_fit(hg,ag,expected_home,expected_away)
            if ag == 0:
                allocation_fit = (allocation_fit + clean[0] + (100-team_scored[1])) / 3
            elif hg == 0:
                allocation_fit = (allocation_fit + clean[1] + (100-team_scored[0])) / 3
            raw=(
                0.28*totals.get(total,0)
                +0.20*btts_fit
                +0.20*_outcome_fit(hg,ag,home_outcome,draw_outcome,away_outcome)
                +0.24*allocation_fit
                +0.08*result_btts_fit
            )
            candidates.append((f"{hg}:{ag}",raw))
    return _normalize_top(candidates,limit)


def exact_score_diagnostics(stats: dict[str, Any], limit: int = 3) -> dict[str, list[dict[str, Any]]]:
    return {"ht":[p.to_dict() for p in rank_exact_scores_ht(stats,limit)], "ft":[p.to_dict() for p in rank_exact_scores_ft(stats,limit)]}
