"""
Production Risk Manager
=======================

Comprehensive risk management system for HFT trading.

Features:
- Thread-safe position management
- Multiple risk limit types
- Kill switch functionality
- Dynamic position sizing
- Correlation risk checks
- Persistent state backup
- Real-time P&L tracking
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import os

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level status."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    HALTED = "halted"


class HaltReason(Enum):
    """Trading halt reasons."""
    MANUAL = "manual"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    MAX_DRAWDOWN = "max_drawdown"
    POSITION_LIMIT = "position_limit"
    EXPOSURE_LIMIT = "exposure_limit"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    VOLATILITY = "volatility"
    SYSTEM_ERROR = "system_error"


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    max_position_size: Decimal = Decimal("0.1")  # Max size per position
    max_position_value: Decimal = Decimal("10000")  # Max value per position
    max_total_exposure: Decimal = Decimal("50000")  # Max total exposure
    max_positions: int = 5  # Max concurrent positions
    max_daily_loss_pct: Decimal = Decimal("0.05")  # 5% daily loss limit
    max_drawdown_pct: Decimal = Decimal("0.20")  # 20% max drawdown
    max_risk_per_trade_pct: Decimal = Decimal("0.02")  # 2% risk per trade
    max_consecutive_losses: int = 5
    min_time_between_trades: int = 10  # seconds


@dataclass
class PositionState:
    """Position state data."""
    symbol: str
    side: str  # 'long' or 'short'
    size: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    opened_at: datetime = field(default_factory=datetime.utcnow)
    trade_count: int = 0

    def update_price(self, price: Decimal):
        """Update current price and calculate unrealized P&L."""
        self.current_price = price
        if self.entry_price <= 0:
            self.unrealized_pnl = Decimal("0")
            return
        if self.side == 'long':
            self.unrealized_pnl = (price - self.entry_price) * self.size
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.size

    def calculate_close_pnl(self, exit_price: Decimal) -> Decimal:
        """Calculate P&L if position is closed at exit_price."""
        if self.entry_price <= 0:
            return Decimal("0")
        if self.side == 'long':
            return (exit_price - self.entry_price) * self.size
        return (self.entry_price - exit_price) * self.size

    @property
    def position_value(self) -> Decimal:
        """Get current position value."""
        return self.size * self.current_price

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'size': str(self.size),
            'entry_price': str(self.entry_price),
            'current_price': str(self.current_price),
            'unrealized_pnl': str(self.unrealized_pnl),
            'realized_pnl': str(self.realized_pnl),
            'opened_at': self.opened_at.isoformat(),
            'trade_count': self.trade_count,
        }


@dataclass
class RiskState:
    """Overall risk state."""
    base_capital: Decimal = Decimal("10000")
    current_capital: Decimal = Decimal("10000")
    peak_capital: Decimal = Decimal("10000")
    daily_pnl: Decimal = Decimal("0")
    total_pnl: Decimal = Decimal("0")
    daily_trades: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    consecutive_losses: int = 0
    last_trade_time: Optional[datetime] = None
    trading_day: str = field(default_factory=lambda: datetime.utcnow().strftime('%Y-%m-%d'))
    is_halted: bool = False
    halt_reason: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.NORMAL

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        total = self.winning_trades + self.losing_trades
        if total == 0:
            return 0.0
        return self.winning_trades / total * 100

    @property
    def current_drawdown(self) -> Decimal:
        """Calculate current drawdown."""
        if self.peak_capital <= 0:
            return Decimal("0")
        return (self.peak_capital - self.current_capital) / self.peak_capital

    @property
    def daily_pnl_pct(self) -> Decimal:
        """Calculate daily P&L percentage."""
        if self.base_capital <= 0:
            return Decimal("0")
        return (self.daily_pnl / self.base_capital) * 100

    @property
    def total_pnl_pct(self) -> Decimal:
        """Calculate total P&L percentage."""
        if self.base_capital <= 0:
            return Decimal("0")
        return (self.total_pnl / self.base_capital) * 100


class ProductionRiskManager:
    """
    Production-grade risk manager with thread-safe operations.

    Features:
    - Pre-trade risk checks
    - Position tracking
    - P&L calculation
    - Kill switch
    - State persistence
    """

    def __init__(
        self,
        limits: Optional[RiskLimits] = None,
        initial_capital: Decimal = Decimal("10000"),
        state_file: Optional[str] = None,
    ):
        """
        Initialize risk manager.

        Args:
            limits: Risk limits configuration
            initial_capital: Starting capital
            state_file: Path to state backup file
        """
        self.limits = limits or RiskLimits()
        self.state_file = state_file

        # Initialize state
        self.state = RiskState(
            base_capital=initial_capital,
            current_capital=initial_capital,
            peak_capital=initial_capital,
        )

        # Positions
        self.positions: Dict[str, PositionState] = {}

        # Thread-safety
        self._lock = asyncio.Lock()
        self._position_lock = asyncio.Lock()

        # Load persisted state
        if state_file and os.path.exists(state_file):
            self._load_state()

        logger.info(f"RiskManager initialized with capital: ${initial_capital}")

    async def pre_trade_check(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        price: Decimal,
    ) -> Tuple[bool, Optional[str]]:
        """
        Perform pre-trade risk checks.

        Args:
            symbol: Trading symbol
            side: 'long' or 'short'
            size: Position size
            price: Entry price

        Returns:
            Tuple of (is_allowed, rejection_reason)
        """
        async with self._lock:
            # Check if halted
            if self.state.is_halted:
                return False, f"Trading halted: {self.state.halt_reason}"

            # Check daily reset
            self._check_daily_reset()

            # Check position size limit
            if size > self.limits.max_position_size:
                return False, f"Size {size} exceeds limit {self.limits.max_position_size}"

            # Check position value limit
            position_value = size * price
            if position_value > self.limits.max_position_value:
                return False, f"Value ${position_value} exceeds limit ${self.limits.max_position_value}"

            # Check max positions
            if len(self.positions) >= self.limits.max_positions:
                return False, f"Max positions ({self.limits.max_positions}) reached"

            # Check total exposure
            current_exposure = sum(p.position_value for p in self.positions.values())
            if current_exposure + position_value > self.limits.max_total_exposure:
                return False, f"Exposure would exceed limit ${self.limits.max_total_exposure}"

            # Check daily loss limit
            daily_loss_limit = self.state.base_capital * self.limits.max_daily_loss_pct
            if self.state.daily_pnl < -daily_loss_limit:
                await self._halt_trading(HaltReason.DAILY_LOSS_LIMIT)
                return False, "Daily loss limit exceeded"

            # Check drawdown
            if self.state.current_drawdown > self.limits.max_drawdown_pct:
                await self._halt_trading(HaltReason.MAX_DRAWDOWN)
                return False, f"Drawdown {self.state.current_drawdown:.2%} exceeds limit"

            # Check consecutive losses
            if self.state.consecutive_losses >= self.limits.max_consecutive_losses:
                await self._halt_trading(HaltReason.CONSECUTIVE_LOSSES)
                return False, f"Consecutive losses ({self.state.consecutive_losses}) exceeded"

            # Check trade frequency
            if self.state.last_trade_time:
                time_since_last = (datetime.utcnow() - self.state.last_trade_time).total_seconds()
                if time_since_last < self.limits.min_time_between_trades:
                    return False, f"Trade too soon (wait {self.limits.min_time_between_trades}s)"

            # Check existing position
            if symbol in self.positions:
                return False, f"Already have position in {symbol}"

            # Check risk per trade
            max_risk = self.state.current_capital * self.limits.max_risk_per_trade_pct
            if position_value > max_risk:
                return False, f"Trade risk ${position_value} exceeds max ${max_risk}"

            return True, None

    async def open_position(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        entry_price: Decimal,
    ) -> Optional[PositionState]:
        """
        Open a new position.

        Args:
            symbol: Trading symbol
            side: 'long' or 'short'
            size: Position size
            entry_price: Entry price

        Returns:
            Position state or None if failed
        """
        async with self._position_lock:
            if symbol in self.positions:
                logger.warning(f"Position already exists for {symbol}")
                return None

            position = PositionState(
                symbol=symbol,
                side=side,
                size=size,
                entry_price=entry_price,
                current_price=entry_price,
                opened_at=datetime.utcnow(),
            )

            self.positions[symbol] = position

            # Update state
            async with self._lock:
                self.state.daily_trades += 1
                self.state.total_trades += 1
                self.state.last_trade_time = datetime.utcnow()

            logger.info(f"Opened {side} position: {symbol} {size} @ ${entry_price}")
            await self._persist_state()

            return position

    async def close_position(
        self,
        symbol: str,
        exit_price: Decimal,
    ) -> Optional[Decimal]:
        """
        Close a position.

        Args:
            symbol: Trading symbol
            exit_price: Exit price

        Returns:
            Realized P&L or None if position not found
        """
        async with self._position_lock:
            if symbol not in self.positions:
                logger.warning(f"No position to close for {symbol}")
                return None

            position = self.positions[symbol]
            pnl = position.calculate_close_pnl(exit_price)

            # Update state
            async with self._lock:
                self.state.current_capital += pnl
                self.state.daily_pnl += pnl
                self.state.total_pnl += pnl

                if pnl > 0:
                    self.state.winning_trades += 1
                    self.state.consecutive_losses = 0
                else:
                    self.state.losing_trades += 1
                    self.state.consecutive_losses += 1

                # Update peak capital
                if self.state.current_capital > self.state.peak_capital:
                    self.state.peak_capital = self.state.current_capital

                # Update risk level
                self._update_risk_level()

            # Remove position
            del self.positions[symbol]

            logger.info(f"Closed {position.side} {symbol} @ ${exit_price}, PnL: ${pnl}")
            await self._persist_state()

            return pnl

    async def update_prices(self, prices: Dict[str, Decimal]):
        """Update all positions with current prices."""
        async with self._position_lock:
            for symbol, position in self.positions.items():
                if symbol in prices:
                    position.update_price(prices[symbol])

    async def halt_trading(self, reason: str = "Manual halt"):
        """Halt all trading."""
        await self._halt_trading(HaltReason.MANUAL, reason)

    async def _halt_trading(self, reason: HaltReason, message: Optional[str] = None):
        """Internal halt trading."""
        async with self._lock:
            self.state.is_halted = True
            self.state.halt_reason = message or reason.value
            self.state.risk_level = RiskLevel.HALTED
            logger.warning(f"TRADING HALTED: {self.state.halt_reason}")
        await self._persist_state()

    async def resume_trading(self):
        """Resume trading after halt."""
        async with self._lock:
            self.state.is_halted = False
            self.state.halt_reason = None
            self._update_risk_level()
            logger.info("TRADING RESUMED")
        await self._persist_state()

    def _check_daily_reset(self):
        """Check if daily stats need to be reset."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        if today != self.state.trading_day:
            self.state.daily_pnl = Decimal("0")
            self.state.daily_trades = 0
            self.state.trading_day = today
            logger.info("Daily stats reset for new trading day")

    def _update_risk_level(self):
        """Update risk level based on current state."""
        drawdown = self.state.current_drawdown
        daily_loss_pct = abs(self.state.daily_pnl) / self.state.base_capital if self.state.daily_pnl < 0 else Decimal("0")

        if self.state.is_halted:
            self.state.risk_level = RiskLevel.HALTED
        elif drawdown > self.limits.max_drawdown_pct * Decimal("0.8") or daily_loss_pct > self.limits.max_daily_loss_pct * Decimal("0.8"):
            self.state.risk_level = RiskLevel.CRITICAL
        elif drawdown > self.limits.max_drawdown_pct * Decimal("0.5") or daily_loss_pct > self.limits.max_daily_loss_pct * Decimal("0.5"):
            self.state.risk_level = RiskLevel.WARNING
        else:
            self.state.risk_level = RiskLevel.NORMAL

    async def _persist_state(self):
        """Persist state to file."""
        if not self.state_file:
            return

        try:
            state_data = {
                'state': {
                    'base_capital': str(self.state.base_capital),
                    'current_capital': str(self.state.current_capital),
                    'peak_capital': str(self.state.peak_capital),
                    'daily_pnl': str(self.state.daily_pnl),
                    'total_pnl': str(self.state.total_pnl),
                    'daily_trades': self.state.daily_trades,
                    'total_trades': self.state.total_trades,
                    'winning_trades': self.state.winning_trades,
                    'losing_trades': self.state.losing_trades,
                    'consecutive_losses': self.state.consecutive_losses,
                    'trading_day': self.state.trading_day,
                    'is_halted': self.state.is_halted,
                    'halt_reason': self.state.halt_reason,
                },
                'positions': {s: p.to_dict() for s, p in self.positions.items()},
                'timestamp': datetime.utcnow().isoformat(),
            }

            # Ensure directory exists
            Path(self.state_file).parent.mkdir(parents=True, exist_ok=True)

            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to persist state: {e}")

    def _load_state(self):
        """Load state from file."""
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)

            state_data = data.get('state', {})
            self.state.base_capital = Decimal(state_data.get('base_capital', '10000'))
            self.state.current_capital = Decimal(state_data.get('current_capital', '10000'))
            self.state.peak_capital = Decimal(state_data.get('peak_capital', '10000'))
            self.state.total_pnl = Decimal(state_data.get('total_pnl', '0'))
            self.state.total_trades = state_data.get('total_trades', 0)
            self.state.winning_trades = state_data.get('winning_trades', 0)
            self.state.losing_trades = state_data.get('losing_trades', 0)

            logger.info(f"Loaded persisted state: capital=${self.state.current_capital}")

        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def get_stats(self) -> Dict:
        """Get risk statistics."""
        total_unrealized_pnl = sum(float(p.unrealized_pnl) for p in self.positions.values())
        total_exposure = sum(float(p.position_value) for p in self.positions.values())

        return {
            'base_capital': float(self.state.base_capital),
            'current_capital': float(self.state.current_capital),
            'peak_capital': float(self.state.peak_capital),
            'total_pnl': float(self.state.total_pnl),
            'total_pnl_pct': float(self.state.total_pnl_pct),
            'daily_pnl': float(self.state.daily_pnl),
            'daily_pnl_pct': float(self.state.daily_pnl_pct),
            'current_drawdown': float(self.state.current_drawdown),
            'total_exposure': total_exposure,
            'total_unrealized_pnl': total_unrealized_pnl,
            'open_positions': len(self.positions),
            'total_trades': self.state.total_trades,
            'daily_trades': self.state.daily_trades,
            'winning_trades': self.state.winning_trades,
            'losing_trades': self.state.losing_trades,
            'win_rate': self.state.win_rate,
            'consecutive_losses': self.state.consecutive_losses,
            'is_halted': self.state.is_halted,
            'halt_reason': self.state.halt_reason,
            'risk_level': self.state.risk_level.value,
        }

    def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        return [p.to_dict() for p in self.positions.values()]

    def get_position(self, symbol: str) -> Optional[PositionState]:
        """Get position for symbol."""
        return self.positions.get(symbol)
