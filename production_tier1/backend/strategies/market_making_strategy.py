"""
Production Market Making Strategy
=================================

Professional market making strategy with:
- Dynamic spread adjustment
- Inventory management
- Trend detection
- Risk controls
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
import numpy as np

from .base_strategy import BaseStrategy, Signal, SignalDirection

logger = logging.getLogger(__name__)


@dataclass
class MarketState:
    """Current market state."""
    mid_price: Decimal
    spread: Decimal
    volatility: float
    trend: float  # -1 to 1
    volume_imbalance: float  # -1 to 1
    momentum: float


class ProductionMarketMakingStrategy(BaseStrategy):
    """
    Production market making strategy.

    Features:
    - Dynamic spread based on volatility and inventory
    - Trend detection to avoid adverse selection
    - Inventory management with skew
    - Volume imbalance analysis
    """

    def __init__(
        self,
        params: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize market making strategy.

        Args:
            params: Strategy parameters
                - base_spread: Base spread (default: 0.0003 = 3bps)
                - order_size: Base order size (default: 0.01)
                - max_position: Maximum position size (default: 0.1)
                - inventory_target: Target inventory (default: 0)
                - volatility_window: Volatility calculation window (default: 60)
                - trend_window: Trend detection window (default: 30)
                - min_spread: Minimum spread (default: 0.0001)
                - max_spread: Maximum spread (default: 0.002)
                - signal_cooldown: Minimum seconds between signals (default: 60)
        """
        default_params = {
            'base_spread': Decimal('0.0003'),
            'order_size': Decimal('0.01'),
            'max_position': Decimal('0.1'),
            'inventory_target': Decimal('0'),
            'volatility_window': 60,
            'trend_window': 30,
            'min_spread': Decimal('0.0001'),
            'max_spread': Decimal('0.002'),
            'signal_cooldown': 60,
        }

        if params:
            default_params.update(params)

        super().__init__('MarketMaking', default_params)

        # Price history
        self.price_history: deque = deque(maxlen=self.params['volatility_window'])
        self.volume_history: deque = deque(maxlen=self.params['volatility_window'])

        # State tracking
        self.current_position = Decimal('0')
        self.last_signal_time: Optional[datetime] = None

        # Market state
        self.market_state: Optional[MarketState] = None

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
        Analyze market and generate signal.

        Returns signal to place bid/ask orders for market making.
        """
        if not self.is_active:
            return None

        # Check cooldown
        if self.last_signal_time:
            time_diff = (timestamp - self.last_signal_time).total_seconds()
            if time_diff < self.params['signal_cooldown']:
                return None

        # Update price history
        self.price_history.append(float(price))
        self.volume_history.append(float(volume))

        # Need enough data
        if len(self.price_history) < self.params['trend_window']:
            return None

        # Calculate market state
        self.market_state = self._calculate_market_state(price, bid, ask)

        # Generate signal
        signal = self._generate_signal(symbol, price, timestamp)

        if signal:
            await self._record_signal(signal)
            self.last_signal_time = timestamp

        return signal

    def _calculate_market_state(
        self,
        price: Decimal,
        bid: Decimal,
        ask: Decimal,
    ) -> MarketState:
        """Calculate current market state."""
        prices = np.array(list(self.price_history))

        # Mid price and spread
        mid_price = (bid + ask) / 2
        spread = (ask - bid) / mid_price if mid_price > 0 else Decimal('0')

        # Volatility (annualized)
        if len(prices) > 1:
            returns = np.diff(prices) / prices[:-1]
            volatility = float(np.std(returns)) * np.sqrt(525600)  # Annualize for 1-minute bars
        else:
            volatility = 0.0

        # Trend (-1 to 1)
        trend_window = min(self.params['trend_window'], len(prices))
        if trend_window > 1:
            trend_prices = prices[-trend_window:]
            trend = (trend_prices[-1] - trend_prices[0]) / trend_prices[0] if trend_prices[0] > 0 else 0
            # Normalize to -1 to 1
            trend = max(-1, min(1, trend * 100))  # Scale factor
        else:
            trend = 0.0

        # Momentum (rate of change)
        if len(prices) >= 5:
            short_ma = np.mean(prices[-5:])
            long_ma = np.mean(prices[-min(20, len(prices)):])
            momentum = (short_ma - long_ma) / long_ma if long_ma > 0 else 0
        else:
            momentum = 0.0

        # Volume imbalance (simplified)
        volumes = list(self.volume_history)
        if len(volumes) >= 2:
            recent_vol = np.mean(volumes[-5:]) if len(volumes) >= 5 else volumes[-1]
            avg_vol = np.mean(volumes)
            volume_imbalance = (recent_vol - avg_vol) / avg_vol if avg_vol > 0 else 0
        else:
            volume_imbalance = 0.0

        return MarketState(
            mid_price=mid_price,
            spread=spread,
            volatility=volatility,
            trend=trend,
            volume_imbalance=volume_imbalance,
            momentum=momentum,
        )

    def _generate_signal(
        self,
        symbol: str,
        price: Decimal,
        timestamp: datetime,
    ) -> Optional[Signal]:
        """Generate market making signal."""
        if not self.market_state:
            return None

        state = self.market_state

        # Calculate dynamic spread
        spread = self._calculate_dynamic_spread(state)

        # Calculate inventory skew
        skew = self._calculate_inventory_skew()

        # Determine signal direction based on market conditions
        signal_direction = self._determine_signal_direction(state, skew)

        if signal_direction == SignalDirection.NONE:
            return None

        # Calculate order prices
        if signal_direction == SignalDirection.LONG:
            # Place bid (buy)
            entry_price = state.mid_price * (1 - spread / 2 - skew)
            take_profit = entry_price * (1 + spread)
            stop_loss = entry_price * (1 - spread * 2)
        else:  # SHORT
            # Place ask (sell)
            entry_price = state.mid_price * (1 + spread / 2 + skew)
            take_profit = entry_price * (1 - spread)
            stop_loss = entry_price * (1 + spread * 2)

        # Calculate confidence
        confidence = self._calculate_confidence(state, skew)

        # Position sizing
        size = self.params['order_size'] * Decimal(str(0.5 + confidence * 0.5))

        return Signal(
            symbol=symbol,
            direction=signal_direction,
            strength=confidence,
            price=entry_price,
            size=size,
            take_profit=take_profit,
            stop_loss=stop_loss,
            timestamp=timestamp,
            reason=self._build_reason(state, spread, skew),
            metadata={
                'spread': float(spread),
                'skew': float(skew),
                'volatility': state.volatility,
                'trend': state.trend,
            }
        )

    def _calculate_dynamic_spread(self, state: MarketState) -> Decimal:
        """
        Calculate dynamic spread based on market conditions.

        Wider spread when:
        - Volatility is high
        - Strong trend (adverse selection risk)
        - Inventory imbalance
        """
        base_spread = self.params['base_spread']

        # Volatility adjustment (higher vol = wider spread)
        vol_multiplier = 1 + min(state.volatility, 1.0)

        # Trend adjustment (stronger trend = wider spread)
        trend_multiplier = 1 + abs(state.trend) * 0.5

        # Calculate final spread
        spread = base_spread * Decimal(str(vol_multiplier * trend_multiplier))

        # Clamp to min/max
        spread = max(self.params['min_spread'], min(self.params['max_spread'], spread))

        return spread

    def _calculate_inventory_skew(self) -> Decimal:
        """
        Calculate inventory skew for order placement.

        Positive skew = prefer to sell (reduce long inventory)
        Negative skew = prefer to buy (reduce short inventory)
        """
        max_position = self.params['max_position']
        target = self.params['inventory_target']

        if max_position <= 0:
            return Decimal('0')

        # Calculate deviation from target
        deviation = (self.current_position - target) / max_position

        # Skew proportional to deviation
        skew = deviation * Decimal('0.001')  # 0.1% skew per 100% inventory

        return skew

    def _determine_signal_direction(
        self,
        state: MarketState,
        skew: Decimal,
    ) -> SignalDirection:
        """Determine signal direction based on market conditions."""
        # Don't trade during strong trends (adverse selection)
        if abs(state.trend) > 0.7:
            return SignalDirection.NONE

        # Don't trade during high volatility
        if state.volatility > 0.5:
            return SignalDirection.NONE

        # Inventory management takes priority
        if self.current_position > self.params['max_position'] * Decimal('0.8'):
            return SignalDirection.SHORT  # Need to reduce long inventory

        if self.current_position < -self.params['max_position'] * Decimal('0.8'):
            return SignalDirection.LONG  # Need to reduce short inventory

        # Normal market making - alternate or use skew
        if skew > Decimal('0.0005'):
            return SignalDirection.SHORT  # Prefer to sell
        elif skew < Decimal('-0.0005'):
            return SignalDirection.LONG  # Prefer to buy
        else:
            # Neutral - use momentum
            if state.momentum > 0.001:
                return SignalDirection.LONG
            elif state.momentum < -0.001:
                return SignalDirection.SHORT
            else:
                return SignalDirection.LONG  # Default to buy in range market

    def _calculate_confidence(
        self,
        state: MarketState,
        skew: Decimal,
    ) -> float:
        """Calculate signal confidence."""
        confidence = 0.5  # Base

        # Lower confidence in volatile markets
        confidence -= min(state.volatility * 0.3, 0.2)

        # Lower confidence in trending markets
        confidence -= abs(state.trend) * 0.2

        # Higher confidence near inventory target
        if abs(skew) < Decimal('0.0002'):
            confidence += 0.1

        # Clamp
        return max(0.2, min(1.0, confidence))

    def _build_reason(
        self,
        state: MarketState,
        spread: Decimal,
        skew: Decimal,
    ) -> str:
        """Build signal reason string."""
        parts = [
            f"MM spread {float(spread)*10000:.1f}bps",
            f"vol {state.volatility:.2%}",
            f"trend {state.trend:+.2f}",
        ]
        if abs(skew) > Decimal('0.0001'):
            parts.append(f"skew {float(skew)*10000:+.1f}bps")
        return " | ".join(parts)

    def update_position(self, delta: Decimal):
        """Update current position."""
        self.current_position += delta
        logger.debug(f"Position updated: {self.current_position}")

    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters."""
        return {
            'base_spread': float(self.params['base_spread']),
            'order_size': float(self.params['order_size']),
            'max_position': float(self.params['max_position']),
            'inventory_target': float(self.params['inventory_target']),
            'volatility_window': self.params['volatility_window'],
            'trend_window': self.params['trend_window'],
            'min_spread': float(self.params['min_spread']),
            'max_spread': float(self.params['max_spread']),
            'signal_cooldown': self.params['signal_cooldown'],
        }
