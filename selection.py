from __future__ import annotations

import selection_legacy as legacy
from selection_legacy import *

DIRECTIONAL_TEAM_GOALS = {"home_team_over15", "away_team_over15"}
DIRECTIONAL_TEAM_TIMING = {"home_score_both_halves", "away_score_both_halves"}

legacy.TEAM_GOALS_IDS.update(DIRECTIONAL_TEAM_GOALS | DIRECTIONAL_TEAM_TIMING)
legacy.ROBUSTNESS_FACTORS.update({
    "home_team_over15": 0.91,
    "away_team_over15": 0.91,
    "home_score_both_halves": 0.86,
    "away_score_both_halves": 0.86,
})
legacy.MARKET_CLUSTERS.update({
    "home_team_over15": "team_goals_home",
    "away_team_over15": "team_goals_away",
    "home_score_both_halves": "team_timing_home",
    "away_score_both_halves": "team_timing_away",
})
legacy.NESTED_PAIRS.update({
    frozenset({"home_team_over15", "home_score_both_halves"}),
    frozenset({"away_team_over15", "away_score_both_halves"}),
    frozenset({"home_team_over15", "over15"}),
    frozenset({"away_team_over15", "over15"}),
})

_original_scenario_tags = legacy._scenario_tags


def _scenario_tags(rule_id: str) -> set[str]:
    if rule_id == "home_team_over15":
        return {"home_team_goals", "high_scoring", "open_game"}
    if rule_id == "away_team_over15":
        return {"away_team_goals", "high_scoring", "open_game"}
    if rule_id == "home_score_both_halves":
        return {"home_team_goals", "goals_both_halves", "open_game"}
    if rule_id == "away_score_both_halves":
        return {"away_team_goals", "goals_both_halves", "open_game"}
    return _original_scenario_tags(rule_id)


legacy._scenario_tags = _scenario_tags


def __getattr__(name: str):
    return getattr(legacy, name)
