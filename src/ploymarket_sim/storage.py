from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from time import time

from .classifier import classify_market
from .clob import PricePoint
from .market_rules import infer_strike_direction
from .paper import PaperSignalRow
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


@dataclass(frozen=True)
class SnapshotStats:
    snapshot_count: int
    first_timestamp: int | None
    last_timestamp: int | None


@dataclass(frozen=True)
class PaperPositionState:
    market_id: str
    side: str
    entry_price: float
    shares: float
    notional: float
    opened_at: int
    status: str
    closed_at: int | None
    realized_pnl: float
    cooldown_until: int
    peak_price: float
    partial_take_profit_count: int


@dataclass(frozen=True)
class PaperAccountSummary:
    realized_pnl: float
    open_position_count: int
    closed_position_count: int


class Storage:
    def __init__(self, enabled: bool, sqlite_path: str):
        self.enabled = enabled
        self.sqlite_path = sqlite_path
        self._initialized = False

    def init(self) -> None:
        if not self.enabled:
            return
        if self._initialized:
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
                    no_price REAL,
                    no_token_id TEXT,
                    condition_id TEXT,
                    fees_enabled INTEGER NOT NULL,
                    taker_fee_rate REAL,
                    fee_type TEXT,
                    observed_at REAL NOT NULL
                )
                """
            )
            _ensure_column(connection, "markets", "no_price", "REAL")
            _ensure_column(connection, "markets", "no_token_id", "TEXT")
            _ensure_column(connection, "markets", "condition_id", "TEXT")
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_snapshots (
                    run_timestamp INTEGER NOT NULL,
                    market_id TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    yes_price REAL,
                    taker_fee_rate REAL NOT NULL,
                    action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    gross_edge REAL NOT NULL,
                    net_edge REAL NOT NULL,
                    execution_mode TEXT NOT NULL,
                    execution_side TEXT NOT NULL,
                    limit_price REAL,
                    expected_net_edge REAL NOT NULL,
                    reason TEXT NOT NULL,
                    execution_reason TEXT NOT NULL,
                    PRIMARY KEY (run_timestamp, market_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS stale_tokens (
                    token_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    observed_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_positions (
                    market_id TEXT PRIMARY KEY,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    shares REAL NOT NULL,
                    notional REAL NOT NULL,
                    opened_at INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    closed_at INTEGER,
                    realized_pnl REAL NOT NULL,
                    cooldown_until INTEGER NOT NULL,
                    peak_price REAL NOT NULL DEFAULT 0,
                    partial_take_profit_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_position_history (
                    market_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    shares REAL NOT NULL,
                    notional REAL NOT NULL,
                    opened_at INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    closed_at INTEGER NOT NULL,
                    realized_pnl REAL NOT NULL,
                    cooldown_until INTEGER NOT NULL,
                    peak_price REAL NOT NULL DEFAULT 0,
                    partial_take_profit_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (market_id, opened_at)
                )
                """
            )
            _ensure_column(connection, "paper_positions", "peak_price", "REAL NOT NULL DEFAULT 0")
            _ensure_column(connection, "paper_positions", "partial_take_profit_count", "INTEGER NOT NULL DEFAULT 0")
            connection.execute(
                """
                UPDATE paper_positions
                SET peak_price = entry_price
                WHERE status = 'open' AND peak_price <= 0
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO paper_position_history (
                    market_id, side, entry_price, shares, notional, opened_at,
                    status, closed_at, realized_pnl, cooldown_until, peak_price, partial_take_profit_count
                )
                SELECT market_id, side, entry_price, shares, notional, opened_at,
                       status, closed_at, realized_pnl, cooldown_until, peak_price, partial_take_profit_count
                FROM paper_positions
                WHERE status = 'closed' AND closed_at IS NOT NULL
                """
            )
        self._initialized = True

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
                    yes_price, yes_token_id, no_price, no_token_id, condition_id, fees_enabled, taker_fee_rate, fee_type, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_id) DO UPDATE SET
                    question=excluded.question,
                    slug=excluded.slug,
                    market_type=excluded.market_type,
                    end_date=excluded.end_date,
                    liquidity=excluded.liquidity,
                    volume_24hr=excluded.volume_24hr,
                    yes_price=excluded.yes_price,
                    yes_token_id=excluded.yes_token_id,
                    no_price=excluded.no_price,
                    no_token_id=excluded.no_token_id,
                    condition_id=excluded.condition_id,
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
                        market.no_price,
                        market.no_token_id,
                        market.condition_id,
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
                       yes_price, yes_token_id, no_price, no_token_id, condition_id, fees_enabled, taker_fee_rate, fee_type
                FROM markets
                ORDER BY volume_24hr DESC
                """
            ).fetchall()
        return [_market_from_row(row) for row in rows]

    def load_markets_observed_after(self, cutoff_timestamp: float) -> list[Market]:
        if not self.enabled or not Path(self.sqlite_path).exists():
            return []
        self.init()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT market_id, question, slug, end_date, liquidity, volume_24hr,
                       yes_price, yes_token_id, no_price, no_token_id, condition_id, fees_enabled, taker_fee_rate, fee_type
                FROM markets
                WHERE observed_at >= ?
                ORDER BY volume_24hr DESC
                """,
                (cutoff_timestamp,),
            ).fetchall()
        return [_market_from_row(row) for row in rows]

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

    def save_paper_snapshots(self, rows: list[PaperSignalRow]) -> None:
        if not self.enabled or not rows:
            return
        self.init()
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO paper_snapshots (
                    run_timestamp, market_id, market_type, yes_price, taker_fee_rate,
                    action, confidence, gross_edge, net_edge, execution_mode,
                    execution_side, limit_price, expected_net_edge, reason, execution_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_timestamp, market_id) DO UPDATE SET
                    market_type=excluded.market_type,
                    yes_price=excluded.yes_price,
                    taker_fee_rate=excluded.taker_fee_rate,
                    action=excluded.action,
                    confidence=excluded.confidence,
                    gross_edge=excluded.gross_edge,
                    net_edge=excluded.net_edge,
                    execution_mode=excluded.execution_mode,
                    execution_side=excluded.execution_side,
                    limit_price=excluded.limit_price,
                    expected_net_edge=excluded.expected_net_edge,
                    reason=excluded.reason,
                    execution_reason=excluded.execution_reason
                """,
                [
                    (
                        row.run_timestamp,
                        row.market_id,
                        row.market_type,
                        row.yes_price,
                        row.taker_fee_rate,
                        row.action,
                        row.confidence,
                        row.gross_edge,
                        row.net_edge,
                        row.execution_mode,
                        row.execution_side,
                        row.limit_price,
                        row.expected_net_edge,
                        row.reason,
                        row.execution_reason,
                    )
                    for row in rows
                ],
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

    def load_price_history_observed_after(self, token_id: str, cutoff_timestamp: float) -> list[PricePoint]:
        if not self.enabled or not token_id or not Path(self.sqlite_path).exists():
            return []
        self.init()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, price
                FROM price_history
                WHERE token_id = ? AND observed_at >= ?
                ORDER BY timestamp
                """,
                (token_id, cutoff_timestamp),
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

    def snapshot_stats(self) -> SnapshotStats:
        if not self.enabled or not Path(self.sqlite_path).exists():
            return SnapshotStats(0, None, None)
        self.init()
        with self._connect() as connection:
            count, first_timestamp, last_timestamp = connection.execute(
                """
                SELECT COUNT(*), MIN(run_timestamp), MAX(run_timestamp)
                FROM paper_snapshots
                """
            ).fetchone()
        return SnapshotStats(
            int(count),
            int(first_timestamp) if first_timestamp is not None else None,
            int(last_timestamp) if last_timestamp is not None else None,
        )

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

    def mark_stale_token(self, token_id: str, market_id: str, reason: str) -> None:
        if not self.enabled or not token_id:
            return
        self.init()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO stale_tokens (token_id, market_id, reason, observed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(token_id) DO UPDATE SET
                    market_id=excluded.market_id,
                    reason=excluded.reason,
                    observed_at=excluded.observed_at
                """,
                (token_id, market_id, reason, time()),
            )

    def is_stale_token(self, token_id: str, max_age_seconds: int = 24 * 3600) -> bool:
        if not self.enabled or not token_id or not Path(self.sqlite_path).exists():
            return False
        self.init()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT observed_at
                FROM stale_tokens
                WHERE token_id = ?
                """,
                (token_id,),
            ).fetchone()
        if row is None:
            return False
        return time() - float(row[0]) <= max_age_seconds

    def save_open_paper_position(self, position: PaperPositionState) -> None:
        if not self.enabled:
            return
        self.init()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO paper_positions (
                    market_id, side, entry_price, shares, notional, opened_at,
                    status, closed_at, realized_pnl, cooldown_until, peak_price, partial_take_profit_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_id) DO UPDATE SET
                    side=excluded.side,
                    entry_price=excluded.entry_price,
                    shares=excluded.shares,
                    notional=excluded.notional,
                    opened_at=excluded.opened_at,
                    status=excluded.status,
                    closed_at=excluded.closed_at,
                    realized_pnl=excluded.realized_pnl,
                    cooldown_until=excluded.cooldown_until,
                    peak_price=excluded.peak_price,
                    partial_take_profit_count=excluded.partial_take_profit_count
                """,
                (
                    position.market_id,
                    position.side,
                    position.entry_price,
                    position.shares,
                    position.notional,
                    position.opened_at,
                    position.status,
                    position.closed_at,
                    position.realized_pnl,
                    position.cooldown_until,
                    position.peak_price,
                    position.partial_take_profit_count,
                ),
            )

    def update_open_paper_position(self, position: PaperPositionState) -> None:
        if not self.enabled:
            return
        self.init()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE paper_positions
                SET shares = ?,
                    notional = ?,
                    realized_pnl = ?,
                    peak_price = ?,
                    partial_take_profit_count = ?
                WHERE market_id = ? AND status = 'open'
                """,
                (
                    position.shares,
                    position.notional,
                    position.realized_pnl,
                    position.peak_price,
                    position.partial_take_profit_count,
                    position.market_id,
                ),
            )

    def close_paper_position(self, market_id: str, closed_at: int, realized_pnl: float, cooldown_until: int) -> None:
        if not self.enabled:
            return
        self.init()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE paper_positions
                SET status = 'closed',
                    closed_at = ?,
                    realized_pnl = ?,
                    cooldown_until = ?
                WHERE market_id = ?
                """,
                (closed_at, realized_pnl, cooldown_until, market_id),
            )
            connection.execute(
                """
                INSERT INTO paper_position_history (
                    market_id, side, entry_price, shares, notional, opened_at,
                    status, closed_at, realized_pnl, cooldown_until, peak_price, partial_take_profit_count
                )
                SELECT market_id, side, entry_price, shares, notional, opened_at,
                       status, closed_at, realized_pnl, cooldown_until, peak_price, partial_take_profit_count
                FROM paper_positions
                WHERE market_id = ? AND status = 'closed' AND closed_at IS NOT NULL
                ON CONFLICT(market_id, opened_at) DO UPDATE SET
                    closed_at=excluded.closed_at,
                    realized_pnl=excluded.realized_pnl,
                    cooldown_until=excluded.cooldown_until,
                    peak_price=excluded.peak_price,
                    partial_take_profit_count=excluded.partial_take_profit_count
                """,
                (market_id,),
            )

    def load_paper_position(self, market_id: str) -> PaperPositionState | None:
        if not self.enabled or not Path(self.sqlite_path).exists():
            return None
        self.init()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT market_id, side, entry_price, shares, notional, opened_at,
                       status, closed_at, realized_pnl, cooldown_until, peak_price, partial_take_profit_count
                FROM paper_positions
                WHERE market_id = ?
                """,
                (market_id,),
            ).fetchone()
        if row is None:
            return None
        return PaperPositionState(
            market_id=str(row[0]),
            side=str(row[1]),
            entry_price=float(row[2]),
            shares=float(row[3]),
            notional=float(row[4]),
            opened_at=int(row[5]),
            status=str(row[6]),
            closed_at=int(row[7]) if row[7] is not None else None,
            realized_pnl=float(row[8]),
            cooldown_until=int(row[9]),
            peak_price=float(row[10]),
            partial_take_profit_count=int(row[11]),
        )

    def load_open_paper_market_ids(self) -> set[str]:
        if not self.enabled or not Path(self.sqlite_path).exists():
            return set()
        self.init()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT market_id
                FROM paper_positions
                WHERE status = 'open'
                """
            ).fetchall()
        return {str(row[0]) for row in rows}

    def load_closed_paper_position_history(self) -> list[PaperPositionState]:
        if not self.enabled or not Path(self.sqlite_path).exists():
            return []
        self.init()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT market_id, side, entry_price, shares, notional, opened_at,
                       status, closed_at, realized_pnl, cooldown_until, peak_price, partial_take_profit_count
                FROM paper_position_history
                ORDER BY closed_at, market_id, opened_at
                """
            ).fetchall()
        return [
            PaperPositionState(
                market_id=str(row[0]),
                side=str(row[1]),
                entry_price=float(row[2]),
                shares=float(row[3]),
                notional=float(row[4]),
                opened_at=int(row[5]),
                status=str(row[6]),
                closed_at=int(row[7]),
                realized_pnl=float(row[8]),
                cooldown_until=int(row[9]),
                peak_price=float(row[10]),
                partial_take_profit_count=int(row[11]),
            )
            for row in rows
        ]

    def load_paper_account_summary(self) -> PaperAccountSummary:
        if not self.enabled or not Path(self.sqlite_path).exists():
            return PaperAccountSummary(0.0, 0, 0)
        self.init()
        with self._connect() as connection:
            closed_pnl, closed_count = connection.execute(
                """
                SELECT COALESCE(SUM(realized_pnl), 0), COUNT(*)
                FROM paper_position_history
                """
            ).fetchone()
            open_pnl, open_count = connection.execute(
                """
                SELECT COALESCE(SUM(realized_pnl), 0), COUNT(*)
                FROM paper_positions
                WHERE status = 'open'
                """
            ).fetchone()
        return PaperAccountSummary(
            realized_pnl=float(closed_pnl) + float(open_pnl),
            open_position_count=int(open_count),
            closed_position_count=int(closed_count),
        )

    def count_recent_paper_losses(self, market_type: str, side: str, since_timestamp: int) -> int:
        if not self.enabled or not Path(self.sqlite_path).exists():
            return 0
        self.init()
        with self._connect() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM paper_position_history h
                JOIN markets m ON m.market_id = h.market_id
                WHERE m.market_type = ?
                  AND h.side = ?
                  AND h.closed_at >= ?
                  AND h.realized_pnl < 0
                """,
                (market_type, side, since_timestamp),
            ).fetchone()[0]
        return int(count)

    def count_recent_paper_losses_by_direction(
        self, market_type: str, direction: str, side: str, since_timestamp: int
    ) -> int:
        if not self.enabled or not Path(self.sqlite_path).exists():
            return 0
        self.init()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT m.question
                FROM paper_position_history h
                JOIN markets m ON m.market_id = h.market_id
                WHERE m.market_type = ?
                  AND h.side = ?
                  AND h.closed_at >= ?
                  AND h.realized_pnl < 0
                """,
                (market_type, side, since_timestamp),
            ).fetchall()
        return sum(1 for (question,) in rows if infer_strike_direction(str(question)) == direction)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path, timeout=30)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection


def storage_from_config(config) -> Storage:
    return Storage(config.storage.enabled, config.storage.sqlite_path)


def _market_from_row(row) -> Market:
    (
        market_id,
        question,
        slug,
        end_date,
        liquidity,
        volume_24hr,
        yes_price,
        yes_token_id,
        no_price,
        no_token_id,
        condition_id,
        fees_enabled,
        taker_fee_rate,
        fee_type,
    ) = row
    prices = []
    if yes_price is not None:
        prices.append(float(yes_price))
    if no_price is not None:
        prices.append(float(no_price))
    elif yes_price is not None:
        prices.append(max(0.0, 1.0 - float(yes_price)))
    token_ids = []
    if yes_token_id:
        token_ids.append(str(yes_token_id))
    if no_token_id:
        token_ids.append(str(no_token_id))
    elif yes_token_id:
        token_ids.append("")
    return Market(
        str(market_id),
        str(question),
        str(slug),
        str(end_date) if end_date else None,
        float(liquidity),
        float(volume_24hr),
        True,
        ["Yes", "No"],
        prices,
        token_ids,
        bool(fees_enabled),
        float(taker_fee_rate) if taker_fee_rate is not None else None,
        str(fee_type) if fee_type else None,
        str(condition_id) if condition_id else None,
    )


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
