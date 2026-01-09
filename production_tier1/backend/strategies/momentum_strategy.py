"""
Production Momentum Strategy
============================

Professional momentum trading strategy with:
- RSI confirmation
- Volume analysis
- Trend detection
- Dynamic position sizing
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
class MomentumState:
    """Current momentum state."""
    momentum: float
    rsi: float
    volume_ratio: float
    trend_strength: float
    is_overbought: bool
    is_oversold: bool


class ProductionMomentumStrategy(BaseStrategy):
    """
    Production momentum strategy with RSI and volume confirmation.

    Entry conditions:
    - Strong positive momentum + RSI not overbought → LONG
    - Strong negative momentum + RSI not oversold → SHORT

    Exit conditions:
    - RSI overbought/oversold
    - Momentum reversal
    - Stop loss / Take profit
    """

    def __init__(
        self,
        params: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize momentum strategy.

        Args:
            params: Strategy parameters
                - lookback: Momentum calculation window (default: 20)
                - rsi_period: RSI calculation period (default: 14)
                - momentum_threshold: Minimum momentum for signal (default: 0.02)
                - rsi_overbought: RSI overbought level (default: 70)
                - rsi_oversold: RSI oversold level (default: 30)
                - volume_threshold: Volume ratio for confirmation (default: 1.5)
                - signal_cooldown: Seconds between signals (default: 300)
                - base_position_size: Base position size (default: 0.01)
                - take_profit_pct: Take profit percentage (default: 0.02)
                - stop_loss_pct: Stop loss percentage (default: 0.01)
        """
        default_params = {
            'lookback': 20,
            'rsi_period': 14,
            'momentum_threshold': Decimal('0.02'),
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'volume_threshold': 1.5,
            'signal_cooldown': 300,
            'base_position_size': Decimal('0.01'),
            'take_profit_pct': Decimal('0.02'),
            'stop_loss_pct': Decimal('0.01'),
        }

        if params:
            default_params.update(params)

        super().__init__('Momentum', default_params)

        # Price and volume history
        max_history = max(self.params['lookback'], self.params['rsi_period']) + 10
        self.price_history: deque = deque(maxlen=max_history)
        self.volume_history: deque = deque(maxlen=max_history)

        # State tracking
        self.current_position: Optional[str] = None  # 'long', 'short', or None
        self.last_signal_time: Optional[datetime] = None
        self.momentum_state: Optional[MomentumState] = None

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
        Analyze market data and generate momentum signal.
        """
        if not self.is_active:
            return None

        # Check cooldown
        if self.last_signal_time:
            time_diff = (timestamp - self.last_signal_time).total_seconds()
            if time_diff < self.params['signal_cooldown']:
                return None

        # Update history
        self.price_history.append(float(price))
        self.volume_history.append(float(volume))

        # Need enough data
        min_data = max(self.params['lookback'], self.params['rsi_period']) + 1
        if len(self.price_history) < min_data:
            return None

        # Calculate momentum state
        self.momentum_state = self._calculate_momentum_state()

        # Generate signal
        signal = self._generate_signal(symbol, price, timestamp)

        if signal:
            await self._record_signal(signal)
            self.last_signal_time = timestamp

        return signal

    def _calculate_momentum_state(self) -> MomentumState:
        """Calculate current momentum state."""
        prices = np.array(list(self.price_history))
        volumes = np.array(list(self.volume_history))

        # Momentum: rate of change over lookback period
        lookback = self.params['lookback']
        if prices[-lookback] > 0:
            momentum = (prices[-1] - prices[-lookback]) / prices[-lookback]
        else:
            momentum = 0.0

        # RSI calculation
        rsi = self._calculate_rsi(prices, self.params['rsi_period'])

        # Volume ratio (recent vs average)
        if len(volumes) >= 10:
            recent_vol = np.mean(volumes[-5:])
            avg_vol = np.mean(volumes[:-5])
            volume_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
        else:
            volume_ratio = 1.0

        # Trend strength (based on EMA alignment)
        if len(prices) >= 20:
            ema_fast = self._ema(prices, 10)
            ema_slow = self._ema(prices, 20)
            if ema_slow > 0:
                trend_strength = (ema_fast - ema_slow) / ema_slow
            else:
                trend_strength = 0.0
        else:
            trend_strength = 0.0

        return MomentumState(
            momentum=momentum,
            rsi=rsi,
            volume_ratio=volume_ratio,
            trend_strength=trend_strength,
            is_overbought=rsi > self.params['rsi_overbought'],
            is_oversold=rsi < self.params['rsi_oversold'],
        )

    def _calculate_rsi(self, prices: np.ndarray, period: int) -> float:
        """Calculate RSI indicator."""
        if len(prices) < period + 1:
            return 50.0  # Neutral

        deltas = np.diff(prices[-period - 1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 100.0
        if avg_gain == 0:
            return 0.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate EMA."""
        if len(prices) < period:
            return float(prices[-1])

        multiplier = 2 / (period + 1)
        ema = float(prices[-period])

        for price in prices[-period + 1:]:
            ema = (float(price) - ema) * multiplier + ema

        return ema

    def _generate_signal(
        self,
        symbol: str,
        price: Decimal,
        timestamp: datetime,
    ) -> Optional[Signal]:
        """Generate momentum-based trading signal."""
        if not self.momentum_state:
            return None

        state = self.momentum_state
        threshold = float(self.params['momentum_threshold'])

        signal_direction = SignalDirection.NONE
        reason_parts = []

        # Entry signals
        if self.current_position is None:
            # LONG entry: positive momentum, not overbought, volume confirmation
            if (state.momentum > threshold and
                not state.is_overbought and
                state.volume_ratio >= self.params['volume_threshold']):

                signal_direction = SignalDirection.LONG
                self.current_position = 'long'
                reason_parts = [
                    f"Momentum +{state.momentum*100:.2f}%",
                    f"RSI {state.rsi:.1f}",
                    f"Vol {state.volume_ratio:.1f}x",
                ]

            # SHORT entry: negative momentum, not oversold, volume confirmation
            elif (state.momentum < -threshold and
                  not state.is_oversold and
                  state.volume_ratio >= self.params['volume_threshold']):

                signal_direction = SignalDirection.SHORT
                self.current_position = 'short'
                reason_parts = [
                    f"Momentum {state.momentum*100:.2f}%",
                    f"RSI {state.rsi:.1f}",
                    f"Vol {state.volume_ratio:.1f}x",
                ]

        # Exit signals
        elif self.current_position == 'long':
            # Exit long on overbought or momentum reversal
            if state.is_overbought or state.momentum < 0:
                signal_direction = SignalDirection.CLOSE
                self.current_position = None
                reason_parts = [
                    "Exit Long",
                    f"RSI {state.rsi:.1f}" if state.is_overbought else f"Mom reversal",
                ]

        elif self.current_position == 'short':
            # Exit short on oversold or momentum reversal
            if state.is_oversold or state.momentum > 0:
                signal_direction = SignalDirection.CLOSE
                self.current_position = None
                reason_parts = [
                    "Exit Short",
                    f"RSI {state.rsi:.1f}" if state.is_oversold else f"Mom reversal",
                ]

        if signal_direction == SignalDirection.NONE:
            return None

        # Calculate confidence
        confidence = self._calculate_confidence(state, signal_direction)

        # Calculate position size
        size = self.params['base_position_size'] * Decimal(str(0.5 + confidence * 0.5))

        # Calculate TP/SL
        tp_pct = self.params['take_profit_pct']
        sl_pct = self.params['stop_loss_pct']

        if signal_direction == SignalDirection.LONG:
            take_profit = price * (1 + tp_pct)
            stop_loss = price * (1 - sl_pct)
        elif signal_direction == SignalDirection.SHORT:
            take_profit = price * (1 - tp_pct)
            stop_loss = price * (1 + sl_pct)
        else:
            take_profit = None
            stop_loss = None

        return Signal(
            symbol=symbol,
            direction=signal_direction,
            strength=confidence,
            price=price,
            size=size,
            take_profit=take_profit,
            stop_loss=stop_loss,
            timestamp=timestamp,
            reason=" | ".join(reason_parts),
            metadata={
                'momentum': state.momentum,
                'rsi': state.rsi,
                'volume_ratio': state.volume_ratio,
                'trend_strength': state.trend_strength,
            }
        )

    def _calculate_confidence(
        self,
        state: MomentumState,
        direction: SignalDirection,
    ) -> float:
        """Calculate signal confidence (0-1)."""
        confidence = 0.5  # Base

        # Momentum strength boost
        mom_strength = abs(state.momentum)
        if mom_strength > 0.04:
            confidence += 0.2
        elif mom_strength > 0.03:
            confidence += 0.15
        elif mom_strength > 0.02:
            confidence += 0.1

        # RSI confirmation boost
        if direction == SignalDirection.LONG and state.rsi < 50:
            confidence += 0.1  # Room to run
        elif direction == SignalDirection.SHORT and state.rsi > 50:
            confidence += 0.1  # Room to fall

        # Volume confirmation boost
        if state.volume_ratio > 2.0:
            confidence += 0.15
        elif state.volume_ratio > 1.5:
            confidence += 0.1

        # Trend alignment boost
        if direction == SignalDirection.LONG and state.trend_strength > 0.01:
            confidence += 0.1
        elif direction == SignalDirection.SHORT and state.trend_strength < -0.01:
            confidence += 0.1

        return min(confidence, 1.0)

    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters."""
        return {
            'lookback': self.params['lookback'],
            'rsi_period': self.params['rsi_period'],
            'momentum_threshold': float(self.params['momentum_threshold']),
            'rsi_overbought': self.params['rsi_overbought'],
            'rsi_oversold': self.params['rsi_oversold'],
            'volume_threshold': self.params['volume_threshold'],
            'signal_cooldown': self.params['signal_cooldown'],
            'base_position_size': float(self.params['base_position_size']),
            'take_profit_pct': float(self.params['take_profit_pct']),
            'stop_loss_pct': float(self.params['stop_loss_pct']),
        }

    def reset_position(self):
        """Reset current position state."""
        self.current_position = None
        logger.info(f"Strategy '{self.name}' position reset")
