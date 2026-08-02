from __future__ import annotations

from exact_score_v2 import *
from exact_score_v2 import _ft_total_distribution
import exact_score_v2 as _impl


def _score_tuple(score: str) -> tuple[int, int]:
    return tuple(int(value) for value in score.split(":"))


def _score_outcome(score: str) -> str:
    home, away = _score_tuple(score)
    return "home" if home > away else "draw" if home == away else "away"


def _total_bucket(score: str) -> str:
    total = sum(_score_tuple(score))
    return str(total) if total < 3 else "3+"


def _ft_total_class(score: str) -> int:
    return min(sum(_score_tuple(score)), 5)


def _normalize_matrix(matrix: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, value) for value in matrix.values())
    if total <= 0:
        return matrix
    return {score: max(0.0, value) / total for score, value in matrix.items()}


def _scale_group(matrix: dict[str, float], classifier, target: dict[str, float]) -> dict[str, float]:
    current = {key: sum(value for score, value in matrix.items() if classifier(score) == key) for key in target}
    scaled = dict(matrix)
    for score, value in matrix.items():
        key = classifier(score)
        if key not in target:
            continue
        denominator = current.get(key, 0.0)
        scaled[score] = value * (target[key] / denominator if denominator > 1e-12 else 1.0)
    return _normalize_matrix(scaled)


def _target_total_buckets(stats) -> dict[str, float]:
    totals = _impl._ht_total_distribution(stats)
    return {"0": totals.get(0, 0.0) / 100.0, "1": totals.get(1, 0.0) / 100.0, "2": totals.get(2, 0.0) / 100.0, "3+": totals.get(3, 0.0) / 100.0}


def _dominant_total_bucket(stats) -> str:
    targets = _target_total_buckets(stats)
    order = ("0", "1", "2", "3+")
    return max(order, key=lambda key: (targets[key], -order.index(key)))


def _observed_ht_outcome_targets(stats) -> dict[str, float]:
    home, draw, away = _impl._ht_outcomes(stats)
    return {"home": home / 100.0, "draw": draw / 100.0, "away": away / 100.0}


def _dominant_observed_ht_outcome(stats) -> str:
    targets = _observed_ht_outcome_targets(stats)
    order = ("home", "draw", "away")
    return max(order, key=lambda key: (targets[key], -order.index(key)))


def _bucket_supports_outcome(bucket: str, outcome: str) -> bool:
    if bucket == "0":
        return outcome == "draw"
    if bucket == "1":
        return outcome in {"home", "away"}
    return True


def _retain_high_goal_ht_alternatives(stats, targets: dict[str, float]) -> bool:
    dominant_bucket = _dominant_total_bucket(stats)
    if dominant_bucket == "0":
        return False
    over_05 = _impl._clamp(_impl._mean_metric(stats, "Over 0.5 goals at half-time")) / 100.0
    over_15 = _impl._clamp(_impl._mean_metric(stats, "Over 1.5 goals at half-time")) / 100.0
    over_25 = _impl._clamp(_impl._mean_metric(stats, "Over 2.5 goals at half-time")) / 100.0
    return over_05 >= 0.85 and over_15 >= 0.50 and over_25 >= 0.20 and targets["3+"] >= 0.20 and targets[dominant_bucket] - targets["3+"] <= 0.10 + 1e-12


def _retain_ht_outcome_conflict_alternatives(stats, targets: dict[str, float]) -> bool:
    dominant_bucket = _dominant_total_bucket(stats)
    dominant_outcome = _dominant_observed_ht_outcome(stats)
    if _bucket_supports_outcome(dominant_bucket, dominant_outcome):
        return False
    ordered_shares = sorted(targets.values(), reverse=True)
    ordered_outcomes = sorted(_observed_ht_outcome_targets(stats).values(), reverse=True)
    return ordered_shares[0] - ordered_shares[1] < 0.15 - 1e-12 and ordered_outcomes[0] - ordered_outcomes[1] >= 0.05 - 1e-12


def _retain_flat_ht_distribution(stats, targets: dict[str, float]) -> bool:
    ordered = sorted(targets.values(), reverse=True)
    over_15 = _impl._clamp(_impl._mean_metric(stats, "Over 1.5 goals at half-time")) / 100.0
    return len(ordered) >= 3 and ordered[0] - ordered[2] <= 0.05 + 1e-12 and targets["2"] >= 0.20 - 1e-12 and targets["3+"] >= 0.10 - 1e-12 and over_15 >= 0.35 - 1e-12


def _selected_ht_buckets(stats) -> tuple[str, ...]:
    targets = _target_total_buckets(stats)
    dominant_bucket = _dominant_total_bucket(stats)
    dominant_share = targets[dominant_bucket]
    if _retain_high_goal_ht_alternatives(stats, targets):
        selected = tuple(bucket for bucket in ("1", "2", "3+") if targets[bucket] > 0 and dominant_share - targets[bucket] <= 0.10 + 1e-12)
        return selected or (dominant_bucket,)
    if _retain_ht_outcome_conflict_alternatives(stats, targets):
        dominant_outcome = _dominant_observed_ht_outcome(stats)
        selected = tuple(bucket for bucket in ("0", "1", "2", "3+") if bucket == dominant_bucket or (targets[bucket] > 0 and dominant_share - targets[bucket] <= 0.10 + 1e-12 and _bucket_supports_outcome(bucket, dominant_outcome)))
        return selected or (dominant_bucket,)
    if _retain_flat_ht_distribution(stats, targets):
        return tuple(bucket for bucket in ("0", "1", "2", "3+") if targets[bucket] >= dominant_share - 0.15 - 1e-12)
    return (dominant_bucket,)


def _target_btts(stats) -> dict[str, float]:
    yes = _impl._clamp(_impl._mean_metric(stats, "BTTS in first-half")) / 100.0
    return {"yes": yes, "no": 1.0 - yes}


def _btts_class(score: str) -> str:
    home, away = _score_tuple(score)
    return "yes" if home > 0 and away > 0 else "no"


def _soft_outcome_targets(matrix: dict[str, float], stats) -> dict[str, float]:
    observed = _observed_ht_outcome_targets(stats)
    base = {key: sum(value for score, value in matrix.items() if _score_outcome(score) == key) for key in observed}
    blended = {key: 0.65 * base[key] + 0.35 * observed[key] for key in observed}
    total = sum(blended.values()) or 1.0
    return {key: value / total for key, value in blended.items()}


def _ipf_ht_matrix(stats, iterations: int = 60) -> dict[str, float]:
    base_picks = _impl.rank_exact_scores_ht(stats, limit=25)
    matrix = _normalize_matrix({pick.score: max(0.0, pick.raw_score) / 100.0 for pick in base_picks})
    total_targets = _target_total_buckets(stats)
    btts_targets = _target_btts(stats)
    outcome_targets = _soft_outcome_targets(matrix, stats)
    for _ in range(iterations):
        matrix = _scale_group(matrix, _total_bucket, total_targets)
        matrix = _scale_group(matrix, _btts_class, btts_targets)
        matrix = _scale_group(matrix, _score_outcome, outcome_targets)
    return _normalize_matrix(matrix)


def rank_exact_scores_ht(stats, limit: int = 3):
    matrix = _ipf_ht_matrix(stats)
    selected_buckets = _selected_ht_buckets(stats)
    return _impl._normalize_top([(score, value) for score, value in matrix.items() if _total_bucket(score) in selected_buckets], limit)


def ht_profile_diagnostics(stats) -> dict[str, object]:
    matrix = _ipf_ht_matrix(stats)
    totals = {key: round(sum(value for score, value in matrix.items() if _total_bucket(score) == key) * 100.0, 1) for key in ("0", "1", "2", "3+")}
    outcomes = {key: round(sum(value for score, value in matrix.items() if _score_outcome(score) == key) * 100.0, 1) for key in ("home", "draw", "away")}
    btts_yes = round(sum(value for score, value in matrix.items() if _btts_class(score) == "yes") * 100.0, 1)
    selected_bucket = _dominant_total_bucket(stats)
    selected_buckets = _selected_ht_buckets(stats)
    targets = _target_total_buckets(stats)
    return {"total_goals": totals, "btts": {"yes": btts_yes, "no": round(100.0 - btts_yes, 1)}, "outcome": outcomes, "selection": {"goal_bucket": selected_bucket, "goal_buckets": list(selected_buckets), "bucket_share": totals[selected_bucket], "dominant_observed_outcome": _dominant_observed_ht_outcome(stats), "retained_high_goal_alternatives": _retain_high_goal_ht_alternatives(stats, targets), "retained_outcome_conflict_alternatives": _retain_ht_outcome_conflict_alternatives(stats, targets), "retained_flat_distribution_alternatives": _retain_flat_ht_distribution(stats, targets), "hard_total_margin": 15.0, "model_share_scope": "conditional_within_selected_goal_buckets"}}


def _ft_total_targets(stats) -> dict[int, float]:
    totals = _ft_total_distribution(stats)
    return {goals: max(0.0, totals.get(goals, 0.0)) / 100.0 for goals in range(6)}


def _dominant_ft_total(stats) -> int:
    targets = _ft_total_targets(stats)
    return max(range(6), key=lambda goals: (targets[goals], -goals))


def _retain_zero_goal_ft(stats, targets: dict[int, float], dominant_total: int) -> bool:
    if dominant_total != 1 or _dominant_total_bucket(stats) != "0":
        return False
    zero_share, one_share = targets.get(0, 0.0), targets.get(1, 0.0)
    btts_no = 1.0 - _impl._clamp(_impl._mean_metric(stats, "Both Teams to Score")) / 100.0
    under_15 = _impl._clamp(_impl._mean_metric(stats, "Under 1.5 goals")) / 100.0
    return zero_share >= 0.12 and zero_share >= 0.50 * one_share and btts_no >= 0.65 and under_15 >= 0.40


def _retain_close_ft_totals(stats, targets: dict[int, float], dominant_total: int) -> tuple[int, ...]:
    if dominant_total != 1 or "0" not in _selected_ht_buckets(stats):
        return (dominant_total,)
    ordered = sorted(targets.values(), reverse=True)
    if len(ordered) < 2 or ordered[0] - ordered[1] >= 0.15 - 1e-12:
        return (dominant_total,)
    if targets[3] >= 0.15 - 1e-12 and targets[1] - targets[3] <= 0.10 + 1e-12:
        return (1, 3)
    return (dominant_total,)


def _retain_high_ft_tail(stats, targets: dict[int, float], dominant_total: int) -> bool:
    high_tail = targets[4] + targets[5]
    over_25 = _impl._clamp(_impl._mean_metric(stats, "Over 2.5 goals")) / 100.0
    over_35 = _impl._clamp(_impl._mean_metric(stats, "Over 3.5 goals")) / 100.0
    btts = _impl._clamp(_impl._mean_metric(stats, "Both Teams to Score")) / 100.0
    return dominant_total <= 2 and high_tail >= 0.30 - 1e-12 and high_tail >= targets[dominant_total] - 0.05 - 1e-12 and over_35 >= 0.35 - 1e-12 and over_25 >= 0.40 - 1e-12 and btts >= 0.60 - 1e-12


def _retain_adjacent_high_ft_total(targets: dict[int, float], dominant_total: int) -> tuple[int, ...]:
    if dominant_total != 4:
        return (dominant_total,)
    three_share = targets[3]
    if three_share >= 0.20 - 1e-12 and targets[4] - three_share <= 0.05 + 1e-12:
        return (3, 4)
    return (dominant_total,)


def _selected_ft_totals(stats) -> tuple[int, ...]:
    targets = _ft_total_targets(stats)
    dominant_total = _dominant_ft_total(stats)
    if _retain_zero_goal_ft(stats, targets, dominant_total):
        return (0, 1)
    close_totals = _retain_close_ft_totals(stats, targets, dominant_total)
    if len(close_totals) > 1:
        return close_totals
    if _retain_high_ft_tail(stats, targets, dominant_total):
        return tuple(sorted({dominant_total, 4, 5}))
    adjacent_totals = _retain_adjacent_high_ft_total(targets, dominant_total)
    if len(adjacent_totals) > 1:
        return adjacent_totals
    return (dominant_total,)


def _valid_score_path(ht_score: str, ft_score: str) -> bool:
    ht_home, ht_away = _score_tuple(ht_score)
    ft_home, ft_away = _score_tuple(ft_score)
    return _impl.is_valid_score_progression(ht_home, ht_away, ft_home, ft_away)


def _ft_path_support(ft_score: str, stats) -> float:
    ht_matrix = _ipf_ht_matrix(stats)
    selected_ht_buckets = _selected_ht_buckets(stats)
    return sum(probability for ht_score, probability in ht_matrix.items() if _total_bucket(ht_score) in selected_ht_buckets and _valid_score_path(ht_score, ft_score))


def _ft_market_alignment(score: str, stats) -> float:
    home_goals, away_goals = _score_tuple(score)
    outcome_home, outcome_draw, outcome_away = _impl._ft_outcomes(stats)
    outcome_fit = {"home": outcome_home, "draw": outcome_draw, "away": outcome_away}[_score_outcome(score)] / 100.0
    btts_yes = _impl._clamp(_impl._mean_metric(stats, "Both Teams to Score")) / 100.0
    btts_fit = btts_yes if home_goals > 0 and away_goals > 0 else 1.0 - btts_yes
    scored = _impl._metric(stats, "Goals scored per game") or (1.0, 1.0)
    conceded = _impl._metric(stats, "Goals conceded per game") or (1.0, 1.0)
    expected_home = (scored[0] + conceded[1]) / 2.0
    expected_away = (scored[1] + conceded[0]) / 2.0
    allocation_fit = 1.0 / (1.0 + abs(home_goals - expected_home) + abs(away_goals - expected_away))
    twice = _impl._metric(stats, "Team scored twice")
    team_over_fit = 0.5
    if twice is not None:
        home_twice, away_twice = (_impl._clamp(value) / 100.0 for value in twice)
        team_over_fit = ((home_twice if home_goals >= 2 else 1.0 - home_twice) + (away_twice if away_goals >= 2 else 1.0 - away_twice)) / 2.0
    return 0.35 * outcome_fit + 0.30 * btts_fit + 0.20 * allocation_fit + 0.15 * team_over_fit


def _strong_high_tail_profile(stats) -> bool:
    targets = _ft_total_targets(stats)
    high_tail = targets[4] + targets[5]
    btts = _impl._clamp(_impl._mean_metric(stats, "Both Teams to Score")) / 100.0
    return high_tail >= 0.40 - 1e-12 and btts >= 0.70 - 1e-12


def _high_draw_directional_margin(stats) -> float:
    home, draw, away = _impl._ft_outcomes(stats)
    return max(home, away) - draw


def _balanced_high_draw_profile(stats) -> bool:
    scored = _impl._metric(stats, "Goals scored per game") or (1.0, 1.0)
    conceded = _impl._metric(stats, "Goals conceded per game") or (1.0, 1.0)
    expected_home = (scored[0] + conceded[1]) / 2.0
    expected_away = (scored[1] + conceded[0]) / 2.0
    _, draw, _ = _impl._ft_outcomes(stats)
    btts = _impl._clamp(_impl._mean_metric(stats, "Both Teams to Score")) / 100.0
    return btts >= 0.70 - 1e-12 and draw >= 20.0 - 1e-12 and abs(expected_home - expected_away) <= 0.25 + 1e-12 and _high_draw_directional_margin(stats) <= 10.0 + 1e-12


def _extended_ft_base_matrix(stats, max_total: int = 8) -> dict[str, float]:
    totals = _ft_total_targets(stats)
    home_outcome, draw_outcome, away_outcome = _impl._ft_outcomes(stats)
    btts = _impl._mean_metric(stats, "Both Teams to Score")
    goals_scored = _impl._metric(stats, "Goals scored per game") or (1.0, 1.0)
    goals_conceded = _impl._metric(stats, "Goals conceded per game") or (1.0, 1.0)
    expected_home = (goals_scored[0] + goals_conceded[1]) / 2.0
    expected_away = (goals_scored[1] + goals_conceded[0]) / 2.0
    win_btts = _impl._metric(stats, "Win and BTTS") or (0.0, 0.0)
    draw_btts = _impl._metric(stats, "Draw and BTTS") or (0.0, 0.0)
    lose_btts = _impl._metric(stats, "Lose and BTTS") or (0.0, 0.0)
    directional = {"home": ((win_btts[0] + lose_btts[1]) / 2, home_outcome), "draw": (sum(draw_btts) / 2, draw_outcome), "away": ((lose_btts[0] + win_btts[1]) / 2, away_outcome)}
    clean = _impl._metric(stats, "Clean sheets") or (0.0, 0.0)
    team_scored = _impl._metric(stats, "Team scored") or (0.0, 0.0)
    decay = 0.90 if _strong_high_tail_profile(stats) else 0.82
    balanced_high_draw = _balanced_high_draw_profile(stats)
    candidates: dict[str, float] = {}
    for home_goals in range(max_total + 1):
        for away_goals in range(max_total + 1):
            total = home_goals + away_goals
            if total > max_total:
                continue
            total_class = min(total, 5)
            outcome = _score_outcome(f"{home_goals}:{away_goals}")
            result_btts_yes, result_total = directional[outcome]
            is_btts = home_goals > 0 and away_goals > 0
            result_btts_fit = result_btts_yes if is_btts else _impl._clamp(result_total - result_btts_yes)
            btts_fit = btts if is_btts else 100.0 - btts
            allocation_fit = _impl._team_goal_fit(home_goals, away_goals, expected_home, expected_away)
            if away_goals == 0:
                allocation_fit = (allocation_fit + clean[0] + (100.0 - team_scored[1])) / 3.0
            elif home_goals == 0:
                allocation_fit = (allocation_fit + clean[1] + (100.0 - team_scored[0])) / 3.0
            raw = 0.28 * totals.get(total_class, 0.0) * 100.0 + 0.20 * btts_fit + 0.20 * _impl._outcome_fit(home_goals, away_goals, home_outcome, draw_outcome, away_outcome) + 0.24 * allocation_fit + 0.08 * result_btts_fit
            if total > 5:
                raw *= decay ** (total - 5)
            if balanced_high_draw and outcome == "draw" and total >= 4:
                raw *= 1.08
            candidates[f"{home_goals}:{away_goals}"] = raw / 100.0
    return _normalize_matrix(candidates)


def _ft_base_matrix(stats, selected_totals: tuple[int, ...]) -> dict[str, float]:
    if 5 in selected_totals:
        return _extended_ft_base_matrix(stats)
    base_picks = _impl.rank_exact_scores_ft(stats, limit=21)
    return _normalize_matrix({pick.score: pick.model_share / 100.0 for pick in base_picks})


def _normalize_ft_selection(ranked: list[tuple[str, float, float]], limit: int) -> list[ExactScorePick]:
    ordered = sorted(ranked, key=lambda item: (item[1], item[0]), reverse=True)
    displayed = ordered[:limit]
    displayed_total = sum(max(0.0, rank_value) for _, rank_value, _ in displayed)
    if displayed_total <= 0:
        return []
    return [ExactScorePick(score=score, model_share=round(max(0.0, rank_value) / displayed_total * 100.0, 1), raw_score=round(max(0.0, raw_probability) * 100.0, 2)) for score, rank_value, raw_probability in displayed]


def rank_exact_scores_ft(stats, limit: int = 3):
    targets = _ft_total_targets(stats)
    selected_totals = _selected_ft_totals(stats)
    base_matrix = _ft_base_matrix(stats, selected_totals)
    candidates = {score: probability for score, probability in base_matrix.items() if _ft_total_class(score) in selected_totals}
    path_support = {score: _ft_path_support(score, stats) for score in candidates}
    compatible = {score: value for score, value in candidates.items() if path_support[score] > 1e-12}
    if compatible:
        candidates = compatible
    max_path = max((path_support[score] for score in candidates), default=1.0) or 1.0
    max_total_target = max((targets[goals] for goals in selected_totals), default=1.0) or 1.0
    ranked = []
    for score, raw_probability in candidates.items():
        score_total_class = _ft_total_class(score)
        total_fit = targets[score_total_class] / max_total_target
        path_fit = path_support[score] / max_path
        market_fit = _ft_market_alignment(score, stats)
        rank_value = raw_probability * (0.35 + 0.65 * total_fit) * (0.30 + 0.70 * path_fit) * (0.45 + 0.55 * market_fit)
        ranked.append((score, rank_value, raw_probability))
    return _normalize_ft_selection(ranked, limit)


def ft_profile_diagnostics(stats) -> dict[str, object]:
    dominant_total = _dominant_ft_total(stats)
    selected_totals = _selected_ft_totals(stats)
    targets = _ft_total_targets(stats)
    ht_bucket = _dominant_total_bucket(stats)
    ht_buckets = _selected_ht_buckets(stats)
    retained_zero = 0 in selected_totals and dominant_total != 0
    retained_high_tail = _retain_high_ft_tail(stats, targets, dominant_total)
    retained_adjacent_high = len(_retain_adjacent_high_ft_total(targets, dominant_total)) > 1
    retained_close = len(selected_totals) > 1 and not retained_zero and not retained_high_tail and not retained_adjacent_high
    return {"total_goals": {str(key): round(value * 100.0, 1) for key, value in targets.items()}, "selection": {"goal_total": dominant_total, "goal_totals": list(selected_totals), "total_share": round(targets[dominant_total] * 100.0, 1), "high_tail_share": round((targets[4] + targets[5]) * 100.0, 1), "hard_total_margin": 15.0, "retained_close_total_alternatives": retained_close, "retained_adjacent_high_total_alternative": retained_adjacent_high, "retained_high_tail_alternatives": retained_high_tail, "strong_high_tail_decay": _strong_high_tail_profile(stats), "balanced_high_draw_bonus": _balanced_high_draw_profile(stats), "high_draw_directional_margin": round(_high_draw_directional_margin(stats), 1), "extended_ft_score_grid": retained_high_tail, "ht_goal_bucket": ht_bucket, "ht_goal_buckets": list(ht_buckets), "requires_valid_ht_ft_progression": True, "retained_zero_goal_alternative": retained_zero, "market_alignment": ["outcome", "BTTS", "team goals", "team scored twice"], "model_share_scope": "renormalized_within_displayed_ft_top_scores"}}


def exact_score_diagnostics(stats, limit: int = 3):
    return {"ht": [pick.to_dict() for pick in rank_exact_scores_ht(stats, limit)], "ft": [pick.to_dict() for pick in rank_exact_scores_ft(stats, limit)], "ht_profile": ht_profile_diagnostics(stats), "ft_profile": ft_profile_diagnostics(stats)}
