from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine import ALGORITHM_VERSION

DB_PATH = Path(__file__).with_name("predictions.db")
DEFAULT_PROFILE_NAME = "Domyślny"


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _columns(con: sqlite3.Connection) -> set[str]:
    return {str(row[1]) for row in con.execute("PRAGMA table_info(saved_matches)").fetchall()}


def init_db() -> None:
    with _connect() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_key TEXT NOT NULL UNIQUE,
                saved_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'oczekuje',
                match_date TEXT,
                kickoff TEXT,
                country TEXT,
                league TEXT,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                source_url TEXT,
                snapshot_json TEXT NOT NULL,
                home_ft INTEGER,
                away_ft INTEGER,
                home_ht INTEGER,
                away_ht INTEGER,
                settled_at TEXT,
                settlement_json TEXT,
                algorithm_version TEXT,
                config_version TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_profiles (
                name TEXT PRIMARY KEY,
                config_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        existing = _columns(con)
        if "algorithm_version" not in existing:
            con.execute("ALTER TABLE saved_matches ADD COLUMN algorithm_version TEXT")
        if "config_version" not in existing:
            con.execute("ALTER TABLE saved_matches ADD COLUMN config_version TEXT")


def load_prediction_config() -> dict[str, Any] | None:
    """Wczytuje aktywną, trwale zapisaną konfigurację progów."""
    init_db()
    with _connect() as con:
        row = con.execute(
            "SELECT config_json FROM prediction_profiles WHERE is_active=1 ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    try:
        value = json.loads(row["config_json"])
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def prediction_profile_info() -> dict[str, Any] | None:
    init_db()
    with _connect() as con:
        row = con.execute(
            "SELECT name, updated_at FROM prediction_profiles WHERE is_active=1 ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row is not None else None


def save_prediction_config(config: dict[str, Any], name: str = DEFAULT_PROFILE_NAME) -> tuple[bool, str]:
    """Zapisuje cały zestaw progów i trybów jako aktywną konfigurację domyślną."""
    init_db()
    normalized_name = (name or DEFAULT_PROFILE_NAME).strip() or DEFAULT_PROFILE_NAME
    payload = json.dumps(config, ensure_ascii=False)
    updated_at = datetime.now(timezone.utc).isoformat()
    try:
        with _connect() as con:
            con.execute("UPDATE prediction_profiles SET is_active=0")
            con.execute(
                """
                INSERT INTO prediction_profiles (name, config_json, updated_at, is_active)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(name) DO UPDATE SET
                    config_json=excluded.config_json,
                    updated_at=excluded.updated_at,
                    is_active=1
                """,
                (normalized_name, payload, updated_at),
            )
        return True, "Progi i tryby zostały zapisane na stałe. Będą wczytywane po ponownym uruchomieniu aplikacji."
    except (sqlite3.Error, TypeError, ValueError) as exc:
        return False, f"Nie udało się zapisać progów: {exc}"


def reset_prediction_config() -> tuple[bool, str]:
    """Wyłącza trwały profil; przy następnym wczytaniu używany jest config.yaml."""
    init_db()
    try:
        with _connect() as con:
            con.execute("UPDATE prediction_profiles SET is_active=0")
        return True, "Przywrócono wartości domyślne z config.yaml."
    except sqlite3.Error as exc:
        return False, f"Nie udało się przywrócić konfiguracji: {exc}"


def save_match(snapshot: dict[str, Any]) -> tuple[bool, str]:
    init_db()
    match = snapshot["match"]
    unique_key = "|".join(
        [
            str(match.get("match_date") or match.get("listing_date") or ""),
            str(match.get("home_team") or ""),
            str(match.get("away_team") or ""),
            str(match.get("url") or ""),
        ]
    )
    snapshot.setdefault("algorithm_version", ALGORITHM_VERSION)
    snapshot.setdefault("config_version", snapshot.get("algorithm_version", ALGORITHM_VERSION))
    try:
        with _connect() as con:
            con.execute(
                """
                INSERT INTO saved_matches (
                    unique_key, saved_at, match_date, kickoff, country, league,
                    home_team, away_team, source_url, snapshot_json,
                    algorithm_version, config_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unique_key,
                    datetime.now(timezone.utc).isoformat(),
                    match.get("match_date") or match.get("listing_date"),
                    match.get("kickoff"),
                    match.get("country"),
                    match.get("league"),
                    match.get("home_team"),
                    match.get("away_team"),
                    match.get("url"),
                    json.dumps(snapshot, ensure_ascii=False),
                    snapshot.get("algorithm_version"),
                    snapshot.get("config_version"),
                ),
            )
        return True, "Mecz zapisano do późniejszej weryfikacji."
    except sqlite3.IntegrityError:
        return False, "Ten mecz jest już zapisany do weryfikacji."


def list_matches(status: str | None = None) -> list[dict[str, Any]]:
    init_db()
    query = "SELECT * FROM saved_matches"
    params: tuple[Any, ...] = ()
    if status:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY match_date DESC, kickoff DESC, id DESC"
    with _connect() as con:
        return [dict(row) for row in con.execute(query, params).fetchall()]


def settle_match(
    match_id: int,
    home_ft: int,
    away_ft: int,
    home_ht: int | None,
    away_ht: int | None,
    settlement: list[dict[str, Any]],
) -> None:
    with _connect() as con:
        con.execute(
            """
            UPDATE saved_matches
            SET status='rozliczony', home_ft=?, away_ft=?, home_ht=?, away_ht=?,
                settled_at=?, settlement_json=?
            WHERE id=?
            """,
            (
                home_ft,
                away_ft,
                home_ht,
                away_ht,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(settlement, ensure_ascii=False),
                match_id,
            ),
        )


def reprocess_match(match_id: int) -> tuple[bool, str]:
    """Jawne, audytowalne ponowne rozliczenie pojedynczego meczu."""
    from settlement import settle_recommendations

    with _connect() as con:
        row = con.execute("SELECT * FROM saved_matches WHERE id=?", (match_id,)).fetchone()
        if row is None:
            return False, "Nie znaleziono meczu."
        if row["home_ft"] is None or row["away_ft"] is None:
            return False, "Mecz nie ma zapisanego wyniku końcowego."
        snapshot = json.loads(row["snapshot_json"])
        settlement = settle_recommendations(
            snapshot.get("recommendations", []),
            int(row["home_ft"]),
            int(row["away_ft"]),
            None if row["home_ht"] is None else int(row["home_ht"]),
            None if row["away_ht"] is None else int(row["away_ht"]),
        )
        con.execute(
            "UPDATE saved_matches SET settlement_json=?, algorithm_version=? WHERE id=?",
            (json.dumps(settlement, ensure_ascii=False), ALGORITHM_VERSION, match_id),
        )
    return True, "Mecz został ponownie rozliczony aktualnym algorytmem."


def delete_match(match_id: int) -> None:
    with _connect() as con:
        con.execute("DELETE FROM saved_matches WHERE id=?", (match_id,))
