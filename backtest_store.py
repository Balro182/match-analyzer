from __future__ import annotations

import backtest_store_legacy as legacy
from backtest_store_legacy import *


def _hit(rule_id: str, ht: Scoreline, ft: Scoreline) -> bool | None:
    if ft.home < ht.home or ft.away < ht.away:
        raise ValueError("Wynik FT nie może być niższy niż wynik HT")

    if rule_id == "home_team_over15":
        return ft.home >= 2
    if rule_id == "away_team_over15":
        return ft.away >= 2
    if rule_id == "home_score_both_halves":
        return ht.home > 0 and ft.home > ht.home
    if rule_id == "away_score_both_halves":
        return ht.away > 0 and ft.away > ht.away
    return legacy._hit(rule_id, ht, ft)


# Legacy settlement resolves _hit from its own module globals. Rebind it so both
# SQLite and Supabase use exactly the same directional settlement semantics.
legacy._hit = _hit


def __getattr__(name: str):
    return getattr(legacy, name)
