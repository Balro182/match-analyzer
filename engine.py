from __future__ import annotations

import directional_engine_v2 as _v2
from directional_engine_v2 import *

_canonicalize_goal_totals = _v2.impl.legacy._canonicalize_goal_totals
_evaluate_htft = _v2.impl.legacy._evaluate_htft


def __getattr__(name: str):
    if hasattr(_v2, name):
        return getattr(_v2, name)
    if hasattr(_v2.impl, name):
        return getattr(_v2.impl, name)
    return getattr(_v2.impl.legacy, name)
