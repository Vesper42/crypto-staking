"""SQLite persistence for staking positions and price history."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from config import CONFIG

_SCHEMA = """
CREATE TABLE IF NOT EXISTS staking_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    amount_idr REAL NOT NULL,
    entry_price_usd REAL DEFAULT 0,
    apy REAL NOT NULL,
    staked_at TEXT NOT NULL,
    last_reward_check TEXT,
    accumulated_reward_idr REAL DEFAULT 0,
    platform TEXT DEFAULT 'tokocrypto'
);

CREATE TABLE IF NOT EXISTS price_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    price_usd REAL NOT NULL,
    change_from_entry_pct REAL
);

CREATE TABLE IF NOT EXISTS alerts_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_price_log_ts ON price_log(ts);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts_sent(ts);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(CONFIG.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript(_SCHEMA)


def upsert_position(asset: str, amount_idr: float, entry_price_usd: float, apy: float) -> int:
    with _conn() as c:
        existing = c.execute(
            "SELECT id FROM staking_positions WHERE asset = ? AND platform = ?",
            (asset, CONFIG.platform),
        ).fetchone()
        if existing:
            c.execute(
                """UPDATE staking_positions
                   SET amount_idr = ?, entry_price_usd = ?, apy = ?, staked_at = ?
                   WHERE id = ?""",
                (amount_idr, entry_price_usd, apy, _now(), existing["id"]),
            )
            return int(existing["id"])
        cur = c.execute(
            """INSERT INTO staking_positions
               (asset, amount_idr, entry_price_usd, apy, staked_at, platform)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (asset, amount_idr, entry_price_usd, apy, _now(), CONFIG.platform),
        )
        return int(cur.lastrowid or 0)


def get_positions() -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM staking_positions WHERE platform = ? ORDER BY asset",
            (CONFIG.platform,),
        ).fetchall()
        return [dict(r) for r in rows]


def record_price(symbol: str, price_usd: float, change_pct: float) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO price_log (ts, symbol, price_usd, change_from_entry_pct) VALUES (?, ?, ?, ?)",
            (_now(), symbol, price_usd, change_pct),
        )


def update_reward(asset: str, reward_idr: float) -> None:
    with _conn() as c:
        c.execute(
            """UPDATE staking_positions
               SET accumulated_reward_idr = accumulated_reward_idr + ?, last_reward_check = ?
               WHERE asset = ? AND platform = ?""",
            (reward_idr, _now(), asset, CONFIG.platform),
        )


def was_alert_sent_today(alert_type: str) -> bool:
    today = datetime.now(timezone.utc).date().isoformat()
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM alerts_sent WHERE alert_type = ? AND ts >= ? LIMIT 1",
            (alert_type, today),
        ).fetchone()
        return row is not None


def record_alert(alert_type: str, message: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO alerts_sent (ts, alert_type, message) VALUES (?, ?, ?)",
            (_now(), alert_type, message),
        )
