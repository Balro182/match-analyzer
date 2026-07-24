from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


METRICS = (
    "Goals scored per game",
    "Goals conceded per game",
    "Clean sheets",
    "Team scored",
    "Team scored twice",
    "Scored in both halves",
    "Goal in both halves",
    "Win",
    "Draw",
    "Lose",
    "Win and Over 1.5 goals",
    "Lose and Over 1.5 goals",
    "Team win first half",
    "Team draw at half time",
    "Team lost first half",
    "Both Teams to Score",
    "BTTS in first-half",
    "BBTS in second-half",
    "BBTS and Over 1.5",
    "BBTS and Over 2.5",
    "Win and BTTS",
    "Draw and BTTS",
    "Lose and BTTS",
    "Match total goals 0",
    "Match total goals 1",
    "Match total goals 2",
    "Match total goals 3",
    "Match total goals 4",
    "Match total goals 0 or 1",
    "Match total goals 2 or 3",
    "Match total goals 4+",
    "Over 1.5 goals",
    "Over 2.5 goals",
    "Over 3.5 goals",
    "Under 1.5 goals",
    "Under 2.5 goals",
    "Under 3.5 goals",
    "Over 0.5 goals at half-time",
    "Over 1.5 goals at half-time",
    "Over 2.5 goals at half-time",
    "Win HT - Win FT",
    "Win HT - Draw FT",
    "Win HT - Lose FT",
    "Draw HT - Win FT",
    "Draw HT - Draw FT",
    "Draw HT - Lose FT",
    "Lose HT - Win FT",
    "Lose HT - Draw FT",
    "Lose HT - Lose FT",
)

# Longest names first prevents matching "Win" inside "Win and BTTS".
_METRICS_BY_LENGTH = tuple(sorted(METRICS, key=len, reverse=True))
_NUMBER = r"[-+]?\d+(?:[.,]\d+)?%?"


@dataclass(frozen=True)
class ParsedStats:
    stats: dict[str, dict[str, float]]
    missing_metrics: list[str]
    duplicate_metrics: list[str]
    ignored_lines: list[str]


def _as_float(value: str) -> float:
    return float(value.strip().rstrip("%").replace(",", "."))


def _metric_in_line(line: str) -> str | None:
    folded = line.casefold()
    for metric in _METRICS_BY_LENGTH:
        if metric.casefold() in folded:
            return metric
    return None


def _numbers_around_metric(line: str, metric: str) -> tuple[float, float] | None:
    start = line.casefold().find(metric.casefold())
    if start < 0:
        return None
    before = line[:start]
    after = line[start + len(metric) :]
    left = re.findall(_NUMBER, before)
    right = re.findall(_NUMBER, after)
    if not left or not right:
        return None
    return _as_float(left[-1]), _as_float(right[0])


def parse_pasted_stats(text: str, required_metrics: Iterable[str] = METRICS) -> ParsedStats:
    """Parse two-column statistics copied from the football-stats page.

    Each metric row is expected to contain the home value before the metric name
    and the away value after it, for example::

        1.90  Goals scored per game  1.50
        60.00%  Win  30.00%

    Headers, team names and blank lines are ignored.
    """

    stats: dict[str, dict[str, float]] = {}
    duplicates: list[str] = []
    ignored: list[str] = []

    for raw_line in text.splitlines():
        line = " ".join(raw_line.strip().split())
        if not line:
            continue
        metric = _metric_in_line(line)
        if metric is None:
            ignored.append(raw_line.strip())
            continue
        values = _numbers_around_metric(line, metric)
        if values is None:
            ignored.append(raw_line.strip())
            continue
        if metric in stats:
            duplicates.append(metric)
        home, away = values
        stats[metric] = {"home": home, "away": away}

    required = list(required_metrics)
    missing = [metric for metric in required if metric not in stats]
    return ParsedStats(stats, missing, sorted(set(duplicates)), ignored)
