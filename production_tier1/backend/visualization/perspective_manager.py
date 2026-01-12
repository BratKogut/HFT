"""
Perspective Manager
===================

Real-time data visualization manager using Perspective.

Features:
- Streaming tables for trades, positions, orderbook, signals
- WebSocket integration with FastAPI
- Apache Arrow data format for efficiency
- Interactive dashboards with pivot, filter, sort
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any, Callable
import json

try:
    import perspective
    from perspective import Table, PerspectiveManager as PspManager
    from perspective.handlers.starlette import PerspectiveStarletteHandler
    PERSPECTIVE_AVAILABLE = True
except ImportError:
    PERSPECTIVE_AVAILABLE = False
    perspective = None

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PerspectiveTableConfig:
    """Configuration for a Perspective table."""
    name: str
    schema: Dict[str, str]
    index: Optional[str] = None
    limit: int = 10000  # Max rows to keep


# Table schemas for HFT data
TRADES_SCHEMA = {
    "id": "str",
    "timestamp": "datetime",
    "symbol": "str",
    "side": "str",
    "size": "float",
    "price": "float",
    "value": "float",
    "fees": "float",
    "pnl": "float",
    "pnl_pct": "float",
    "strategy": "str",
    "status": "str",
}

POSITIONS_SCHEMA = {
    "symbol": "str",
    "side": "str",
    "size": "float",
    "entry_price": "float",
    "current_price": "float",
    "value": "float",
    "unrealized_pnl": "float",
    "unrealized_pnl_pct": "float",
    "take_profit": "float",
    "stop_loss": "float",
    "opened_at": "datetime",
    "duration_seconds": "float",
}

ORDERBOOK_SCHEMA = {
    "timestamp": "datetime",
    "symbol": "str",
    "level": "int",
    "bid_price": "float",
    "bid_size": "float",
    "ask_price": "float",
    "ask_size": "float",
    "spread": "float",
    "spread_pct": "float",
    "mid_price": "float",
}

SIGNALS_SCHEMA = {
    "id": "str",
    "timestamp": "datetime",
    "symbol": "str",
    "strategy": "str",
    "direction": "str",
    "strength": "float",
    "price": "float",
    "confidence": "float",
    "status": "str",
    "reason": "str",
}

MARKET_DATA_SCHEMA = {
    "timestamp": "datetime",
    "symbol": "str",
    "price": "float",
    "bid": "float",
    "ask": "float",
    "spread": "float",
    "volume_24h": "float",
    "change_24h_pct": "float",
    "high_24h": "float",
    "low_24h": "float",
}

RISK_METRICS_SCHEMA = {
    "timestamp": "datetime",
    "capital": "float",
    "equity": "float",
    "daily_pnl": "float",
    "daily_pnl_pct": "float",
    "drawdown": "float",
    "drawdown_pct": "float",
    "open_positions": "int",
    "total_exposure": "float",
    "risk_level": "str",
    "is_halted": "bool",
}

PERFORMANCE_SCHEMA = {
    "timestamp": "datetime",
    "total_trades": "int",
    "winning_trades": "int",
    "losing_trades": "int",
    "win_rate": "float",
    "profit_factor": "float",
    "sharpe_ratio": "float",
    "sortino_ratio": "float",
    "max_drawdown": "float",
    "avg_trade_pnl": "float",
    "avg_winner": "float",
    "avg_loser": "float",
}


class PerspectiveManager:
    """
    Manages Perspective tables for real-time HFT visualization.

    Usage:
        manager = PerspectiveManager()
        await manager.initialize()

        # Update data
        manager.update_trades([{...}])
        manager.update_positions([{...}])

        # Get handler for FastAPI
        handler = manager.get_starlette_handler()
    """

    def __init__(self):
        """Initialize Perspective manager."""
        if not PERSPECTIVE_AVAILABLE:
            logger.warning("Perspective not available - visualization disabled")
            self._enabled = False
            return

        self._enabled = True
        self._manager: Optional[PspManager] = None
        self._tables: Dict[str, Table] = {}
        self._lock = asyncio.Lock()

        # Table configurations
        self._table_configs = {
            "trades": PerspectiveTableConfig(
                name="trades",
                schema=TRADES_SCHEMA,
                index="id",
                limit=10000,
            ),
            "positions": PerspectiveTableConfig(
                name="positions",
                schema=POSITIONS_SCHEMA,
                index="symbol",
                limit=100,
            ),
            "orderbook": PerspectiveTableConfig(
                name="orderbook",
                schema=ORDERBOOK_SCHEMA,
                limit=500,
            ),
            "signals": PerspectiveTableConfig(
                name="signals",
                schema=SIGNALS_SCHEMA,
                index="id",
                limit=1000,
            ),
            "market_data": PerspectiveTableConfig(
                name="market_data",
                schema=MARKET_DATA_SCHEMA,
                index="symbol",
                limit=100,
            ),
            "risk_metrics": PerspectiveTableConfig(
                name="risk_metrics",
                schema=RISK_METRICS_SCHEMA,
                limit=1000,
            ),
            "performance": PerspectiveTableConfig(
                name="performance",
                schema=PERFORMANCE_SCHEMA,
                limit=1000,
            ),
        }

        logger.info("PerspectiveManager initialized")

    @property
    def enabled(self) -> bool:
        """Check if Perspective is enabled."""
        return self._enabled

    async def initialize(self) -> bool:
        """Initialize Perspective manager and create tables."""
        if not self._enabled:
            return False

        async with self._lock:
            try:
                # Create manager
                self._manager = PspManager()

                # Create tables
                for name, config in self._table_configs.items():
                    table = self._manager.new_table(
                        config.schema,
                        index=config.index,
                        limit=config.limit,
                    )
                    self._tables[name] = table
                    logger.info(f"Created Perspective table: {name}")

                logger.info("Perspective tables initialized successfully")
                return True

            except Exception as e:
                logger.error(f"Failed to initialize Perspective: {e}")
                self._enabled = False
                return False

    def get_starlette_handler(self) -> Optional[PerspectiveStarletteHandler]:
        """Get Starlette/FastAPI WebSocket handler."""
        if not self._enabled or not self._manager:
            return None
        return PerspectiveStarletteHandler(manager=self._manager)

    def get_table(self, name: str) -> Optional[Table]:
        """Get a Perspective table by name."""
        return self._tables.get(name)

    # ==================
    # Update Methods
    # ==================

    def update_trades(self, trades: List[Dict[str, Any]]) -> None:
        """Update trades table with new data."""
        if not self._enabled or "trades" not in self._tables:
            return

        try:
            # Convert to proper format
            data = []
            for trade in trades:
                data.append({
                    "id": str(trade.get("id", "")),
                    "timestamp": self._parse_datetime(trade.get("timestamp")),
                    "symbol": trade.get("symbol", ""),
                    "side": trade.get("side", ""),
                    "size": float(trade.get("size", 0)),
                    "price": float(trade.get("price", 0)),
                    "value": float(trade.get("size", 0)) * float(trade.get("price", 0)),
                    "fees": float(trade.get("fees", 0)),
                    "pnl": float(trade.get("pnl", 0)),
                    "pnl_pct": float(trade.get("pnl_pct", 0)),
                    "strategy": trade.get("strategy", ""),
                    "status": trade.get("status", ""),
                })

            self._tables["trades"].update(data)

        except Exception as e:
            logger.error(f"Error updating trades table: {e}")

    def update_positions(self, positions: List[Dict[str, Any]]) -> None:
        """Update positions table with new data."""
        if not self._enabled or "positions" not in self._tables:
            return

        try:
            data = []
            now = datetime.utcnow()

            for pos in positions:
                entry_price = float(pos.get("entry_price", 0))
                current_price = float(pos.get("current_price", entry_price))
                size = float(pos.get("size", 0))
                side = pos.get("side", "long")

                # Calculate PnL
                if side == "long":
                    pnl = (current_price - entry_price) * size
                    pnl_pct = ((current_price / entry_price) - 1) * 100 if entry_price > 0 else 0
                else:
                    pnl = (entry_price - current_price) * size
                    pnl_pct = ((entry_price / current_price) - 1) * 100 if current_price > 0 else 0

                # Calculate duration
                opened_at = self._parse_datetime(pos.get("opened_at", now))
                duration = (now - opened_at).total_seconds() if opened_at else 0

                data.append({
                    "symbol": pos.get("symbol", ""),
                    "side": side,
                    "size": size,
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "value": size * current_price,
                    "unrealized_pnl": pnl,
                    "unrealized_pnl_pct": pnl_pct,
                    "take_profit": float(pos.get("take_profit", 0)),
                    "stop_loss": float(pos.get("stop_loss", 0)),
                    "opened_at": opened_at,
                    "duration_seconds": duration,
                })

            self._tables["positions"].update(data)

        except Exception as e:
            logger.error(f"Error updating positions table: {e}")

    def update_orderbook(self, symbol: str, bids: List, asks: List) -> None:
        """Update orderbook table with new data."""
        if not self._enabled or "orderbook" not in self._tables:
            return

        try:
            data = []
            now = datetime.utcnow()

            max_levels = min(len(bids), len(asks), 20)

            for i in range(max_levels):
                bid_price = float(bids[i][0]) if i < len(bids) else 0
                bid_size = float(bids[i][1]) if i < len(bids) else 0
                ask_price = float(asks[i][0]) if i < len(asks) else 0
                ask_size = float(asks[i][1]) if i < len(asks) else 0

                mid_price = (bid_price + ask_price) / 2 if bid_price > 0 and ask_price > 0 else 0
                spread = ask_price - bid_price
                spread_pct = (spread / mid_price * 100) if mid_price > 0 else 0

                data.append({
                    "timestamp": now,
                    "symbol": symbol,
                    "level": i + 1,
                    "bid_price": bid_price,
                    "bid_size": bid_size,
                    "ask_price": ask_price,
                    "ask_size": ask_size,
                    "spread": spread,
                    "spread_pct": spread_pct,
                    "mid_price": mid_price,
                })

            self._tables["orderbook"].update(data)

        except Exception as e:
            logger.error(f"Error updating orderbook table: {e}")

    def update_signals(self, signals: List[Dict[str, Any]]) -> None:
        """Update signals table with new data."""
        if not self._enabled or "signals" not in self._tables:
            return

        try:
            data = []
            for signal in signals:
                data.append({
                    "id": str(signal.get("id", "")),
                    "timestamp": self._parse_datetime(signal.get("timestamp")),
                    "symbol": signal.get("symbol", ""),
                    "strategy": signal.get("strategy", ""),
                    "direction": signal.get("direction", ""),
                    "strength": float(signal.get("strength", 0)),
                    "price": float(signal.get("price", 0)),
                    "confidence": float(signal.get("confidence", 0)),
                    "status": signal.get("status", "pending"),
                    "reason": signal.get("reason", ""),
                })

            self._tables["signals"].update(data)

        except Exception as e:
            logger.error(f"Error updating signals table: {e}")

    def update_market_data(self, ticker: Dict[str, Any]) -> None:
        """Update market data table with ticker."""
        if not self._enabled or "market_data" not in self._tables:
            return

        try:
            data = [{
                "timestamp": self._parse_datetime(ticker.get("timestamp")),
                "symbol": ticker.get("symbol", ""),
                "price": float(ticker.get("last", 0)),
                "bid": float(ticker.get("bid", 0)),
                "ask": float(ticker.get("ask", 0)),
                "spread": float(ticker.get("ask", 0)) - float(ticker.get("bid", 0)),
                "volume_24h": float(ticker.get("volume_24h", 0)),
                "change_24h_pct": float(ticker.get("change_24h_pct", 0)),
                "high_24h": float(ticker.get("high_24h", 0)),
                "low_24h": float(ticker.get("low_24h", 0)),
            }]

            self._tables["market_data"].update(data)

        except Exception as e:
            logger.error(f"Error updating market_data table: {e}")

    def update_risk_metrics(self, metrics: Dict[str, Any]) -> None:
        """Update risk metrics table."""
        if not self._enabled or "risk_metrics" not in self._tables:
            return

        try:
            data = [{
                "timestamp": datetime.utcnow(),
                "capital": float(metrics.get("capital", 0)),
                "equity": float(metrics.get("equity", 0)),
                "daily_pnl": float(metrics.get("daily_pnl", 0)),
                "daily_pnl_pct": float(metrics.get("daily_pnl_pct", 0)),
                "drawdown": float(metrics.get("drawdown", 0)),
                "drawdown_pct": float(metrics.get("drawdown_pct", 0)),
                "open_positions": int(metrics.get("open_positions", 0)),
                "total_exposure": float(metrics.get("total_exposure", 0)),
                "risk_level": metrics.get("risk_level", "normal"),
                "is_halted": bool(metrics.get("is_halted", False)),
            }]

            self._tables["risk_metrics"].update(data)

        except Exception as e:
            logger.error(f"Error updating risk_metrics table: {e}")

    def update_performance(self, stats: Dict[str, Any]) -> None:
        """Update performance metrics table."""
        if not self._enabled or "performance" not in self._tables:
            return

        try:
            data = [{
                "timestamp": datetime.utcnow(),
                "total_trades": int(stats.get("total_trades", 0)),
                "winning_trades": int(stats.get("winning_trades", 0)),
                "losing_trades": int(stats.get("losing_trades", 0)),
                "win_rate": float(stats.get("win_rate", 0)),
                "profit_factor": float(stats.get("profit_factor", 0)),
                "sharpe_ratio": float(stats.get("sharpe_ratio", 0)),
                "sortino_ratio": float(stats.get("sortino_ratio", 0)),
                "max_drawdown": float(stats.get("max_drawdown", 0)),
                "avg_trade_pnl": float(stats.get("avg_trade_pnl", 0)),
                "avg_winner": float(stats.get("avg_winner", 0)),
                "avg_loser": float(stats.get("avg_loser", 0)),
            }]

            self._tables["performance"].update(data)

        except Exception as e:
            logger.error(f"Error updating performance table: {e}")

    # ==================
    # Helper Methods
    # ==================

    def _parse_datetime(self, value: Any) -> datetime:
        """Parse datetime from various formats."""
        if value is None:
            return datetime.utcnow()
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return datetime.utcnow()
        return datetime.utcnow()

    def get_table_names(self) -> List[str]:
        """Get list of available table names."""
        return list(self._tables.keys())

    async def get_table_data(self, table_name: str, limit: int = 100) -> List[Dict]:
        """Get data from a table as list of dicts."""
        if table_name not in self._tables:
            return []

        try:
            view = self._tables[table_name].view()
            data = view.to_records()
            return data[:limit] if limit else data
        except Exception as e:
            logger.error(f"Error getting table data: {e}")
            return []

    def clear_table(self, table_name: str) -> None:
        """Clear all data from a table."""
        if table_name in self._tables:
            self._tables[table_name].clear()

    def clear_all(self) -> None:
        """Clear all tables."""
        for table in self._tables.values():
            table.clear()
