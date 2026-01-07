"""
Simple Liquidation Hunter

Simplified version that works with integrated engine.
Focuses on core liquidation hunting logic without complex dependencies.

Strategy:
1. Detect large liquidation clusters
2. Wait for price to approach cluster
3. Trade in direction of liquidation cascade
4. Take profit: 0.8-1.2%
5. Stop loss: 1.0-1.5%
"""

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class LiquidationLevel:
    """Liquidation level"""
    price: float
    volume: float  # BTC
    side: str  # 'long' or 'short'
    leverage: int


class SimpleLiquidationHunter:
    """
    Simple Liquidation Hunter
    
    Detects liquidation clusters and trades liquidation cascades.
    
    Entry: Price within 1-2% of large liquidation cluster
    Exit: TP 0.8-1.2% or SL 1.0-1.5%
    """
    
    def __init__(self,
                 min_cluster_volume: float = 100.0,
                 entry_distance_pct: float = 0.015,
                 take_profit_pct: float = 0.010,
                 stop_loss_pct: float = 0.012):
        
        self.min_cluster_volume = min_cluster_volume
        self.entry_distance_pct = entry_distance_pct
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        
        # Statistics
        self.signals_generated = 0
        self.last_price = 0.0
    
    def analyze(self, market_data: Dict) -> Optional[Dict]:
        """
        Analyze market for liquidation opportunities
        
        Args:
            market_data: {
                'symbol': 'BTC/USDT',
                'price': 93500.0,
                'bid': 93498.0,
                'ask': 93502.0,
                'volume': 100.0
            }
        
        Returns:
            Signal dict or None
        """
        # Input validation
        if not market_data or not isinstance(market_data, dict):
            return None
        
        # Get price with validation
        bid = market_data.get('bid', 0)
        ask = market_data.get('ask', 0)
        
        # Validate bid/ask
        if bid <= 0 or ask <= 0 or not np.isfinite(bid) or not np.isfinite(ask):
            return None
        
        if ask < bid:  # Invalid spread
            return None
        
        price = market_data.get('price', (bid + ask) / 2)
        
        # Validate price
        if price <= 0 or price > 1_000_000 or not np.isfinite(price):
            return None
        
        # Update last price
        if self.last_price == 0:
            self.last_price = price
            return None
        
        # Get liquidation levels
        liq_levels = self._get_liquidation_levels(price)
        
        # Find significant clusters
        significant = [l for l in liq_levels if l.volume >= self.min_cluster_volume]
        
        if not significant:
            return None
        
        # Find closest cluster
        closest = min(significant, key=lambda l: abs(l.price - price))
        
        # Calculate distance (with zero check)
        if price == 0 or price < 0.01:
            return None
        distance_pct = abs(closest.price - price) / price
        
        # Check if close enough to enter
        if distance_pct <= self.entry_distance_pct:
            signal = self._generate_signal(closest, price, market_data)
            
            if signal:
                self.signals_generated += 1
            
            return signal
        
        # Update last price
        self.last_price = price
        
        return None
    
    def _get_liquidation_levels(self, current_price: float) -> List[LiquidationLevel]:
        """
        Get liquidation levels
        
        In production, this would query exchange API.
        For now, we simulate based on common leverage levels.
        """
        levels = []
        
        # Common leverage levels
        leverages = [10, 20, 50, 100]
        
        for lev in leverages:
            # Long liquidations (below current price)
            liq_price_long = current_price * (1 - 1/lev)
            volume_long = (lev / 10) * np.random.uniform(50, 200)
            
            levels.append(LiquidationLevel(
                price=liq_price_long,
                volume=volume_long,
                side='long',
                leverage=lev
            ))
            
            # Short liquidations (above current price)
            liq_price_short = current_price * (1 + 1/lev)
            volume_short = (lev / 10) * np.random.uniform(50, 200)
            
            levels.append(LiquidationLevel(
                price=liq_price_short,
                volume=volume_short,
                side='short',
                leverage=lev
            ))
        
        return levels
    
    def _generate_signal(self, 
                        cluster: LiquidationLevel,
                        current_price: float,
                        market_data: Dict) -> Optional[Dict]:
        """Generate trading signal"""
        
        # Determine trade direction
        if cluster.side == 'long':
            # Long liquidations = price drop = SHORT
            side = 'sell'
        else:
            # Short liquidations = price rise = LONG
            side = 'buy'
        
        # Calculate confidence based on cluster size
        confidence = min(0.5 + (cluster.volume / 500) * 0.3, 0.9)
        
        # Minimum confidence threshold
        if confidence < 0.5:
            return None
        
        # Calculate entry/exit prices
        if side == 'buy':
            entry_price = current_price * 1.0005
            take_profit = entry_price * (1 + self.take_profit_pct)
            stop_loss = entry_price * (1 - self.stop_loss_pct)
        else:  # sell
            entry_price = current_price * 0.9995
            take_profit = entry_price * (1 - self.take_profit_pct)
            stop_loss = entry_price * (1 + self.stop_loss_pct)
        
        return {
            'side': side,
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'confidence': confidence,
            'reason': f'Liquidation cluster at ${cluster.price:,.0f} ({cluster.volume:.0f} BTC, {cluster.leverage}x)',
            'metadata': {
                'cluster_price': cluster.price,
                'cluster_volume': cluster.volume,
                'cluster_side': cluster.side,
                'leverage': cluster.leverage,
                'distance_pct': abs(cluster.price - current_price) / current_price * 100
            }
        }
    
    def get_stats(self) -> Dict:
        """Get strategy statistics"""
        return {
            'strategy': 'simple_liquidation_hunter',
            'signals_generated': self.signals_generated
        }


if __name__ == "__main__":
    print("="*80)
    print("Simple Liquidation Hunter - Test")
    print("="*80)
    
    strategy = SimpleLiquidationHunter()
    
    # Test with sample data
    test_prices = [93000, 93100, 93200, 93300, 93400, 93500]
    
    for price in test_prices:
        market_data = {
            'symbol': 'BTC/USDT',
            'price': price,
            'bid': price - 2.5,
            'ask': price + 2.5,
            'volume': 100.0
        }
        
        signal = strategy.analyze(market_data)
        
        if signal:
            print(f"✅ Signal at ${price:,}: {signal['side'].upper()}")
            print(f"   Entry: ${signal['entry_price']:,.2f}")
            print(f"   TP: ${signal['take_profit']:,.2f} (+{strategy.take_profit_pct*100:.1f}%)")
            print(f"   SL: ${signal['stop_loss']:,.2f} (-{strategy.stop_loss_pct*100:.1f}%)")
            print(f"   Confidence: {signal['confidence']:.0%}")
            print(f"   Reason: {signal['reason']}")
            print()
    
    stats = strategy.get_stats()
    print(f"Signals generated: {stats['signals_generated']}")
    print("="*80)
