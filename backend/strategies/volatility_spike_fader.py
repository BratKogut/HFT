"""
Volatility Spike Fader Strategy

Exploits market overreactions by fading extreme price movements.

How it works:
1. Detect volatility spikes (>3% move in 15 minutes)
2. Identify overreaction (price deviates from mean)
3. Fade the spike (trade in opposite direction)
4. Take profit on mean reversion

Target: 55-65% win rate, 1.0-2.0% avg profit per trade
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque


@dataclass
class SpikeEvent:
    """Represents a detected volatility spike"""
    timestamp: datetime
    direction: str  # 'up' or 'down'
    magnitude: float  # Percentage change
    peak_price: float
    base_price: float
    volume_ratio: float  # Volume vs average


class VolatilitySpikeDetector:
    """
    Detects volatility spikes in price action
    """
    
    def __init__(self,
                 spike_threshold: float = 0.03,  # 3% move = spike
                 spike_window: int = 15,         # 15 minutes
                 volume_threshold: float = 2.0):  # 2x average volume
        
        self.spike_threshold = spike_threshold
        self.spike_window = spike_window
        self.volume_threshold = volume_threshold
        
        # Price history
        self.prices = deque(maxlen=spike_window)
        self.volumes = deque(maxlen=100)  # For volume average
        self.timestamps = deque(maxlen=spike_window)
        
    def update(self, price: float, volume: float, timestamp: datetime) -> Optional[SpikeEvent]:
        """
        Update detector with new price data
        
        Returns SpikeEvent if spike detected, None otherwise
        """
        self.prices.append(price)
        self.volumes.append(volume)
        self.timestamps.append(timestamp)
        
        # Need enough data
        if len(self.prices) < self.spike_window:
            return None
        
        # Calculate price change over window
        base_price = self.prices[0]
        current_price = self.prices[-1]
        price_change = (current_price - base_price) / base_price
        
        # Check for spike
        if abs(price_change) >= self.spike_threshold:
            # Calculate volume ratio
            avg_volume = np.mean(list(self.volumes)[:-self.spike_window]) if len(self.volumes) > self.spike_window else np.mean(self.volumes)
            recent_volume = np.mean(list(self.volumes)[-self.spike_window:])
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Determine direction
            direction = 'up' if price_change > 0 else 'down'
            
            # Find peak price
            if direction == 'up':
                peak_price = max(self.prices)
            else:
                peak_price = min(self.prices)
            
            return SpikeEvent(
                timestamp=timestamp,
                direction=direction,
                magnitude=abs(price_change),
                peak_price=peak_price,
                base_price=base_price,
                volume_ratio=volume_ratio
            )
        
        return None


class VolatilitySpikeFader:
    """
    Fades volatility spikes for mean reversion profits
    
    Entry conditions:
    - Spike detected (>3% move in 15 min)
    - High volume confirmation (optional)
    - Not in strong trend (optional filter)
    
    Exit conditions:
    - Take profit: 1.0-2.0% reversion
    - Stop loss: 0.8-1.2% if spike continues
    - Time stop: 60 minutes max
    """
    
    def __init__(self,
                 spike_threshold: float = 0.012,      # 1.2% spike (realistic for BTC)
                 min_spike_magnitude: float = 0.010,  # Min 1.0% for trade
                 base_take_profit_pct: float = 0.008,  # 0.8% TP (tighter for smaller moves)
                 base_stop_loss_pct: float = 0.006,    # 0.6% SL (tighter)
                 max_hold_time: int = 3600):           # 60 minutes
        
        self.spike_threshold = spike_threshold
        self.min_spike_magnitude = min_spike_magnitude
        self.base_take_profit_pct = base_take_profit_pct
        self.base_stop_loss_pct = base_stop_loss_pct
        self.max_hold_time = max_hold_time
        
        # Components
        self.spike_detector = VolatilitySpikeDetector(spike_threshold=spike_threshold)
        
        # State
        self.last_spike: Optional[SpikeEvent] = None
        self.spike_cooldown = 300  # 5 minutes between spikes
        
        # Statistics
        self.signals_generated = 0
        self.trades_executed = 0
        self.wins = 0
        self.losses = 0
        
    def analyze_market(self,
                      current_price: float,
                      volume: float,
                      timestamp: datetime) -> Optional[Dict]:
        """
        Analyze market for spike opportunities
        
        Returns signal dict or None
        """
        # Update spike detector
        spike = self.spike_detector.update(current_price, volume, timestamp)
        
        if not spike:
            return None
        
        # Check cooldown
        if self.last_spike:
            time_since_last = (timestamp - self.last_spike.timestamp).total_seconds()
            if time_since_last < self.spike_cooldown:
                return None
        
        # Check minimum magnitude
        if spike.magnitude < self.min_spike_magnitude:
            return None
        
        # Generate signal
        signal = self._generate_signal(spike, current_price, timestamp)
        
        if signal:
            self.signals_generated += 1
            self.last_spike = spike
        
        return signal
    
    def _generate_signal(self,
                        spike: SpikeEvent,
                        current_price: float,
                        timestamp: datetime) -> Dict:
        """
        Generate trading signal to fade the spike
        """
        # Fade the spike (trade opposite direction)
        if spike.direction == 'up':
            # Spike up → SHORT (fade the rally)
            side = 'sell'
            entry_price = current_price * 0.9995  # Slight discount
            
            # Target: revert toward base price
            reversion_target = spike.base_price + (spike.peak_price - spike.base_price) * 0.3  # 30% retracement
            take_profit = max(entry_price * (1 - self.base_take_profit_pct), reversion_target)
            stop_loss = entry_price * (1 + self.base_stop_loss_pct)
            
        else:  # spike down
            # Spike down → LONG (fade the dump)
            side = 'buy'
            entry_price = current_price * 1.0005  # Slight premium
            
            # Target: revert toward base price
            reversion_target = spike.base_price - (spike.base_price - spike.peak_price) * 0.3  # 30% retracement
            take_profit = min(entry_price * (1 + self.base_take_profit_pct), reversion_target)
            stop_loss = entry_price * (1 - self.base_stop_loss_pct)
        
        # Calculate confidence
        confidence = self._calculate_confidence(spike)
        
        # Position sizing (adaptive)
        base_size = 0.01  # 0.01 BTC
        confidence_multiplier = 0.7 + (confidence * 0.3)  # 0.7x to 1.0x
        position_size = base_size * confidence_multiplier
        
        signal = {
            'strategy': 'volatility_spike_fader',
            'side': side,
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'size': position_size,
            'spike': spike,
            'confidence': confidence,
            'reason': self._build_reason(spike, confidence),
            'timestamp': timestamp
        }
        
        return signal
    
    def _calculate_confidence(self, spike: SpikeEvent) -> float:
        """
        Calculate signal confidence (0-1)
        
        Higher confidence for:
        - Larger spikes
        - High volume confirmation
        - Clean spike pattern
        """
        confidence = 0.5  # Base
        
        # Magnitude boost
        if spike.magnitude > 0.04:  # >4%
            confidence += 0.2
        elif spike.magnitude > 0.035:  # >3.5%
            confidence += 0.1
        
        # Volume confirmation boost
        if spike.volume_ratio > 2.5:
            confidence += 0.15
        elif spike.volume_ratio > 2.0:
            confidence += 0.10
        elif spike.volume_ratio > 1.5:
            confidence += 0.05
        
        # Cap at 1.0
        return min(confidence, 1.0)
    
    def _build_reason(self, spike: SpikeEvent, confidence: float) -> str:
        """Build human-readable reason"""
        return (f"Spike {spike.direction.upper()} {spike.magnitude*100:.1f}% | "
                f"Vol: {spike.volume_ratio:.1f}x | "
                f"Conf: {confidence:.0%}")
    
    def check_exit(self, current_price: float, position: Dict) -> Tuple[bool, str]:
        """Check if position should be exited"""
        entry_price = position['entry_price']
        entry_time = position['timestamp']
        side = position['side']
        
        # Check take profit
        if side == 'buy':
            if current_price >= position['take_profit']:
                return True, 'take_profit'
            if current_price <= position['stop_loss']:
                return True, 'stop_loss'
        else:  # sell
            if current_price <= position['take_profit']:
                return True, 'take_profit'
            if current_price >= position['stop_loss']:
                return True, 'stop_loss'
        
        # Check time stop
        time_held = (datetime.utcnow() - entry_time).total_seconds()
        if time_held >= self.max_hold_time:
            return True, 'time_stop'
        
        return False, ''
    
    def calculate_pnl(self, position: Dict, exit_price: float) -> float:
        """Calculate PnL for a position"""
        entry_price = position['entry_price']
        size = position['size']
        side = position['side']
        
        if side == 'buy':
            pnl_pct = (exit_price - entry_price) / entry_price
        else:  # sell
            pnl_pct = (entry_price - exit_price) / entry_price
        
        # Account for fees
        fees = 0.002
        pnl_pct -= fees
        
        position_value = entry_price * size
        pnl = position_value * pnl_pct
        
        return pnl
    
    def update_stats(self, pnl: float):
        """Update strategy statistics"""
        self.trades_executed += 1
        if pnl > 0:
            self.wins += 1
        else:
            self.losses += 1
    
    def get_stats(self) -> Dict:
        """Get strategy statistics"""
        win_rate = (self.wins / self.trades_executed * 100) if self.trades_executed > 0 else 0
        
        return {
            'strategy': 'volatility_spike_fader',
            'signals_generated': self.signals_generated,
            'trades_executed': self.trades_executed,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': win_rate
        }


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("⚡ VOLATILITY SPIKE FADER")
    print("="*80)
    print()
    print("Strategy: Fade extreme price movements for mean reversion")
    print("Target: 55-65% win rate, 1.0-2.0% profit per trade")
    print()
    print("Ready for backtesting!")
    print("="*80)
