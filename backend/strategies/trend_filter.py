"""
Trend Filter - Detect Market Regime

Identifies market conditions:
- Strong Uptrend
- Strong Downtrend
- Range/Choppy
- Volatile

Used to filter trading signals and adapt strategy behavior.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
from enum import Enum
from dataclasses import dataclass


class TrendDirection(str, Enum):
    """Trend direction"""
    STRONG_UP = 'strong_up'
    WEAK_UP = 'weak_up'
    NEUTRAL = 'neutral'
    WEAK_DOWN = 'weak_down'
    STRONG_DOWN = 'strong_down'


class MarketRegime(str, Enum):
    """Market regime"""
    TRENDING_UP = 'trending_up'
    TRENDING_DOWN = 'trending_down'
    RANGE_BOUND = 'range_bound'
    VOLATILE = 'volatile'


@dataclass
class TrendState:
    """Current trend state"""
    direction: TrendDirection
    regime: MarketRegime
    strength: float  # 0-1, how strong the trend is
    momentum: float  # Rate of change
    volatility: float  # Current volatility level
    confidence: float  # 0-1, confidence in the assessment


class TrendFilter:
    """
    Multi-timeframe trend filter
    
    Uses multiple indicators:
    - Moving averages (fast/slow crossover)
    - Rate of change (momentum)
    - ATR (volatility)
    - Price action (higher highs/lower lows)
    """
    
    def __init__(self,
                 fast_period: int = 50,      # Fast MA period (increased for better trend detection)
                 slow_period: int = 200,     # Slow MA period (increased for stronger trend signal)
                 momentum_period: int = 60,  # Momentum lookback (increased)
                 atr_period: int = 14,       # ATR period
                 trend_threshold: float = 0.003,  # 0.3% for trend (more sensitive)
                 strong_threshold: float = 0.010):  # 1.0% for strong trend (adjusted)
        
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.momentum_period = momentum_period
        self.atr_period = atr_period
        self.trend_threshold = trend_threshold
        self.strong_threshold = strong_threshold
        
        # Price history
        self.prices = []
        self.highs = []
        self.lows = []
        
    def update(self, price: float, high: float = None, low: float = None) -> TrendState:
        """
        Update trend filter with new price data
        
        Args:
            price: Current close price
            high: High price (optional, defaults to price)
            low: Low price (optional, defaults to price)
        
        Returns:
            TrendState with current assessment
        """
        # Add to history
        self.prices.append(price)
        self.highs.append(high if high is not None else price)
        self.lows.append(low if low is not None else price)
        
        # Keep only necessary history
        max_period = max(self.slow_period, self.momentum_period, self.atr_period)
        if len(self.prices) > max_period * 2:
            self.prices = self.prices[-max_period * 2:]
            self.highs = self.highs[-max_period * 2:]
            self.lows = self.lows[-max_period * 2:]
        
        # Need enough data
        if len(self.prices) < self.slow_period:
            return TrendState(
                direction=TrendDirection.NEUTRAL,
                regime=MarketRegime.RANGE_BOUND,
                strength=0.0,
                momentum=0.0,
                volatility=0.0,
                confidence=0.0
            )
        
        # Calculate indicators
        fast_ma = self._calculate_ma(self.fast_period)
        slow_ma = self._calculate_ma(self.slow_period)
        momentum = self._calculate_momentum()
        volatility = self._calculate_volatility()
        
        # Determine trend direction
        direction = self._determine_direction(price, fast_ma, slow_ma, momentum)
        
        # Determine market regime
        regime = self._determine_regime(momentum, volatility)
        
        # Calculate trend strength
        strength = self._calculate_strength(price, fast_ma, slow_ma, momentum)
        
        # Calculate confidence
        confidence = self._calculate_confidence(direction, momentum, volatility)
        
        return TrendState(
            direction=direction,
            regime=regime,
            strength=strength,
            momentum=momentum,
            volatility=volatility,
            confidence=confidence
        )
    
    def _calculate_ma(self, period: int) -> float:
        """Calculate moving average"""
        if len(self.prices) < period:
            return self.prices[-1]
        
        return np.mean(self.prices[-period:])
    
    def _calculate_momentum(self) -> float:
        """
        Calculate momentum (rate of change)
        
        Returns percentage change over momentum_period
        """
        if len(self.prices) < self.momentum_period:
            return 0.0
        
        old_price = self.prices[-self.momentum_period]
        current_price = self.prices[-1]
        
        return (current_price - old_price) / old_price
    
    def _calculate_volatility(self) -> float:
        """
        Calculate volatility using ATR (Average True Range)
        
        Returns ATR as percentage of price
        """
        if len(self.prices) < self.atr_period:
            return 0.0
        
        # Calculate true ranges
        true_ranges = []
        for i in range(-self.atr_period, 0):
            high = self.highs[i]
            low = self.lows[i]
            prev_close = self.prices[i-1] if i > -len(self.prices) else self.prices[i]
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        # ATR = average of true ranges
        atr = np.mean(true_ranges)
        
        # Return as percentage of price
        return atr / self.prices[-1]
    
    def _determine_direction(self, price: float, fast_ma: float, slow_ma: float, momentum: float) -> TrendDirection:
        """Determine trend direction"""
        
        # Strong uptrend: price > fast MA > slow MA, strong momentum
        if price > fast_ma > slow_ma and momentum > self.strong_threshold:
            return TrendDirection.STRONG_UP
        
        # Weak uptrend: price > fast MA, positive momentum
        elif price > fast_ma and momentum > self.trend_threshold:
            return TrendDirection.WEAK_UP
        
        # Strong downtrend: price < fast MA < slow MA, strong negative momentum
        elif price < fast_ma < slow_ma and momentum < -self.strong_threshold:
            return TrendDirection.STRONG_DOWN
        
        # Weak downtrend: price < fast MA, negative momentum
        elif price < fast_ma and momentum < -self.trend_threshold:
            return TrendDirection.WEAK_DOWN
        
        # Neutral: no clear trend
        else:
            return TrendDirection.NEUTRAL
    
    def _determine_regime(self, momentum: float, volatility: float) -> MarketRegime:
        """Determine market regime"""
        
        # High volatility = volatile regime
        if volatility > 0.02:  # 2% ATR
            return MarketRegime.VOLATILE
        
        # Strong momentum = trending
        if abs(momentum) > self.strong_threshold:
            if momentum > 0:
                return MarketRegime.TRENDING_UP
            else:
                return MarketRegime.TRENDING_DOWN
        
        # Low momentum, low volatility = range bound
        elif abs(momentum) < self.trend_threshold and volatility < 0.01:
            return MarketRegime.RANGE_BOUND
        
        # Default
        else:
            if momentum > 0:
                return MarketRegime.TRENDING_UP
            else:
                return MarketRegime.TRENDING_DOWN
    
    def _calculate_strength(self, price: float, fast_ma: float, slow_ma: float, momentum: float) -> float:
        """
        Calculate trend strength (0-1)
        
        Based on:
        - Distance from MAs
        - Momentum magnitude
        - MA alignment
        """
        # Distance from fast MA
        ma_distance = abs(price - fast_ma) / price
        
        # Momentum magnitude
        momentum_strength = min(abs(momentum) / self.strong_threshold, 1.0)
        
        # MA alignment (fast vs slow)
        ma_alignment = abs(fast_ma - slow_ma) / slow_ma
        ma_alignment_strength = min(ma_alignment / 0.05, 1.0)  # 5% = max
        
        # Combined strength
        strength = (ma_distance * 0.3 + momentum_strength * 0.5 + ma_alignment_strength * 0.2)
        
        return min(strength, 1.0)
    
    def _calculate_confidence(self, direction: TrendDirection, momentum: float, volatility: float) -> float:
        """
        Calculate confidence in trend assessment (0-1)
        
        Higher confidence when:
        - Clear direction (not neutral)
        - Strong momentum
        - Low volatility (stable trend)
        """
        # Direction confidence
        if direction in [TrendDirection.STRONG_UP, TrendDirection.STRONG_DOWN]:
            direction_conf = 1.0
        elif direction in [TrendDirection.WEAK_UP, TrendDirection.WEAK_DOWN]:
            direction_conf = 0.6
        else:
            direction_conf = 0.3
        
        # Momentum confidence
        momentum_conf = min(abs(momentum) / self.strong_threshold, 1.0)
        
        # Volatility confidence (inverse - lower volatility = higher confidence)
        volatility_conf = max(1.0 - (volatility / 0.03), 0.0)  # 3% ATR = 0 confidence
        
        # Combined confidence
        confidence = (direction_conf * 0.4 + momentum_conf * 0.3 + volatility_conf * 0.3)
        
        return confidence
    
    def should_trade_long(self, trend_state: TrendState) -> Tuple[bool, str]:
        """
        Check if conditions are favorable for LONG trades
        
        Returns: (should_trade, reason)
        """
        # Don't long in downtrend
        if trend_state.direction in [TrendDirection.STRONG_DOWN, TrendDirection.WEAK_DOWN]:
            return False, f"Downtrend ({trend_state.direction})"
        
        # Be cautious in high volatility
        if trend_state.volatility > 0.03:
            return False, f"High volatility ({trend_state.volatility*100:.1f}%)"
        
        # Prefer trending up or neutral
        if trend_state.direction in [TrendDirection.STRONG_UP, TrendDirection.WEAK_UP, TrendDirection.NEUTRAL]:
            return True, f"Favorable ({trend_state.direction})"
        
        return True, "Neutral conditions"
    
    def should_trade_short(self, trend_state: TrendState) -> Tuple[bool, str]:
        """
        Check if conditions are favorable for SHORT trades
        
        Returns: (should_trade, reason)
        """
        # Don't short in uptrend
        if trend_state.direction in [TrendDirection.STRONG_UP, TrendDirection.WEAK_UP]:
            return False, f"Uptrend ({trend_state.direction})"
        
        # Be cautious in high volatility
        if trend_state.volatility > 0.03:
            return False, f"High volatility ({trend_state.volatility*100:.1f}%)"
        
        # Prefer trending down or neutral
        if trend_state.direction in [TrendDirection.STRONG_DOWN, TrendDirection.WEAK_DOWN, TrendDirection.NEUTRAL]:
            return True, f"Favorable ({trend_state.direction})"
        
        return True, "Neutral conditions"
    
    def get_position_size_multiplier(self, trend_state: TrendState, trade_direction: str) -> float:
        """
        Get position size multiplier based on trend alignment
        
        Args:
            trend_state: Current trend state
            trade_direction: 'long' or 'short'
        
        Returns:
            Multiplier (0.5 - 1.5)
        """
        # Base multiplier
        multiplier = 1.0
        
        # Increase size if trend aligns with trade
        if trade_direction == 'long':
            if trend_state.direction == TrendDirection.STRONG_UP:
                multiplier = 1.5
            elif trend_state.direction == TrendDirection.WEAK_UP:
                multiplier = 1.2
            elif trend_state.direction in [TrendDirection.WEAK_DOWN, TrendDirection.STRONG_DOWN]:
                multiplier = 0.5  # Reduce size if against trend
        
        elif trade_direction == 'short':
            if trend_state.direction == TrendDirection.STRONG_DOWN:
                multiplier = 1.5
            elif trend_state.direction == TrendDirection.WEAK_DOWN:
                multiplier = 1.2
            elif trend_state.direction in [TrendDirection.WEAK_UP, TrendDirection.STRONG_UP]:
                multiplier = 0.5  # Reduce size if against trend
        
        # Adjust for confidence
        multiplier *= (0.5 + trend_state.confidence * 0.5)  # 0.5x to 1.0x based on confidence
        
        return multiplier


# Example usage
if __name__ == "__main__":
    # Test trend filter
    print("="*80)
    print("🎯 TREND FILTER TEST")
    print("="*80)
    print()
    
    trend_filter = TrendFilter()
    
    # Simulate uptrend (need more data for longer periods)
    print("📈 Simulating UPTREND...")
    for i in range(300):  # Increased to 300 for slow_period=200
        price = 90000 + i * 30 + np.random.randn() * 100  # Steady uptrend
        high = price + abs(np.random.randn() * 50)
        low = price - abs(np.random.randn() * 50)
        
        trend_state = trend_filter.update(price, high, low)
    
    print(f"Direction: {trend_state.direction}")
    print(f"Regime: {trend_state.regime}")
    print(f"Strength: {trend_state.strength:.2f}")
    print(f"Momentum: {trend_state.momentum*100:.2f}%")
    print(f"Volatility: {trend_state.volatility*100:.2f}%")
    print(f"Confidence: {trend_state.confidence:.2f}")
    print()
    
    # Check trade conditions
    can_long, reason = trend_filter.should_trade_long(trend_state)
    print(f"Can LONG: {can_long} ({reason})")
    
    can_short, reason = trend_filter.should_trade_short(trend_state)
    print(f"Can SHORT: {can_short} ({reason})")
    
    print()
    print("="*80)
