from __future__ import annotations

import directional_engine_impl as impl
from directional_engine_impl import *

_canonicalize_goal_totals = impl.legacy._canonicalize_goal_totals
_evaluate_htft = impl.legacy._evaluate_htft


def __getattr__(name: str):
    if hasattr(impl, name):
        return getattr(impl, name)
    return getattr(impl.legacy, name)
