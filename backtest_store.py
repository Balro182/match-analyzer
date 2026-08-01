from __future__ import annotations

import csv
import io
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DB_PATH = Path("data/backtest.db")
SELECTED_LEVELS = {"main", "additional"}


@dataclass(frozen=True)
class Scoreline:
    home: int
    away: int

    @property
    def total(self) -> int:
        return self.home + self.away

    @property
    def outcome(self) -> str:
        return "home" if self.home > self.away else "draw" if self.home == self.away else "away"


def _connect(path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def init_db(path: str | Path = DEFAULT_DB_PATH) -> None:
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                analyzed_at TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                algorithm_version TEXT NOT NULL,
                source_stats_json TEXT NOT NULL,
                predicted_ht TEXT,
                predicted_ft TEXT,
                actual_ht_home INTEGER,
                actual_ht_away INTEGER,
                actual_ft_home INTEGER,
                actual_ft_away INTEGER,
                settled_at TEXT,
                UNIQUE(home_team, away_team, analyzed_at, algorithm_version)
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
                rule_id TEXT NOT NULL,
                label TEXT NOT NULL,
                selected_level TEXT NOT NULL,
                passed INTEGER NOT NULL,
                raw_value REAL,
                threshold_value REAL,
                threshold_margin REAL,
                score REAL NOT NULL,
                data_quality REAL NOT NULL,
                mode TEXT,
                selection_score REAL,
                reasons_json TEXT NOT NULL,
                odds REAL,
                hit INTEGER,
                profit REAL,
                settled_at TEXT,
                UNIQUE(match_id, rule_id)
            );

            CREATE INDEX IF NOT EXISTS idx_recommendations_level ON recommendations(selected_level);
            CREATE INDEX IF NOT EXISTS idx_recommendations_rule ON recommendations(rule_id);
            CREATE INDEX IF NOT EXISTS idx_recommendations_hit ON recommendations(hit);
            """
        )


def _selection_score(reasons: Iterable[str]) -> float | None:
    for reason in reasons:
        marker = "selection score "
        lower = reason.casefold()
        if marker in lower:
            tail = lower.split(marker, 1)[1].split(";", 1)[0].strip()
            try:
                return float(tail.replace(",", "."))
            except ValueError:
                continue
    return None


def _selected_level(reasons: Iterable[str], passed: bool) -> str:
    text = " | ".join(str(reason) for reason in reasons).casefold()
    if passed and "poziom selekcji: główny typ" in text:
        return "main"
    if passed and "poziom selekcji: dodatkowy sygnał" in text:
        return "additional"
    return "rejected"


def save_analysis(
    match: dict[str, Any],
    recommendations: Iterable[Any],
    algorithm_version: str,
    predicted_ht: str | None = None,
    predicted_ft: str | None = None,
    analyzed_at: str | None = None,
    path: str | Path = DEFAULT_DB_PATH,
) -> int:
    init_db(path)
    timestamp = analyzed_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect(path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO matches (
                created_at, analyzed_at, home_team, away_team, algorithm_version,
                source_stats_json, predicted_ht, predicted_ft
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                timestamp,
                str(match.get("home_team") or "Gospodarz"),
                str(match.get("away_team") or "Gość"),
                algorithm_version,
                json.dumps(match.get("stats", {}), ensure_ascii=False, sort_keys=True),
                predicted_ht,
                predicted_ft,
            ),
        )
        match_id = int(cursor.lastrowid)
        for item in recommendations:
            rec = item.to_dict() if hasattr(item, "to_dict") else dict(item)
            reasons = [str(reason) for reason in rec.get("reasons", [])]
            raw_value = rec.get("raw_value")
            threshold = rec.get("threshold")
            margin = None if raw_value is None or threshold is None else float(raw_value) - float(threshold)
            passed = bool(rec.get("passed"))
            conn.execute(
                """
                INSERT INTO recommendations (
                    match_id, rule_id, label, selected_level, passed, raw_value,
                    threshold_value, threshold_margin, score, data_quality, mode,
                    selection_score, reasons_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    str(rec.get("rule_id")),
                    str(rec.get("label")),
                    _selected_level(reasons, passed),
                    int(passed),
                    raw_value,
                    threshold,
                    margin,
                    float(rec.get("score", 0.0)),
                    float(rec.get("data_quality", 0.0)),
                    rec.get("mode"),
                    _selection_score(reasons),
                    json.dumps(reasons, ensure_ascii=False),
                ),
            )
        return match_id


def parse_scoreline(value: str) -> Scoreline:
    normalized = value.strip().replace("-", ":")
    parts = normalized.split(":")
    if len(parts) != 2:
        raise ValueError("Wynik musi mieć format A:B, np. 1:0")
    home, away = (int(part.strip()) for part in parts)
    if home < 0 or away < 0:
        raise ValueError("Wynik nie może zawierać liczb ujemnych")
    return Scoreline(home, away)


def _hit(rule_id: str, ht: Scoreline, ft: Scoreline) -> bool | None:
    if ft.home < ht.home or ft.away < ht.away:
        raise ValueError("Wynik FT nie może być niższy niż wynik HT")

    if rule_id == "home_win": return ft.outcome == "home"
    if rule_id == "draw": return ft.outcome == "draw"
    if rule_id == "away_win": return ft.outcome == "away"
    if rule_id == "home_win_ht": return ht.outcome == "home"
    if rule_id == "draw_ht": return ht.outcome == "draw"
    if rule_id == "away_win_ht": return ht.outcome == "away"
    if rule_id == "btts": return ft.home > 0 and ft.away > 0
    if rule_id == "btts_no": return ft.home == 0 or ft.away == 0
    if rule_id == "clean_sheets": return ft.home == 0 or ft.away == 0
    if rule_id == "team_scored_twice": return max(ft.home, ft.away) >= 2
    if rule_id == "scored_both_halves": return (ht.home > 0 and ft.home > ht.home) or (ht.away > 0 and ft.away > ht.away)
    if rule_id == "goal_both_halves": return ht.total > 0 and ft.total > ht.total
    if rule_id == "btts_ht1": return ht.home > 0 and ht.away > 0
    if rule_id == "btts_ht2": return ft.home > ht.home and ft.away > ht.away

    if rule_id.startswith("total") and rule_id[5:].isdigit():
        return ft.total == int(rule_id[5:])
    if rule_id == "total01": return ft.total <= 1
    if rule_id == "total23": return 2 <= ft.total <= 3
    if rule_id == "total4plus": return ft.total >= 4

    totals = {
        "over15": ft.total > 1.5, "over25": ft.total > 2.5, "over35": ft.total > 3.5,
        "under15": ft.total < 1.5, "under25": ft.total < 2.5, "under35": ft.total < 3.5,
        "over05ht": ht.total > 0.5, "over15ht": ht.total > 1.5, "over25ht": ht.total > 2.5,
    }
    if rule_id in totals: return totals[rule_id]

    htft = {
        "win_win": ("home", "home"), "win_draw": ("home", "draw"), "win_lose": ("home", "away"),
        "draw_win": ("draw", "home"), "draw_draw": ("draw", "draw"), "draw_lose": ("draw", "away"),
        "lose_win": ("away", "home"), "lose_draw": ("away", "draw"), "lose_lose": ("away", "away"),
    }
    if rule_id in htft:
        expected_ht, expected_ft = htft[rule_id]
        return ht.outcome == expected_ht and ft.outcome == expected_ft
    return None


def settle_match(
    match_id: int,
    actual_ht: str,
    actual_ft: str,
    odds_by_rule: dict[str, float] | None = None,
    path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, int]:
    init_db(path)
    ht, ft = parse_scoreline(actual_ht), parse_scoreline(actual_ft)
    if ft.home < ht.home or ft.away < ht.away:
        raise ValueError("Nieprawidłowa progresja HT → FT")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    odds_by_rule = odds_by_rule or {}
    settled = skipped = 0
    with _connect(path) as conn:
        exists = conn.execute("SELECT id FROM matches WHERE id = ?", (match_id,)).fetchone()
        if exists is None:
            raise ValueError(f"Nie istnieje mecz o ID {match_id}")
        conn.execute(
            """UPDATE matches SET actual_ht_home=?, actual_ht_away=?, actual_ft_home=?, actual_ft_away=?, settled_at=? WHERE id=?""",
            (ht.home, ht.away, ft.home, ft.away, timestamp, match_id),
        )
        rows = conn.execute("SELECT id, rule_id, selected_level FROM recommendations WHERE match_id=?", (match_id,)).fetchall()
        for row in rows:
            result = _hit(str(row["rule_id"]), ht, ft)
            if result is None:
                skipped += 1
                continue
            odds = odds_by_rule.get(str(row["rule_id"]))
            profit = None
            if odds is not None and str(row["selected_level"]) in SELECTED_LEVELS:
                profit = float(odds) - 1.0 if result else -1.0
            conn.execute(
                "UPDATE recommendations SET hit=?, odds=?, profit=?, settled_at=? WHERE id=?",
                (int(result), odds, profit, timestamp, int(row["id"])),
            )
            settled += 1
    return {"settled": settled, "skipped": skipped}


def list_matches(path: str | Path = DEFAULT_DB_PATH, unsettled_only: bool = False) -> list[dict[str, Any]]:
    init_db(path)
    where = "WHERE settled_at IS NULL" if unsettled_only else ""
    with _connect(path) as conn:
        rows = conn.execute(
            f"SELECT id, analyzed_at, home_team, away_team, algorithm_version, predicted_ht, predicted_ft, settled_at FROM matches {where} ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def recommendation_rows(path: str | Path = DEFAULT_DB_PATH, selected_only: bool = False) -> list[dict[str, Any]]:
    init_db(path)
    where = "WHERE r.selected_level IN ('main','additional')" if selected_only else ""
    with _connect(path) as conn:
        rows = conn.execute(
            f"""
            SELECT m.id AS match_id, m.analyzed_at, m.home_team, m.away_team, m.algorithm_version,
                   m.actual_ht_home, m.actual_ht_away, m.actual_ft_home, m.actual_ft_away,
                   r.rule_id, r.label, r.selected_level, r.raw_value, r.threshold_value,
                   r.threshold_margin, r.score, r.data_quality, r.selection_score,
                   r.odds, r.hit, r.profit
            FROM recommendations r JOIN matches m ON m.id=r.match_id
            {where}
            ORDER BY m.id DESC, r.id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def aggregate_dashboard(path: str | Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    rows = [row for row in recommendation_rows(path, selected_only=True) if row["hit"] is not None]
    def summarize(group: list[dict[str, Any]]) -> dict[str, float | int | None]:
        total = len(group)
        hits = sum(int(row["hit"]) for row in group)
        profits = [float(row["profit"]) for row in group if row["profit"] is not None]
        return {
            "total": total,
            "hits": hits,
            "hit_rate": round(100.0 * hits / total, 1) if total else None,
            "profit": round(sum(profits), 2) if profits else None,
            "roi": round(100.0 * sum(profits) / len(profits), 1) if profits else None,
        }

    by_level: dict[str, list[dict[str, Any]]] = {}
    by_market: dict[str, list[dict[str, Any]]] = {}
    by_score: dict[str, list[dict[str, Any]]] = {}
    by_margin: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_level.setdefault(str(row["selected_level"]), []).append(row)
        by_market.setdefault(str(row["label"]), []).append(row)
        score = float(row["selection_score"] if row["selection_score"] is not None else row["score"])
        score_bucket = "<90" if score < 90 else "90–99" if score < 100 else "100–109" if score < 110 else "110–119" if score < 120 else "120–129" if score < 130 else "130+"
        by_score.setdefault(score_bucket, []).append(row)
        margin = row["threshold_margin"]
        margin_value = float(margin) if margin is not None else 999.0
        margin_bucket = "0–2,5 pp" if margin_value <= 2.5 else "2,5–5 pp" if margin_value <= 5 else "5–10 pp" if margin_value <= 10 else "10+ pp"
        by_margin.setdefault(margin_bucket, []).append(row)
    return {
        "overall": summarize(rows),
        "by_level": {key: summarize(value) for key, value in by_level.items()},
        "by_market": {key: summarize(value) for key, value in by_market.items()},
        "by_score": {key: summarize(value) for key, value in by_score.items()},
        "by_margin": {key: summarize(value) for key, value in by_margin.items()},
    }


def export_csv(path: str | Path = DEFAULT_DB_PATH, selected_only: bool = False) -> bytes:
    rows = recommendation_rows(path, selected_only=selected_only)
    if not rows:
        return b""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")
