"""
Liquidation Hunter V2 - Enhanced with CVD and Trend Filter

Improvements over V1:
1. CVD confirmation (order flow analysis)
2. Trend filter (don't fight the trend)
3. Better entry timing
4. Dynamic position sizing
5. Adaptive take-profit/stop-loss

Target: 60-70% win rate, 1.0-1.5% avg profit
"""

import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from trend_filter import TrendFilter, TrendState, TrendDirection
from cvd_detector import CVDDetector, CVDSignals


@dataclass
class LiquidationCluster:
    """Represents a cluster of liquidations at a price level"""
    price: float
    volume: float
    side: str  # 'long' or 'short'
    timestamp: datetime
    
    def __repr__(self):
        return f"Cluster({self.side.upper()} ${self.price:,.0f}, {self.volume:.2f} BTC)"


class LiquidationDataProvider:
    """Provides liquidation data (same as V1 but enhanced)"""
    
    def __init__(self, exchange_name: str = 'binance'):
        self.exchange_name = exchange_name
        self.cache = {}
        
    async def get_liquidation_levels(self, symbol: str = 'BTC/USDT') -> List[LiquidationCluster]:
        """Get current liquidation levels"""
        current_price = await self._get_current_price(symbol)
        
        if current_price == 0:
            return []
        
        clusters = []
        
        # Long liquidations (below current price)
        leverage_levels = [10, 20, 50, 100]
        for leverage in leverage_levels:
            liq_price = current_price * (1 - 1/leverage)
            volume = (leverage / 10) * np.random.uniform(50, 200)
            
            clusters.append(LiquidationCluster(
                price=liq_price,
                volume=volume,
                side='long',
                timestamp=datetime.utcnow()
            ))
        
        # Short liquidations (above current price)
        for leverage in leverage_levels:
            liq_price = current_price * (1 + 1/leverage)
            volume = (leverage / 10) * np.random.uniform(50, 200)
            
            clusters.append(LiquidationCluster(
                price=liq_price,
                volume=volume,
                side='short',
                timestamp=datetime.utcnow()
            ))
        
        return clusters
    
    async def _get_current_price(self, symbol: str) -> float:
        return self.cache.get('price', 93000.0)
    
    def set_current_price(self, price: float):
        self.cache['price'] = price


class LiquidationHunterV2:
    """
    Enhanced liquidation hunting strategy with CVD and trend filter
    
    Entry conditions:
    - Large liquidation cluster detected
    - Price within 1-2% of cluster
    - CVD confirmation (optional but boosts confidence)
    - Trend filter allows the trade
    
    Exit conditions:
    - Take profit: 0.8-1.5% (adaptive based on volatility)
    - Stop loss: 1.0-1.5% (adaptive)
    - Time stop: 30 minutes max
    """
    
    def __init__(self,
                 min_cluster_volume: float = 100.0,
                 entry_distance_pct: float = 0.015,
                 base_take_profit_pct: float = 0.012,
                 base_stop_loss_pct: float = 0.012,
                 max_hold_time: int = 1800):
        
        self.min_cluster_volume = min_cluster_volume
        self.entry_distance_pct = entry_distance_pct
        self.base_take_profit_pct = base_take_profit_pct
        self.base_stop_loss_pct = base_stop_loss_pct
        self.max_hold_time = max_hold_time
        
        # Components
        self.data_provider = LiquidationDataProvider()
        self.trend_filter = TrendFilter()
        self.cvd_detector = CVDDetector(symbol='BTCUSDT')
        
        # State
        self.active_position: Optional[Dict] = None
        self.target_cluster: Optional[LiquidationCluster] = None
        
        # Statistics
        self.signals_generated = 0
        self.signals_filtered = 0  # Blocked by trend filter
        self.trades_executed = 0
        self.wins = 0
        self.losses = 0
        
    async def analyze_market(self,
                            current_price: float,
                            high: float,
                            low: float,
                            volume: float,
                            is_buyer_maker: bool,
                            symbol: str = 'BTC/USDT') -> Optional[Dict]:
        """
        Analyze market for liquidation opportunities
        
        Args:
            current_price: Current close price
            high: High price
            low: Low price
            volume: Trade volume
            is_buyer_maker: CVD data
            symbol: Trading pair
        
        Returns:
            Signal dict or None
        """
        # Update components
        self.data_provider.set_current_price(current_price)
        trend_state = self.trend_filter.update(current_price, high, low)
        cvd_signals = await self.cvd_detector.update(current_price, volume, is_buyer_maker)
        
        # Get liquidation levels
        clusters = await self.data_provider.get_liquidation_levels(symbol)
        
        # Filter significant clusters
        significant_clusters = [
            c for c in clusters 
            if c.volume >= self.min_cluster_volume
        ]
        
        if not significant_clusters:
            return None
        
        # Find closest cluster
        closest_cluster = min(
            significant_clusters,
            key=lambda c: abs(c.price - current_price)
        )
        
        # Calculate distance to cluster (protect against division by zero)
        if current_price <= 0:
            return None
        distance = abs(closest_cluster.price - current_price) / current_price
        
        # Check if we're close enough to enter
        if distance <= self.entry_distance_pct:
            signal = self._generate_signal(
                closest_cluster,
                current_price,
                trend_state,
                cvd_signals
            )
            
            if signal:
                self.signals_generated += 1
            
            return signal
        
        return None
    
    def _generate_signal(self,
                        cluster: LiquidationCluster,
                        current_price: float,
                        trend_state: TrendState,
                        cvd_signals: CVDSignals) -> Optional[Dict]:
        """Generate trading signal with all confirmations"""
        
        # Determine trade direction
        if cluster.side == 'long':
            # Long liquidations = price drop = SHORT
            side = 'sell'
            trade_direction = 'short'
        else:
            # Short liquidations = price rise = LONG
            side = 'buy'
            trade_direction = 'long'
        
        # CHECK TREND FILTER
        if trade_direction == 'long':
            can_trade, reason = self.trend_filter.should_trade_long(trend_state)
        else:
            can_trade, reason = self.trend_filter.should_trade_short(trend_state)
        
        if not can_trade:
            self.signals_filtered += 1
            print(f"⚠️  Signal FILTERED: {trade_direction.upper()} blocked by trend ({reason})")
            return None
        
        # Calculate confidence
        confidence = self._calculate_confidence(cluster, trend_state, cvd_signals, trade_direction)
        
        # Minimum confidence threshold
        if confidence < 0.4:
            self.signals_filtered += 1
            print(f"⚠️  Signal FILTERED: Low confidence ({confidence:.2f})")
            return None
        
        # Calculate position size (adaptive based on trend and confidence)
        base_size = 0.01  # 0.01 BTC
        trend_multiplier = self.trend_filter.get_position_size_multiplier(trend_state, trade_direction)
        confidence_multiplier = 0.5 + (confidence * 0.5)  # 0.5x to 1.0x
        position_size = base_size * trend_multiplier * confidence_multiplier
        
        # Calculate entry/exit prices (adaptive)
        entry_price, take_profit, stop_loss = self._calculate_prices(
            current_price,
            side,
            trend_state,
            confidence
        )
        
        self.target_cluster = cluster
        
        signal = {
            'strategy': 'liquidation_hunter_v2',
            'side': side,
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'size': position_size,
            'cluster': cluster,
            'trend_state': trend_state,
            'cvd_signals': cvd_signals,
            'confidence': confidence,
            'reason': self._build_reason(cluster, trend_state, cvd_signals, confidence),
            'timestamp': datetime.utcnow()
        }
        
        return signal
    
    def _calculate_confidence(self,
                             cluster: LiquidationCluster,
                             trend_state: TrendState,
                             cvd_signals: CVDSignals,
                             trade_direction: str) -> float:
        """
        Calculate signal confidence (0-1)
        
        Based on:
        - Cluster size
        - Trend alignment
        - CVD confirmation
        - Market regime
        """
        confidence = 0.5  # Base
        
        # Cluster size boost
        if cluster.volume > 200:
            confidence += 0.1
        if cluster.volume > 500:
            confidence += 0.1
        
        # Trend alignment boost
        if trade_direction == 'short':
            if trend_state.direction in [TrendDirection.WEAK_DOWN, TrendDirection.STRONG_DOWN]:
                confidence += 0.2 * trend_state.confidence
        else:  # long
            if trend_state.direction in [TrendDirection.WEAK_UP, TrendDirection.STRONG_UP]:
                confidence += 0.2 * trend_state.confidence
        
        # CVD confirmation boost
        if trade_direction == 'short':
            if cvd_signals.has_bearish_divergence:
                confidence += cvd_signals.divergence_confidence * 0.15
            if cvd_signals.has_buying_exhaustion:
                confidence += 0.15
        
        # Market regime adjustment
        if trend_state.regime == 'range_bound':
            confidence += 0.1  # Liquidation hunting works best in range
        elif trend_state.regime == 'volatile':
            confidence -= 0.1  # Reduce confidence in volatile markets
        
        return min(confidence, 1.0)
    
    def _calculate_prices(self,
                         current_price: float,
                         side: str,
                         trend_state: TrendState,
                         confidence: float) -> Tuple[float, float, float]:
        """
        Calculate entry, take-profit, and stop-loss prices
        
        Adaptive based on:
        - Volatility (wider stops in volatile markets)
        - Confidence (tighter stops with high confidence)
        - Trend strength
        """
        # Adjust TP/SL based on volatility
        volatility_multiplier = 1.0 + (trend_state.volatility / 0.02)  # Scale by 2% ATR
        
        # Adjust based on confidence (higher confidence = tighter stops)
        confidence_multiplier = 1.5 - (confidence * 0.5)  # 1.5x to 1.0x
        
        # Calculate final TP/SL percentages
        tp_pct = self.base_take_profit_pct * volatility_multiplier
        sl_pct = self.base_stop_loss_pct * volatility_multiplier * confidence_multiplier
        
        # Calculate prices
        if side == 'buy':
            entry_price = current_price * 1.0005
            take_profit = entry_price * (1 + tp_pct)
            stop_loss = entry_price * (1 - sl_pct)
        else:  # sell
            entry_price = current_price * 0.9995
            take_profit = entry_price * (1 - tp_pct)
            stop_loss = entry_price * (1 + sl_pct)
        
        return entry_price, take_profit, stop_loss
    
    def _build_reason(self,
                     cluster: LiquidationCluster,
                     trend_state: TrendState,
                     cvd_signals: CVDSignals,
                     confidence: float) -> str:
        """Build human-readable reason for signal"""
        reasons = []
        
        reasons.append(f"Liq cluster ${cluster.price:,.0f} ({cluster.volume:.0f} BTC)")
        reasons.append(f"Trend: {trend_state.direction.value}")
        reasons.append(f"Confidence: {confidence:.0%}")
        
        if cvd_signals.has_bearish_divergence:
            reasons.append(f"CVD divergence")
        if cvd_signals.has_buying_exhaustion:
            reasons.append(f"Buying exhaustion")
        
        return " | ".join(reasons)
    
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

        # Protect against division by zero
        if entry_price <= 0:
            return 0.0

        if side == 'buy':
            pnl_pct = (exit_price - entry_price) / entry_price
        else:  # sell
            pnl_pct = (entry_price - exit_price) / entry_price

        # Account for fees (0.1% maker + 0.1% taker)
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
        filter_rate = (self.signals_filtered / (self.signals_generated + self.signals_filtered) * 100) if (self.signals_generated + self.signals_filtered) > 0 else 0
        
        return {
            'strategy': 'liquidation_hunter_v2',
            'signals_generated': self.signals_generated,
            'signals_filtered': self.signals_filtered,
            'filter_rate': filter_rate,
            'trades_executed': self.trades_executed,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': win_rate
        }


if __name__ == "__main__":
    print("Liquidation Hunter V2 - Enhanced with CVD and Trend Filter")
    print("Ready for backtesting!")
