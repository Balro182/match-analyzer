from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from backtest_store import DEFAULT_DB_PATH, SELECTED_LEVELS, _hit, parse_scoreline


class DuplicateAnalysisError(ValueError):
    pass


def _base_url() -> str:
    return os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"


def _headers(prefer: str | None = None) -> dict[str, str]:
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _request(method: str, table: str, *, params: dict[str, Any] | None = None,
             body: Any = None, prefer: str | None = None) -> Any:
    response = requests.request(method, f"{_base_url()}/{table}", params=params,
                                json=body, headers=_headers(prefer), timeout=25)
    if response.status_code >= 400:
        message = response.text
        if response.status_code == 409 or "duplicate key" in message.casefold():
            raise DuplicateAnalysisError("Analiza o tym kluczu już istnieje")
        raise RuntimeError(f"Supabase {response.status_code}: {message}")
    return response.json() if response.content else None


def init_db(path: str | Path = DEFAULT_DB_PATH) -> None:
    # Schema is created once with sql/supabase_schema.sql.
    _request("GET", "matches", params={"select": "id", "limit": 1})


def _selection_score(reasons: Iterable[str]) -> float | None:
    for reason in reasons:
        lower = str(reason).casefold()
        if "selection score " in lower:
            try:
                return float(lower.split("selection score ", 1)[1].split(";", 1)[0].strip().replace(",", "."))
            except ValueError:
                pass
    return None


def _selected_level(reasons: Iterable[str], passed: bool) -> str:
    text = " | ".join(str(x) for x in reasons).casefold()
    if passed and "poziom selekcji: główny typ" in text:
        return "main"
    if passed and "poziom selekcji: dodatkowy sygnał" in text:
        return "additional"
    return "rejected"


def _find_duplicate(match_date: str, home_team: str, away_team: str,
                    algorithm_version: str, series_name: str) -> dict[str, Any] | None:
    rows = _request("GET", "matches", params={
        "select": "id,settled_at", "match_date": f"eq.{match_date}",
        "home_team": f"eq.{home_team}", "away_team": f"eq.{away_team}",
        "algorithm_version": f"eq.{algorithm_version}", "series_name": f"eq.{series_name}", "limit": 1,
    })
    return rows[0] if rows else None


def save_analysis(match: dict[str, Any], recommendations: Iterable[Any], algorithm_version: str,
                  predicted_ht: str | None = None, predicted_ft: str | None = None,
                  analyzed_at: str | None = None, path: str | Path = DEFAULT_DB_PATH,
                  *, match_date: str = "", source: str = "live_analysis",
                  series_name: str = "validation-2.11", config_snapshot: dict[str, Any] | None = None,
                  odds_by_rule: dict[str, float] | None = None, bookmaker: str | None = None,
                  duplicate_policy: str = "error") -> int:
    del path
    timestamp = analyzed_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    home_team = str(match.get("home_team") or "Gospodarz")
    away_team = str(match.get("away_team") or "Gość")
    duplicate = _find_duplicate(match_date, home_team, away_team, algorithm_version, series_name)
    if duplicate:
        if duplicate_policy == "return_existing":
            return int(duplicate["id"])
        if duplicate_policy == "replace_unsettled" and duplicate.get("settled_at") is None:
            _request("DELETE", "matches", params={"id": f"eq.{duplicate['id']}"})
        else:
            raise DuplicateAnalysisError(f"Analiza już istnieje (ID {duplicate['id']})")

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    inserted = _request("POST", "matches", body={
        "created_at": created_at, "analyzed_at": timestamp, "match_date": match_date,
        "home_team": home_team, "away_team": away_team, "algorithm_version": algorithm_version,
        "source": source, "series_name": series_name,
        "source_stats_json": match.get("stats", {}), "config_snapshot_json": config_snapshot,
        "predicted_ht": predicted_ht, "predicted_ft": predicted_ft,
    }, prefer="return=representation")
    match_id = int(inserted[0]["id"])
    odds_by_rule = odds_by_rule or {}
    rows = []
    for item in recommendations:
        rec = item.to_dict() if hasattr(item, "to_dict") else dict(item)
        reasons = [str(x) for x in rec.get("reasons", [])]
        raw_value, threshold = rec.get("raw_value"), rec.get("threshold")
        rule_id = str(rec.get("rule_id"))
        odds = odds_by_rule.get(rule_id)
        rows.append({
            "match_id": match_id, "rule_id": rule_id, "label": str(rec.get("label")),
            "selected_level": _selected_level(reasons, bool(rec.get("passed"))),
            "passed": bool(rec.get("passed")), "raw_value": raw_value,
            "threshold_value": threshold,
            "threshold_margin": None if raw_value is None or threshold is None else float(raw_value)-float(threshold),
            "score": float(rec.get("score", 0)), "data_quality": float(rec.get("data_quality", 0)),
            "mode": rec.get("mode"), "selection_score": _selection_score(reasons),
            "reasons_json": reasons, "odds_at_prediction": odds,
            "bookmaker": bookmaker if odds is not None else None,
            "odds_captured_at": created_at if odds is not None else None,
        })
    if rows:
        _request("POST", "recommendations", body=rows, prefer="return=minimal")
    return match_id


def settle_match(match_id: int, actual_ht: str, actual_ft: str,
                 odds_by_rule: dict[str, float] | None = None,
                 path: str | Path = DEFAULT_DB_PATH,
                 closing_odds_by_rule: dict[str, float] | None = None) -> dict[str, int]:
    del path
    ht, ft = parse_scoreline(actual_ht), parse_scoreline(actual_ft)
    if ft.home < ht.home or ft.away < ht.away:
        raise ValueError("Nieprawidłowa progresja HT → FT")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _request("PATCH", "matches", params={"id": f"eq.{match_id}"}, body={
        "actual_ht_home": ht.home, "actual_ht_away": ht.away,
        "actual_ft_home": ft.home, "actual_ft_away": ft.away, "settled_at": timestamp,
    }, prefer="return=minimal")
    rows = _request("GET", "recommendations", params={
        "select": "id,rule_id,selected_level,odds_at_prediction", "match_id": f"eq.{match_id}"})
    odds_by_rule, closing_odds_by_rule = odds_by_rule or {}, closing_odds_by_rule or {}
    settled = skipped = 0
    for row in rows:
        result = _hit(str(row["rule_id"]), ht, ft)
        if result is None:
            skipped += 1
            continue
        rule_id = str(row["rule_id"])
        odds = odds_by_rule.get(rule_id, row.get("odds_at_prediction"))
        profit = None
        if odds is not None and row["selected_level"] in SELECTED_LEVELS:
            profit = float(odds)-1 if result else -1.0
        _request("PATCH", "recommendations", params={"id": f"eq.{row['id']}"}, body={
            "hit": bool(result), "odds_at_prediction": odds,
            "closing_odds": closing_odds_by_rule.get(rule_id), "profit": profit, "settled_at": timestamp,
        }, prefer="return=minimal")
        settled += 1
    return {"settled": settled, "skipped": skipped}


def list_matches(path: str | Path = DEFAULT_DB_PATH, unsettled_only: bool = False,
                 algorithm_version: str | None = None, source: str | None = None,
                 series_name: str | None = None) -> list[dict[str, Any]]:
    del path
    params: dict[str, Any] = {"select": "id,analyzed_at,match_date,home_team,away_team,algorithm_version,source,series_name,predicted_ht,predicted_ft,settled_at", "order": "id.desc"}
    if unsettled_only: params["settled_at"] = "is.null"
    if algorithm_version: params["algorithm_version"] = f"eq.{algorithm_version}"
    if source: params["source"] = f"eq.{source}"
    if series_name: params["series_name"] = f"eq.{series_name}"
    return _request("GET", "matches", params=params)


def recommendation_rows(path: str | Path = DEFAULT_DB_PATH, selected_only: bool = False,
                        algorithm_version: str | None = None, source: str | None = None,
                        series_name: str | None = None) -> list[dict[str, Any]]:
    del path
    params: dict[str, Any] = {
        "select": "match_id,rule_id,label,selected_level,raw_value,threshold_value,threshold_margin,score,data_quality,selection_score,odds:odds_at_prediction,bookmaker,closing_odds,hit,profit,matches!inner(analyzed_at,match_date,home_team,away_team,algorithm_version,source,series_name,actual_ht_home,actual_ht_away,actual_ft_home,actual_ft_away)",
        "order": "match_id.desc",
    }
    if selected_only: params["selected_level"] = "in.(main,additional)"
    if algorithm_version: params["matches.algorithm_version"] = f"eq.{algorithm_version}"
    if source: params["matches.source"] = f"eq.{source}"
    if series_name: params["matches.series_name"] = f"eq.{series_name}"
    rows = _request("GET", "recommendations", params=params)
    flattened = []
    for row in rows:
        match = row.pop("matches")
        flattened.append({**match, **row})
    return flattened


def _summarize(group: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(group); hits = sum(int(bool(r["hit"])) for r in group)
    profits = [float(r["profit"]) for r in group if r.get("profit") is not None]
    return {"total": total, "hits": hits,
            "hit_rate": round(100*hits/total, 1) if total else None,
            "profit": round(sum(profits), 2) if profits else None,
            "roi": round(100*sum(profits)/len(profits), 1) if profits else None}


def aggregate_dashboard(path: str | Path = DEFAULT_DB_PATH, **filters: Any) -> dict[str, Any]:
    rows = [r for r in recommendation_rows(path, selected_only=True, **filters) if r.get("hit") is not None]
    groups = {"by_level": {}, "by_market": {}, "by_score": {}, "by_margin": {}}
    for row in rows:
        score = float(row["selection_score"] if row.get("selection_score") is not None else row["score"])
        score_bucket = "<90" if score < 90 else "90–99" if score < 100 else "100–109" if score < 110 else "110–119" if score < 120 else "120–129" if score < 130 else "130+"
        margin = float(row["threshold_margin"]) if row.get("threshold_margin") is not None else 999
        margin_bucket = "0–2,5 pp" if margin <= 2.5 else "2,5–5 pp" if margin <= 5 else "5–10 pp" if margin <= 10 else "10+ pp"
        for name, key in (("by_level", row["selected_level"]), ("by_market", row["label"]),
                          ("by_score", score_bucket), ("by_margin", margin_bucket)):
            groups[name].setdefault(str(key), []).append(row)
    return {"overall": _summarize(rows), **{name: {k: _summarize(v) for k, v in data.items()} for name, data in groups.items()}}


def export_csv(path: str | Path = DEFAULT_DB_PATH, selected_only: bool = False, **filters: Any) -> bytes:
    rows = recommendation_rows(path, selected_only=selected_only, **filters)
    if not rows:
        return b""
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader(); writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")
