from __future__ import annotations

import directional_engine_v2 as impl
from directional_engine_v2 import *

_canonicalize_goal_totals = impl.impl.legacy._canonicalize_goal_totals
_evaluate_htft = impl.impl.legacy._evaluate_htft


def __getattr__(name: str):
    if hasattr(impl, name):
        return getattr(impl, name)
    if hasattr(impl.impl, name):
        return getattr(impl.impl, name)
    return getattr(impl.impl.legacy, name)
