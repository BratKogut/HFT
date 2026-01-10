"""
Live Trading Controller
=======================

Production-ready live trading orchestrator that coordinates:
- Real-time market data feeds
- Strategy signal execution
- Risk management integration
- Order lifecycle management

Safety Features:
- Circuit breaker for automatic halt
- Position size validation
- Rate limiting protection
- Emergency kill switch
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
import signal

from exchange.exchange_adapter import (
    ExchangeAdapter,
    OrderRequest,
    OrderSide,
    OrderType,
    Ticker,
)
from risk.risk_manager import ProductionRiskManager, RiskLevel
from strategies.base_strategy import BaseStrategy, Signal, SignalDirection

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Trading mode enumeration."""
    STOPPED = "stopped"
    PAPER = "paper"  # Uses simulated exchange
    SANDBOX = "sandbox"  # Uses exchange testnet
    LIVE = "live"  # Real money trading


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Trading halted
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class TradingConfig:
    """Live trading configuration."""
    # Trading pair
    symbol: str = "BTC/USDT"

    # Order execution
    default_order_size: Decimal = Decimal("0.001")
    max_order_size: Decimal = Decimal("0.1")
    use_limit_orders: bool = False
    limit_order_offset_pct: Decimal = Decimal("0.0001")  # 0.01%

    # Timing
    tick_interval_ms: int = 100  # Main loop interval
    signal_check_interval_ms: int = 1000  # Signal evaluation interval
    position_update_interval_ms: int = 5000  # Position sync interval

    # Safety
    max_daily_trades: int = 100
    max_hourly_trades: int = 20
    cooldown_after_loss_seconds: int = 60
    max_consecutive_losses: int = 3

    # Circuit breaker
    circuit_breaker_threshold: int = 5  # Errors before tripping
    circuit_breaker_reset_seconds: int = 300  # 5 minutes


@dataclass
class TradingState:
    """Current trading state."""
    mode: TradingMode = TradingMode.STOPPED
    is_active: bool = False
    current_position: Optional[Dict] = None
    last_signal: Optional[Signal] = None
    last_trade_time: Optional[datetime] = None

    # Statistics
    trades_today: int = 0
    trades_this_hour: int = 0
    daily_pnl: Decimal = Decimal("0")
    session_pnl: Decimal = Decimal("0")

    # Circuit breaker
    circuit_state: CircuitBreakerState = CircuitBreakerState.CLOSED
    consecutive_errors: int = 0
    last_error_time: Optional[datetime] = None


class LiveTradingController:
    """
    Production live trading controller.

    Orchestrates real-time trading by:
    1. Subscribing to market data
    2. Evaluating strategy signals
    3. Executing orders with risk checks
    4. Managing position lifecycle
    """

    def __init__(
        self,
        exchange: ExchangeAdapter,
        risk_manager: ProductionRiskManager,
        strategies: List[BaseStrategy],
        config: Optional[TradingConfig] = None,
    ):
        """
        Initialize live trading controller.

        Args:
            exchange: Exchange adapter for order execution
            risk_manager: Risk management system
            strategies: List of trading strategies
            config: Trading configuration
        """
        self.exchange = exchange
        self.risk_manager = risk_manager
        self.strategies = strategies
        self.config = config or TradingConfig()
        self.state = TradingState()

        # Async components
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._tasks: List[asyncio.Task] = []

        # Callbacks
        self._trade_callbacks: List[Callable[[Dict], Any]] = []
        self._error_callbacks: List[Callable[[Exception], Any]] = []

        # Price history for strategies
        self._price_history: List[Ticker] = []
        self._max_history = 1000

        # Trade tracking
        self._hourly_trades: List[datetime] = []
        self._daily_trades: List[datetime] = []

    async def start(self, mode: TradingMode = TradingMode.PAPER) -> bool:
        """
        Start live trading.

        Args:
            mode: Trading mode (paper, sandbox, or live)

        Returns:
            True if started successfully
        """
        async with self._lock:
            if self.state.is_active:
                logger.warning("Trading already active")
                return False

            # Validate mode transition
            if mode == TradingMode.LIVE:
                if not await self._validate_live_mode():
                    return False

            self.state.mode = mode
            self.state.is_active = True
            self.state.circuit_state = CircuitBreakerState.CLOSED

            # Reset daily stats if new day
            self._reset_daily_stats_if_needed()

            # Start main loops
            self._stop_event.clear()
            self._tasks = [
                asyncio.create_task(self._market_data_loop()),
                asyncio.create_task(self._signal_loop()),
                asyncio.create_task(self._position_sync_loop()),
                asyncio.create_task(self._health_check_loop()),
            ]

            logger.info(f"Live trading started in {mode.value} mode")
            return True

    async def stop(self, emergency: bool = False) -> None:
        """
        Stop live trading.

        Args:
            emergency: If True, cancel all open orders immediately
        """
        async with self._lock:
            if not self.state.is_active:
                return

            self._stop_event.set()

            # Cancel tasks
            for task in self._tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            self._tasks = []

            # Emergency handling
            if emergency:
                await self._emergency_close_positions()

            self.state.is_active = False
            self.state.mode = TradingMode.STOPPED

            logger.info(f"Live trading stopped (emergency={emergency})")

    async def _validate_live_mode(self) -> bool:
        """Validate system is ready for live trading."""
        checks = []

        # Check exchange connection
        try:
            ticker = await self.exchange.get_ticker(self.config.symbol)
            checks.append(("Exchange connection", ticker is not None))
        except Exception as e:
            logger.error(f"Exchange check failed: {e}")
            checks.append(("Exchange connection", False))

        # Check risk manager
        if self.risk_manager.state.is_halted:
            checks.append(("Risk manager", False))
        else:
            checks.append(("Risk manager", True))

        # Check strategies
        active_strategies = [s for s in self.strategies if s.is_active]
        checks.append(("Active strategies", len(active_strategies) > 0))

        # Log results
        all_passed = all(passed for _, passed in checks)
        for check_name, passed in checks:
            status = "✓" if passed else "✗"
            logger.info(f"Live mode check: {status} {check_name}")

        if not all_passed:
            logger.error("Live mode validation failed - cannot start live trading")

        return all_passed

    async def _market_data_loop(self) -> None:
        """Main market data subscription loop."""
        interval = self.config.tick_interval_ms / 1000

        while not self._stop_event.is_set():
            try:
                # Fetch latest ticker
                ticker = await self.exchange.get_ticker(self.config.symbol)

                if ticker:
                    # Store in history
                    self._price_history.append(ticker)
                    if len(self._price_history) > self._max_history:
                        self._price_history = self._price_history[-self._max_history:]

                    # Update risk manager prices
                    await self.risk_manager.update_prices({
                        self.config.symbol: ticker.last
                    })

                    # Reset error counter on success
                    self.state.consecutive_errors = 0

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                await self._handle_error(e, "market_data_loop")
                await asyncio.sleep(interval * 2)  # Back off on error

    async def _signal_loop(self) -> None:
        """Strategy signal evaluation loop."""
        interval = self.config.signal_check_interval_ms / 1000

        while not self._stop_event.is_set():
            try:
                # Check circuit breaker
                if self.state.circuit_state == CircuitBreakerState.OPEN:
                    await asyncio.sleep(interval)
                    continue

                # Skip if no recent price data
                if not self._price_history:
                    await asyncio.sleep(interval)
                    continue

                # Prepare market data for strategies
                market_data = self._prepare_market_data()

                # Evaluate each strategy
                for strategy in self.strategies:
                    if not strategy.is_active:
                        continue

                    try:
                        signal = await strategy.generate_signal(market_data)

                        if signal and signal.direction != SignalDirection.NEUTRAL:
                            await self._process_signal(signal, strategy)

                    except Exception as e:
                        logger.error(f"Strategy {strategy.name} error: {e}")

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                await self._handle_error(e, "signal_loop")
                await asyncio.sleep(interval)

    async def _position_sync_loop(self) -> None:
        """Position synchronization loop."""
        interval = self.config.position_update_interval_ms / 1000

        while not self._stop_event.is_set():
            try:
                # Get current position from risk manager
                positions = self.risk_manager.get_positions()

                # Update state
                symbol_position = next(
                    (p for p in positions if p.get('symbol') == self.config.symbol),
                    None
                )
                self.state.current_position = symbol_position

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                await self._handle_error(e, "position_sync_loop")
                await asyncio.sleep(interval)

    async def _health_check_loop(self) -> None:
        """Health monitoring and circuit breaker management."""
        while not self._stop_event.is_set():
            try:
                # Clean up trade tracking
                now = datetime.utcnow()
                hour_ago = now - timedelta(hours=1)
                day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

                self._hourly_trades = [t for t in self._hourly_trades if t > hour_ago]
                self._daily_trades = [t for t in self._daily_trades if t > day_start]

                self.state.trades_this_hour = len(self._hourly_trades)
                self.state.trades_today = len(self._daily_trades)

                # Check circuit breaker reset
                if self.state.circuit_state == CircuitBreakerState.OPEN:
                    if self.state.last_error_time:
                        elapsed = (now - self.state.last_error_time).total_seconds()
                        if elapsed > self.config.circuit_breaker_reset_seconds:
                            self.state.circuit_state = CircuitBreakerState.HALF_OPEN
                            logger.info("Circuit breaker entering half-open state")

                # Check risk level
                if self.risk_manager.state.risk_level == RiskLevel.CRITICAL:
                    await self.stop(emergency=True)
                    break

                await asyncio.sleep(10)  # Check every 10 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(10)

    async def _process_signal(self, signal: Signal, strategy: BaseStrategy) -> None:
        """
        Process trading signal with full validation.

        Args:
            signal: Trading signal from strategy
            strategy: Strategy that generated the signal
        """
        # Rate limiting checks
        if self.state.trades_this_hour >= self.config.max_hourly_trades:
            logger.warning("Hourly trade limit reached")
            return

        if self.state.trades_today >= self.config.max_daily_trades:
            logger.warning("Daily trade limit reached")
            return

        # Cooldown check
        if self.state.last_trade_time:
            elapsed = (datetime.utcnow() - self.state.last_trade_time).total_seconds()
            if elapsed < signal.cooldown_seconds:
                return

        # Determine order side
        if signal.direction == SignalDirection.LONG:
            side = OrderSide.BUY
        elif signal.direction == SignalDirection.SHORT:
            side = OrderSide.SELL
        else:
            return

        # Calculate order size
        order_size = min(
            signal.suggested_size or self.config.default_order_size,
            self.config.max_order_size
        )

        # Get current price
        if not self._price_history:
            return
        current_price = self._price_history[-1].last

        # Pre-trade risk check
        allowed, reason = await self.risk_manager.pre_trade_check(
            symbol=self.config.symbol,
            side="long" if side == OrderSide.BUY else "short",
            size=order_size,
            price=current_price,
        )

        if not allowed:
            logger.info(f"Trade rejected by risk manager: {reason}")
            return

        # Execute order
        await self._execute_order(
            side=side,
            size=order_size,
            price=current_price,
            signal=signal,
            strategy_name=strategy.name,
        )

    async def _execute_order(
        self,
        side: OrderSide,
        size: Decimal,
        price: Decimal,
        signal: Signal,
        strategy_name: str,
    ) -> None:
        """Execute order through exchange."""
        try:
            # Determine order type and price
            if self.config.use_limit_orders:
                order_type = OrderType.LIMIT
                offset = price * self.config.limit_order_offset_pct
                limit_price = price - offset if side == OrderSide.BUY else price + offset
            else:
                order_type = OrderType.MARKET
                limit_price = None

            # Create order request
            request = OrderRequest(
                symbol=self.config.symbol,
                side=side,
                order_type=order_type,
                quantity=size,
                price=limit_price,
            )

            # Execute
            result = await self.exchange.place_order(request)

            if result.success:
                # Update state
                now = datetime.utcnow()
                self.state.last_trade_time = now
                self.state.last_signal = signal
                self._hourly_trades.append(now)
                self._daily_trades.append(now)

                # Update risk manager
                position_side = "long" if side == OrderSide.BUY else "short"
                await self.risk_manager.open_position(
                    symbol=self.config.symbol,
                    side=position_side,
                    size=result.filled_quantity,
                    entry_price=result.filled_price or price,
                )

                # Notify callbacks
                trade_info = {
                    'order_id': result.order_id,
                    'symbol': self.config.symbol,
                    'side': side.value,
                    'size': float(result.filled_quantity),
                    'price': float(result.filled_price or price),
                    'strategy': strategy_name,
                    'signal_strength': signal.strength,
                    'timestamp': now.isoformat(),
                }

                for callback in self._trade_callbacks:
                    try:
                        await callback(trade_info)
                    except Exception as e:
                        logger.error(f"Trade callback error: {e}")

                logger.info(
                    f"Order executed: {side.value} {size} {self.config.symbol} "
                    f"@ {result.filled_price or price} ({strategy_name})"
                )

                # Reset circuit breaker on successful trade
                if self.state.circuit_state == CircuitBreakerState.HALF_OPEN:
                    self.state.circuit_state = CircuitBreakerState.CLOSED
                    logger.info("Circuit breaker closed - trading resumed")

            else:
                logger.error(f"Order failed: {result.error_message}")
                await self._handle_error(
                    Exception(result.error_message or "Order failed"),
                    "execute_order"
                )

        except Exception as e:
            await self._handle_error(e, "execute_order")

    async def _handle_error(self, error: Exception, context: str) -> None:
        """Handle errors with circuit breaker logic."""
        logger.error(f"Error in {context}: {error}")

        self.state.consecutive_errors += 1
        self.state.last_error_time = datetime.utcnow()

        # Notify error callbacks
        for callback in self._error_callbacks:
            try:
                await callback(error)
            except Exception as e:
                logger.error(f"Error callback failed: {e}")

        # Check circuit breaker
        if self.state.consecutive_errors >= self.config.circuit_breaker_threshold:
            self.state.circuit_state = CircuitBreakerState.OPEN
            logger.warning(
                f"Circuit breaker OPEN - {self.state.consecutive_errors} consecutive errors"
            )

    async def _emergency_close_positions(self) -> None:
        """Emergency close all positions."""
        logger.warning("Emergency close - closing all positions")

        positions = self.risk_manager.get_positions()

        for position in positions:
            if position.get('symbol') == self.config.symbol and position.get('size', 0) > 0:
                try:
                    side = OrderSide.SELL if position.get('side') == 'long' else OrderSide.BUY
                    size = Decimal(str(position.get('size', 0)))

                    request = OrderRequest(
                        symbol=self.config.symbol,
                        side=side,
                        order_type=OrderType.MARKET,
                        quantity=size,
                    )

                    result = await self.exchange.place_order(request)

                    if result.success:
                        await self.risk_manager.close_position(
                            symbol=self.config.symbol,
                            exit_price=result.filled_price or Decimal("0"),
                        )
                        logger.info(f"Emergency closed position: {position}")
                    else:
                        logger.error(f"Failed to close position: {result.error_message}")

                except Exception as e:
                    logger.error(f"Emergency close error: {e}")

    def _prepare_market_data(self) -> Dict:
        """Prepare market data dict for strategies."""
        if not self._price_history:
            return {}

        latest = self._price_history[-1]

        return {
            'symbol': self.config.symbol,
            'bid': latest.bid,
            'ask': latest.ask,
            'last': latest.last,
            'spread': latest.ask - latest.bid,
            'timestamp': latest.timestamp,
            'price_history': [t.last for t in self._price_history[-100:]],
        }

    def _reset_daily_stats_if_needed(self) -> None:
        """Reset daily statistics if new trading day."""
        now = datetime.utcnow()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        self._daily_trades = [t for t in self._daily_trades if t > day_start]
        self.state.trades_today = len(self._daily_trades)

    def register_trade_callback(self, callback: Callable[[Dict], Any]) -> None:
        """Register callback for trade notifications."""
        self._trade_callbacks.append(callback)

    def register_error_callback(self, callback: Callable[[Exception], Any]) -> None:
        """Register callback for error notifications."""
        self._error_callbacks.append(callback)

    def get_status(self) -> Dict:
        """Get current trading status."""
        return {
            'mode': self.state.mode.value,
            'is_active': self.state.is_active,
            'circuit_state': self.state.circuit_state.value,
            'trades_today': self.state.trades_today,
            'trades_this_hour': self.state.trades_this_hour,
            'daily_pnl': float(self.state.daily_pnl),
            'session_pnl': float(self.state.session_pnl),
            'current_position': self.state.current_position,
            'last_trade_time': (
                self.state.last_trade_time.isoformat()
                if self.state.last_trade_time else None
            ),
            'price_history_length': len(self._price_history),
            'active_strategies': [s.name for s in self.strategies if s.is_active],
        }
