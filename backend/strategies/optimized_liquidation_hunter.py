#!/usr/bin/env python3
"""
Optimized Liquidation Hunter Strategy

Improvements over simple version:
1. Entry filters (signal strength > 0.7)
2. Trend filter (don't SHORT in strong uptrend)
3. Optimized TP/SL
4. Better position sizing
"""

import numpy as np
from typing import Dict, Optional

class OptimizedLiquidationHunter:
    def __init__(self, 
                 signal_threshold=0.75,      # Balanced - quality signals
                 trend_lookback=200,         # Trend detection period
                 trend_threshold=0.005,      # 0.5% trend threshold
                 take_profit_pct=0.022,      # 2.2% TP - realistic target
                 stop_loss_pct=0.007,        # 0.7% SL - not too tight (3.1:1 ratio)
                 min_volume_ratio=1.4,       # Balanced volume requirement
                 min_price_extremity=0.83):  # Balanced extremity (83%)
        
        self.signal_threshold = signal_threshold
        self.trend_lookback = trend_lookback
        self.trend_threshold = trend_threshold
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.min_volume_ratio = min_volume_ratio
        self.min_price_extremity = min_price_extremity
        
        # State
        self.price_history = []
        self.volume_history = []
        
    def analyze(self, tick: Dict) -> Optional[Dict]:
        """
        Analyze tick and generate signal if conditions met
        
        Returns signal dict or None
        """
        # Input validation
        if not tick or not isinstance(tick, dict):
            return None
        
        price = tick.get('close', 0)
        volume = tick.get('volume', 0)
        
        # Validate price
        if price <= 0 or price > 1_000_000 or not np.isfinite(price):
            return None
        
        # Validate volume
        if volume < 0 or not np.isfinite(volume):
            return None
        
        # Update history
        self.price_history.append(price)
        self.volume_history.append(volume)
        
        # Keep only recent history
        if len(self.price_history) > self.trend_lookback:
            self.price_history = self.price_history[-self.trend_lookback:]
            self.volume_history = self.volume_history[-self.trend_lookback:]
        
        # Need enough history
        if len(self.price_history) < self.trend_lookback:
            return None
        
        # 1. Detect trend
        trend_direction, trend_strength = self._detect_trend()
        
        # 2. Detect liquidation setup
        liq_signal, liq_confidence = self._detect_liquidation_setup(price, volume)
        
        # 3. Calculate combined confidence
        confidence = liq_confidence
        
        # Boost confidence if trend supports
        if liq_signal == 'SHORT' and trend_direction == 'DOWN':
            confidence *= 1.2
        elif liq_signal == 'LONG' and trend_direction == 'UP':
            confidence *= 1.2
        
        # Reduce confidence if trend opposes
        if liq_signal == 'SHORT' and trend_direction == 'UP' and trend_strength > 0.7:
            confidence *= 0.5  # Strong uptrend, risky to SHORT
        elif liq_signal == 'LONG' and trend_direction == 'DOWN' and trend_strength > 0.7:
            confidence *= 0.5  # Strong downtrend, risky to LONG
        
        # 4. Filter: Only trade if confidence > threshold
        if confidence < self.signal_threshold:
            return None
        
        # 5. Generate signal
        if liq_signal:
            return {
                'side': liq_signal,
                'confidence': min(confidence, 1.0),
                'price': price,
                'take_profit_pct': self.take_profit_pct,
                'stop_loss_pct': self.stop_loss_pct,
                'reason': f'liquidation_{liq_signal.lower()}_trend_{trend_direction.lower()}',
                'trend_direction': trend_direction,
                'trend_strength': trend_strength
            }
        
        return None
    
    def _detect_trend(self):
        """
        Detect trend using moving averages
        
        Returns: (direction, strength)
        """
        if len(self.price_history) < self.trend_lookback:
            return 'NEUTRAL', 0.0
        
        # Fast and slow MA
        fast_period = 50
        slow_period = 200
        
        fast_ma = np.mean(self.price_history[-fast_period:])
        slow_ma = np.mean(self.price_history[-slow_period:])
        
        # Check for zero to prevent division by zero
        if slow_ma == 0 or fast_ma == 0:
            return 'NEUTRAL', 0.0
        
        # Trend strength
        diff_pct = (fast_ma - slow_ma) / slow_ma
        
        if diff_pct > self.trend_threshold:
            direction = 'UP'
            strength = min(abs(diff_pct) / 0.02, 1.0)  # Normalize to 0-1
        elif diff_pct < -self.trend_threshold:
            direction = 'DOWN'
            strength = min(abs(diff_pct) / 0.02, 1.0)
        else:
            direction = 'NEUTRAL'
            strength = 0.0
        
        return direction, strength
    
    def _detect_liquidation_setup(self, price, volume):
        """
        Detect potential liquidation setup
        
        Returns: (signal, confidence)
        """
        if len(self.price_history) < 20 or len(self.volume_history) < 20:
            return None, 0.0
        
        # Recent price action (last 15 minutes)
        recent_prices = self.price_history[-15:]
        recent_volumes = self.volume_history[-15:]
        
        # Average volume
        avg_volume = np.mean(self.volume_history[-100:]) if len(self.volume_history) >= 100 else np.mean(self.volume_history)
        
        # Current price relative to recent range
        recent_high = max(recent_prices)
        recent_low = min(recent_prices)
        recent_range = recent_high - recent_low
        
        # Check for zero range to prevent division by zero
        if recent_range == 0 or recent_range < 0.0001:  # Also check for very small range
            return None, 0.0
        
        # Price position in range (0 = low, 1 = high)
        price_position = (price - recent_low) / recent_range
        
        # Volume spike detection
        current_volume = volume
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Liquidation signals
        signal = None
        confidence = 0.0
        
        # SHORT signal: Price at recent high + volume spike (stricter)
        if price_position > self.min_price_extremity and volume_ratio > self.min_volume_ratio:
            signal = 'SHORT'
            # Confidence based on extremity and volume
            confidence = 0.6 + (price_position - self.min_price_extremity) * 3.0  # Higher base
            confidence += min((volume_ratio - self.min_volume_ratio) * 0.15, 0.4)  # More volume weight
            confidence = min(confidence, 1.0)
        
        # LONG signal: Price at recent low + volume spike (stricter)
        elif price_position < (1 - self.min_price_extremity) and volume_ratio > self.min_volume_ratio:
            signal = 'LONG'
            # Confidence based on extremity and volume
            confidence = 0.6 + ((1 - self.min_price_extremity) - price_position) * 3.0  # Higher base
            confidence += min((volume_ratio - self.min_volume_ratio) * 0.15, 0.4)  # More volume weight
            confidence = min(confidence, 1.0)
        
        return signal, confidence
    
    def reset(self):
        """Reset strategy state"""
        self.price_history = []
        self.volume_history = []


if __name__ == '__main__':
    # Test strategy
    strategy = OptimizedLiquidationHunter()
    
    # Simulate some ticks
    test_ticks = [
        {'close': 93000, 'volume': 100},
        {'close': 93100, 'volume': 105},
        {'close': 93200, 'volume': 110},
        {'close': 93500, 'volume': 300},  # Volume spike at high
    ]
    
    for tick in test_ticks:
        signal = strategy.analyze(tick)
        if signal:
            print(f"Signal: {signal}")
