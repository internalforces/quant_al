from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


VALID_MARKETS = {"국장", "미장"}


@dataclass(frozen=True)
class AliasEntry:
    chat_id: str
    market: str
    alias: str
    ticker: str
    name: str
    exchange: str


class AliasStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS aliases (
                    chat_id TEXT NOT NULL,
                    alias_key TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    market TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    name TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (chat_id, alias_key)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_aliases_chat_market
                    ON aliases (chat_id, market, alias)
                """
            )

    @staticmethod
    def normalize_alias(alias: str) -> str:
        return " ".join(alias.strip().split()).casefold()

    def upsert(self, entry: AliasEntry) -> None:
        if entry.market not in VALID_MARKETS:
            raise ValueError("market must be 국장 or 미장")
        alias_key = self.normalize_alias(entry.alias)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO aliases (
                    chat_id, alias_key, alias, market, ticker, name, exchange,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, alias_key) DO UPDATE SET
                    alias = excluded.alias,
                    market = excluded.market,
                    ticker = excluded.ticker,
                    name = excluded.name,
                    exchange = excluded.exchange,
                    updated_at = excluded.updated_at
                """,
                (
                    entry.chat_id,
                    alias_key,
                    entry.alias,
                    entry.market,
                    entry.ticker,
                    entry.name,
                    entry.exchange,
                    now,
                    now,
                ),
            )

    def get(self, chat_id: str, alias: str) -> AliasEntry | None:
        alias_key = self.normalize_alias(alias)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT chat_id, market, alias, ticker, name, exchange
                FROM aliases
                WHERE chat_id = ? AND alias_key = ?
                """,
                (chat_id, alias_key),
            ).fetchone()
        return self._row_to_entry(row)

    def list_by_market(self, chat_id: str, market: str) -> list[AliasEntry]:
        if market not in VALID_MARKETS:
            raise ValueError("market must be 국장 or 미장")
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chat_id, market, alias, ticker, name, exchange
                FROM aliases
                WHERE chat_id = ? AND market = ?
                ORDER BY alias COLLATE NOCASE
                """,
                (chat_id, market),
            ).fetchall()
        return [entry for row in rows if (entry := self._row_to_entry(row))]

    def delete(self, chat_id: str, alias: str) -> AliasEntry | None:
        existing = self.get(chat_id, alias)
        if not existing:
            return None
        alias_key = self.normalize_alias(alias)
        with self._connect() as conn:
            conn.execute(
                """
                DELETE FROM aliases
                WHERE chat_id = ? AND alias_key = ?
                """,
                (chat_id, alias_key),
            )
        return existing

    @staticmethod
    def _row_to_entry(row: sqlite3.Row | None) -> AliasEntry | None:
        if row is None:
            return None
        return AliasEntry(
            chat_id=row["chat_id"],
            market=row["market"],
            alias=row["alias"],
            ticker=row["ticker"],
            name=row["name"],
            exchange=row["exchange"],
        )
