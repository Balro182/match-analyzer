from __future__ import annotations

import csv
import io
import os
from pathlib import Path
from typing import Any, Iterable

import sqlite_validation_store as sqlite_store


def _supabase_enabled() -> bool:
    return bool(os.getenv("SUPABASE_URL", "").strip() and os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip())


def backend_name() -> str:
    return "Supabase PostgreSQL" if _supabase_enabled() else "SQLite (fallback)"


def _module():
    if _supabase_enabled():
        import supabase_store
        return supabase_store
    return sqlite_store


def init_db(path: str | Path = sqlite_store.DEFAULT_DB_PATH) -> None:
    return _module().init_db(path)


def save_analysis(match: dict[str, Any], recommendations: Iterable[Any], algorithm_version: str,
                  predicted_ht: str | None = None, predicted_ft: str | None = None,
                  analyzed_at: str | None = None, path: str | Path = sqlite_store.DEFAULT_DB_PATH,
                  **kwargs: Any) -> int:
    return _module().save_analysis(match, recommendations, algorithm_version, predicted_ht, predicted_ft,
                                   analyzed_at, path, **kwargs)


def settle_match(match_id: int, actual_ht: str, actual_ft: str,
                 odds_by_rule: dict[str, float] | None = None,
                 path: str | Path = sqlite_store.DEFAULT_DB_PATH, **kwargs: Any) -> dict[str, int]:
    return _module().settle_match(match_id, actual_ht, actual_ft, odds_by_rule, path, **kwargs)


def list_matches(path: str | Path = sqlite_store.DEFAULT_DB_PATH, **kwargs: Any) -> list[dict[str, Any]]:
    return _module().list_matches(path, **kwargs)


def recommendation_rows(path: str | Path = sqlite_store.DEFAULT_DB_PATH, **kwargs: Any) -> list[dict[str, Any]]:
    return _module().recommendation_rows(path, **kwargs)


def aggregate_dashboard(path: str | Path = sqlite_store.DEFAULT_DB_PATH, **kwargs: Any) -> dict[str, Any]:
    return _module().aggregate_dashboard(path, **kwargs)


def export_csv(path: str | Path = sqlite_store.DEFAULT_DB_PATH, **kwargs: Any) -> bytes:
    return _module().export_csv(path, **kwargs)


def import_history_csv(content: bytes, path: str | Path = sqlite_store.DEFAULT_DB_PATH) -> dict[str, int]:
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    imported = skipped = 0
    for row in rows:
        if not all((row.get("home_team"), row.get("away_team"), row.get("rule_id"), row.get("algorithm_version"))):
            skipped += 1
            continue
        level = row.get("selected_level") or "additional"
        reason = "Poziom selekcji: główny typ" if level == "main" else "Poziom selekcji: dodatkowy sygnał"
        rec = {
            "rule_id": row["rule_id"], "label": row.get("label") or row["rule_id"], "passed": True,
            "raw_value": float(row["raw_value"]) if row.get("raw_value") else None,
            "threshold": float(row["threshold_value"]) if row.get("threshold_value") else None,
            "score": float(row.get("score") or 0), "data_quality": float(row.get("data_quality") or 0),
            "mode": "historical_import", "reasons": [reason, "Źródło: manual_history"],
        }
        try:
            save_analysis(
                {"home_team": row["home_team"], "away_team": row["away_team"], "stats": {}},
                [rec], row["algorithm_version"], analyzed_at=row.get("analyzed_at") or None, path=path,
                match_date=row.get("match_date") or "", source="manual_history",
                series_name=row.get("series_name") or "historical", duplicate_policy="error",
            )
            imported += 1
        except ValueError:
            skipped += 1
    return {"imported": imported, "skipped": skipped}


DEFAULT_DB_PATH = sqlite_store.DEFAULT_DB_PATH
DuplicateAnalysisError = ValueError
