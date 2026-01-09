"""
Production Strategy Base Class
==============================

Base class for all production trading strategies.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class SignalDirection(Enum):
    """Signal direction."""
    LONG = "long"
    SHORT = "short"
    CLOSE = "close"
    NONE = "none"


@dataclass
class Signal:
    """Trading signal."""
    symbol: str
    direction: SignalDirection
    strength: float  # 0.0 to 1.0
    price: Decimal
    size: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class StrategyStats:
    """Strategy statistics."""
    name: str
    is_active: bool = True
    total_signals: int = 0
    signals_by_direction: Dict[str, int] = field(default_factory=dict)
    last_signal_time: Optional[datetime] = None
    total_pnl: Decimal = Decimal("0")
    winning_signals: int = 0
    losing_signals: int = 0

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        total = self.winning_signals + self.losing_signals
        if total == 0:
            return 0.0
        return self.winning_signals / total * 100


class BaseStrategy(ABC):
    """
    Abstract base class for production trading strategies.

    All strategies must implement:
    - analyze(): Analyze market data and generate signals
    - get_parameters(): Return strategy parameters
    """

    def __init__(
        self,
        name: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize strategy.

        Args:
            name: Strategy name
            params: Strategy parameters
        """
        self.name = name
        self.params = params or {}
        self._is_active = True
        self._lock = asyncio.Lock()

        # Statistics
        self.stats = StrategyStats(name=name)

        # Signal history
        self.signal_history: List[Signal] = []
        self._max_history = 1000

        logger.info(f"Strategy '{name}' initialized")

    @property
    def is_active(self) -> bool:
        """Check if strategy is active."""
        return self._is_active

    def activate(self):
        """Activate strategy."""
        self._is_active = True
        self.stats.is_active = True
        logger.info(f"Strategy '{self.name}' activated")

    def deactivate(self):
        """Deactivate strategy."""
        self._is_active = False
        self.stats.is_active = False
        logger.info(f"Strategy '{self.name}' deactivated")

    @abstractmethod
    async def analyze(
        self,
        symbol: str,
        price: Decimal,
        bid: Decimal,
        ask: Decimal,
        volume: Decimal,
        timestamp: datetime,
        market_data: Optional[Dict] = None,
    ) -> Optional[Signal]:
        """
        Analyze market data and generate signal.

        Args:
            symbol: Trading symbol
            price: Current price
            bid: Best bid
            ask: Best ask
            volume: Recent volume
            timestamp: Data timestamp
            market_data: Additional market data

        Returns:
            Signal or None
        """
        pass

    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters."""
        pass

    def set_parameters(self, params: Dict[str, Any]):
        """Update strategy parameters."""
        self.params.update(params)
        logger.info(f"Strategy '{self.name}' parameters updated: {params}")

    async def _record_signal(self, signal: Optional[Signal]):
        """Record signal in history and update stats."""
        if signal is None:
            return

        async with self._lock:
            # Update stats
            self.stats.total_signals += 1
            self.stats.last_signal_time = signal.timestamp

            direction = signal.direction.value
            self.stats.signals_by_direction[direction] = (
                self.stats.signals_by_direction.get(direction, 0) + 1
            )

            # Add to history
            self.signal_history.append(signal)

            # Trim history
            if len(self.signal_history) > self._max_history:
                self.signal_history = self.signal_history[-self._max_history:]

    def record_trade_result(self, pnl: Decimal):
        """Record trade result for statistics."""
        self.stats.total_pnl += pnl
        if pnl > 0:
            self.stats.winning_signals += 1
        else:
            self.stats.losing_signals += 1

    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            'name': self.name,
            'is_active': self._is_active,
            'total_signals': self.stats.total_signals,
            'signals_by_direction': self.stats.signals_by_direction,
            'last_signal_time': self.stats.last_signal_time.isoformat() if self.stats.last_signal_time else None,
            'total_pnl': float(self.stats.total_pnl),
            'winning_signals': self.stats.winning_signals,
            'losing_signals': self.stats.losing_signals,
            'win_rate': self.stats.win_rate,
            'parameters': self.params,
        }

    def reset_stats(self):
        """Reset strategy statistics."""
        self.stats = StrategyStats(name=self.name, is_active=self._is_active)
        self.signal_history.clear()
        logger.info(f"Strategy '{self.name}' stats reset")
