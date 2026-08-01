from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Iterable

import backtest_store as base

DEFAULT_DB_PATH = base.DEFAULT_DB_PATH
DuplicateAnalysisError = ValueError


def init_db(path: str | Path = DEFAULT_DB_PATH) -> None:
    base.init_db(path)


def save_analysis(match: dict[str, Any], recommendations: Iterable[Any], algorithm_version: str,
                  predicted_ht: str | None = None, predicted_ft: str | None = None,
                  analyzed_at: str | None = None, path: str | Path = DEFAULT_DB_PATH,
                  *, match_date: str = "", source: str = "live_analysis",
                  series_name: str = "validation-2.11", config_snapshot: dict[str, Any] | None = None,
                  odds_by_rule: dict[str, float] | None = None, bookmaker: str | None = None,
                  duplicate_policy: str = "error") -> int:
    del source, series_name, config_snapshot, bookmaker
    home = str(match.get("home_team") or "Gospodarz")
    away = str(match.get("away_team") or "Gość")
    duplicate = next((row for row in base.list_matches(path) if row["home_team"] == home and row["away_team"] == away
                      and row["algorithm_version"] == algorithm_version
                      and (not match_date or str(row["analyzed_at"]).startswith(match_date))), None)
    if duplicate:
        if duplicate_policy == "return_existing":
            return int(duplicate["id"])
        raise DuplicateAnalysisError(f"Analiza już istnieje (ID {duplicate['id']})")
    match_id = base.save_analysis(match, recommendations, algorithm_version, predicted_ht, predicted_ft, analyzed_at, path)
    if odds_by_rule:
        # Existing SQLite schema stores odds during settlement; preserve prediction odds by updating now.
        with base._connect(path) as conn:
            for rule_id, odds in odds_by_rule.items():
                conn.execute("UPDATE recommendations SET odds=? WHERE match_id=? AND rule_id=?", (float(odds), match_id, rule_id))
    return match_id


def settle_match(match_id: int, actual_ht: str, actual_ft: str,
                 odds_by_rule: dict[str, float] | None = None,
                 path: str | Path = DEFAULT_DB_PATH, **kwargs: Any) -> dict[str, int]:
    del kwargs
    if odds_by_rule is None:
        rows = [r for r in base.recommendation_rows(path, selected_only=True) if int(r["match_id"]) == int(match_id)]
        odds_by_rule = {str(r["rule_id"]): float(r["odds"]) for r in rows if r.get("odds") is not None}
    return base.settle_match(match_id, actual_ht, actual_ft, odds_by_rule, path)


def list_matches(path: str | Path = DEFAULT_DB_PATH, **kwargs: Any) -> list[dict[str, Any]]:
    rows = base.list_matches(path, unsettled_only=bool(kwargs.get("unsettled_only", False)))
    version = kwargs.get("algorithm_version")
    return [r for r in rows if not version or r["algorithm_version"] == version]


def recommendation_rows(path: str | Path = DEFAULT_DB_PATH, **kwargs: Any) -> list[dict[str, Any]]:
    rows = base.recommendation_rows(path, selected_only=bool(kwargs.get("selected_only", False)))
    version = kwargs.get("algorithm_version")
    return [r for r in rows if not version or r["algorithm_version"] == version]


def aggregate_dashboard(path: str | Path = DEFAULT_DB_PATH, **kwargs: Any) -> dict[str, Any]:
    if not any(kwargs.values()):
        return base.aggregate_dashboard(path)
    rows = [r for r in recommendation_rows(path, selected_only=True, **kwargs) if r["hit"] is not None]
    def summarize(group: list[dict[str, Any]]) -> dict[str, Any]:
        total=len(group); hits=sum(int(r["hit"]) for r in group); profits=[float(r["profit"]) for r in group if r["profit"] is not None]
        return {"total":total,"hits":hits,"hit_rate":round(100*hits/total,1) if total else None,
                "profit":round(sum(profits),2) if profits else None,"roi":round(100*sum(profits)/len(profits),1) if profits else None}
    groups={"by_level":{},"by_market":{},"by_score":{},"by_margin":{}}
    for row in rows:
        score=float(row["selection_score"] if row["selection_score"] is not None else row["score"])
        sb="<90" if score<90 else "90–99" if score<100 else "100–109" if score<110 else "110–119" if score<120 else "120–129" if score<130 else "130+"
        margin=float(row["threshold_margin"]) if row["threshold_margin"] is not None else 999
        mb="0–2,5 pp" if margin<=2.5 else "2,5–5 pp" if margin<=5 else "5–10 pp" if margin<=10 else "10+ pp"
        for name,key in (("by_level",row["selected_level"]),("by_market",row["label"]),("by_score",sb),("by_margin",mb)):
            groups[name].setdefault(str(key),[]).append(row)
    return {"overall":summarize(rows), **{n:{k:summarize(v) for k,v in g.items()} for n,g in groups.items()}}


def export_csv(path: str | Path = DEFAULT_DB_PATH, **kwargs: Any) -> bytes:
    rows = recommendation_rows(path, **kwargs)
    if not rows: return b""
    output=io.StringIO(); writer=csv.DictWriter(output, fieldnames=list(rows[0].keys())); writer.writeheader(); writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def import_history_csv(content: bytes, path: str | Path = DEFAULT_DB_PATH) -> dict[str, int]:
    rows=list(csv.DictReader(io.StringIO(content.decode("utf-8-sig")))); imported=skipped=0
    for row in rows:
        if not row.get("home_team") or not row.get("away_team") or not row.get("rule_id"):
            skipped+=1; continue
        reason="Poziom selekcji: główny typ" if row.get("selected_level")=="main" else "Poziom selekcji: dodatkowy sygnał"
        rec={"rule_id":row["rule_id"],"label":row.get("label") or row["rule_id"],"passed":True,"score":float(row.get("score") or 0),"data_quality":float(row.get("data_quality") or 0),"reasons":[reason]}
        try:
            save_analysis({"home_team":row["home_team"],"away_team":row["away_team"],"stats":{}},[rec],row.get("algorithm_version") or "historical",analyzed_at=row.get("analyzed_at") or None,path=path)
            imported+=1
        except ValueError:
            skipped+=1
    return {"imported":imported,"skipped":skipped}
