from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from time import time

from .classifier import classify_market
from .clob import PricePoint
from .polymarket import Market


@dataclass(frozen=True)
class StorageStats:
    enabled: bool
    sqlite_path: str
    market_count: int
    price_point_count: int


class Storage:
    def __init__(self, enabled: bool, sqlite_path: str):
        self.enabled = enabled
        self.sqlite_path = sqlite_path

    def init(self) -> None:
        if not self.enabled:
            return
        path = Path(self.sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS markets (
                    market_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    end_date TEXT,
                    liquidity REAL NOT NULL,
                    volume_24hr REAL NOT NULL,
                    yes_price REAL,
                    yes_token_id TEXT,
                    fees_enabled INTEGER NOT NULL,
                    taker_fee_rate REAL,
                    fee_type TEXT,
                    observed_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    token_id TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    price REAL NOT NULL,
                    observed_at REAL NOT NULL,
                    PRIMARY KEY (token_id, timestamp)
                )
                """
            )

    def save_markets(self, markets: list[Market]) -> None:
        if not self.enabled:
            return
        self.init()
        observed_at = time()
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO markets (
                    market_id, question, slug, market_type, end_date, liquidity, volume_24hr,
                    yes_price, yes_token_id, fees_enabled, taker_fee_rate, fee_type, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_id) DO UPDATE SET
                    question=excluded.question,
                    slug=excluded.slug,
                    market_type=excluded.market_type,
                    end_date=excluded.end_date,
                    liquidity=excluded.liquidity,
                    volume_24hr=excluded.volume_24hr,
                    yes_price=excluded.yes_price,
                    yes_token_id=excluded.yes_token_id,
                    fees_enabled=excluded.fees_enabled,
                    taker_fee_rate=excluded.taker_fee_rate,
                    fee_type=excluded.fee_type,
                    observed_at=excluded.observed_at
                """,
                [
                    (
                        market.id,
                        market.question,
                        market.slug,
                        classify_market(market).market_type,
                        market.end_date,
                        market.liquidity,
                        market.volume_24hr,
                        market.yes_price,
                        market.yes_token_id,
                        1 if market.fees_enabled else 0,
                        market.taker_fee_rate,
                        market.fee_type,
                        observed_at,
                    )
                    for market in markets
                ],
            )

    def save_price_history(self, token_id: str, history: list[PricePoint]) -> None:
        if not self.enabled or not token_id:
            return
        self.init()
        observed_at = time()
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO price_history (token_id, timestamp, price, observed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(token_id, timestamp) DO UPDATE SET
                    price=excluded.price,
                    observed_at=excluded.observed_at
                """,
                [(token_id, point.timestamp, point.price, observed_at) for point in history],
            )

    def stats(self) -> StorageStats:
        if not self.enabled or not Path(self.sqlite_path).exists():
            return StorageStats(self.enabled, self.sqlite_path, 0, 0)
        self.init()
        with self._connect() as connection:
            market_count = int(connection.execute("SELECT COUNT(*) FROM markets").fetchone()[0])
            price_point_count = int(connection.execute("SELECT COUNT(*) FROM price_history").fetchone()[0])
        return StorageStats(self.enabled, self.sqlite_path, market_count, price_point_count)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.sqlite_path)


def storage_from_config(config) -> Storage:
    return Storage(config.storage.enabled, config.storage.sqlite_path)
