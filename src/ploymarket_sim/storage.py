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


@dataclass(frozen=True)
class MarketHistoryStats:
    market_id: str
    question: str
    market_type: str
    yes_token_id: str
    price_point_count: int
    first_timestamp: int | None
    last_timestamp: int | None


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

    def load_markets(self) -> list[Market]:
        if not self.enabled or not Path(self.sqlite_path).exists():
            return []
        self.init()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT market_id, question, slug, end_date, liquidity, volume_24hr,
                       yes_price, yes_token_id, fees_enabled, taker_fee_rate, fee_type
                FROM markets
                ORDER BY volume_24hr DESC
                """
            ).fetchall()
        markets = []
        for row in rows:
            (
                market_id,
                question,
                slug,
                end_date,
                liquidity,
                volume_24hr,
                yes_price,
                yes_token_id,
                fees_enabled,
                taker_fee_rate,
                fee_type,
            ) = row
            prices = [float(yes_price)] if yes_price is not None else []
            if yes_price is not None:
                prices.append(max(0.0, 1.0 - float(yes_price)))
            markets.append(
                Market(
                    str(market_id),
                    str(question),
                    str(slug),
                    str(end_date) if end_date else None,
                    float(liquidity),
                    float(volume_24hr),
                    True,
                    ["Yes", "No"],
                    prices,
                    [str(yes_token_id), ""] if yes_token_id else [],
                    bool(fees_enabled),
                    float(taker_fee_rate) if taker_fee_rate is not None else None,
                    str(fee_type) if fee_type else None,
                )
            )
        return markets

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

    def load_price_history(self, token_id: str) -> list[PricePoint]:
        if not self.enabled or not token_id or not Path(self.sqlite_path).exists():
            return []
        self.init()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, price
                FROM price_history
                WHERE token_id = ?
                ORDER BY timestamp
                """,
                (token_id,),
            ).fetchall()
        return [PricePoint(int(timestamp), float(price)) for timestamp, price in rows]

    def stats(self) -> StorageStats:
        if not self.enabled or not Path(self.sqlite_path).exists():
            return StorageStats(self.enabled, self.sqlite_path, 0, 0)
        self.init()
        with self._connect() as connection:
            market_count = int(connection.execute("SELECT COUNT(*) FROM markets").fetchone()[0])
            price_point_count = int(connection.execute("SELECT COUNT(*) FROM price_history").fetchone()[0])
        return StorageStats(self.enabled, self.sqlite_path, market_count, price_point_count)

    def market_history_stats(self) -> list[MarketHistoryStats]:
        if not self.enabled or not Path(self.sqlite_path).exists():
            return []
        self.init()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT m.market_id, m.question, m.market_type, m.yes_token_id,
                       COUNT(p.timestamp) AS point_count,
                       MIN(p.timestamp) AS first_timestamp,
                       MAX(p.timestamp) AS last_timestamp
                FROM markets m
                LEFT JOIN price_history p ON p.token_id = m.yes_token_id
                GROUP BY m.market_id, m.question, m.market_type, m.yes_token_id
                ORDER BY point_count DESC, m.volume_24hr DESC
                """
            ).fetchall()
        return [
            MarketHistoryStats(
                market_id=str(market_id),
                question=str(question),
                market_type=str(market_type),
                yes_token_id=str(yes_token_id or ""),
                price_point_count=int(point_count),
                first_timestamp=int(first_timestamp) if first_timestamp is not None else None,
                last_timestamp=int(last_timestamp) if last_timestamp is not None else None,
            )
            for market_id, question, market_type, yes_token_id, point_count, first_timestamp, last_timestamp in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.sqlite_path)


def storage_from_config(config) -> Storage:
    return Storage(config.storage.enabled, config.storage.sqlite_path)
