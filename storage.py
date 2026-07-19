from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).with_name("predictions.db")


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


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
                settlement_json TEXT
            )
            """
        )


def save_match(snapshot: dict[str, Any]) -> tuple[bool, str]:
    init_db()
    match = snapshot["match"]
    unique_key = "|".join([
        str(match.get("match_date") or match.get("listing_date") or ""),
        str(match.get("home_team") or ""),
        str(match.get("away_team") or ""),
        str(match.get("url") or ""),
    ])
    try:
        with _connect() as con:
            con.execute(
                """
                INSERT INTO saved_matches (
                    unique_key, saved_at, match_date, kickoff, country, league,
                    home_team, away_team, source_url, snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def settle_match(match_id: int, home_ft: int, away_ft: int, home_ht: int | None, away_ht: int | None, settlement: list[dict[str, Any]]) -> None:
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


def delete_match(match_id: int) -> None:
    with _connect() as con:
        con.execute("DELETE FROM saved_matches WHERE id=?", (match_id,))
