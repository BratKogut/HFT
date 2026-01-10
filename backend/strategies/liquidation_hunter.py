"""
Liquidation Hunter Strategy

Exploits liquidation cascades in crypto futures markets.

How it works:
1. Detect liquidation clusters (where many positions will be liquidated)
2. Wait for price to approach cluster
3. Enter position in direction of liquidation cascade
4. Take profit when cascade completes
5. Stop-loss if price reverses

Target: 0.8-1.5% profit per trade, 60-70% win rate
"""

import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from dataclasses import dataclass


@dataclass
class LiquidationCluster:
    """Represents a cluster of liquidations at a price level"""
    price: float
    volume: float  # Total BTC to be liquidated
    side: str  # 'long' or 'short'
    timestamp: datetime
    
    def __repr__(self):
        return f"Cluster({self.side.upper()} ${self.price:,.0f}, {self.volume:.2f} BTC)"


class LiquidationDataProvider:
    """
    Provides liquidation data from exchanges
    
    Note: In production, this would connect to real APIs
    For now, we'll estimate liquidations from order book and open interest
    """
    
    def __init__(self, exchange_name: str = 'binance'):
        self.exchange_name = exchange_name
        self.cache = {}
        
    async def get_liquidation_levels(self, symbol: str = 'BTC/USDT') -> List[LiquidationCluster]:
        """
        Get current liquidation levels
        
        In production, this would:
        1. Fetch open interest data
        2. Fetch funding rates
        3. Calculate liquidation prices for different leverage levels
        4. Aggregate into clusters
        
        For now, we'll estimate based on common leverage levels
        """
        # Get current price
        current_price = await self._get_current_price(symbol)
        
        if current_price == 0:
            return []
        
        # Estimate liquidation clusters at common leverage levels
        clusters = []
        
        # Long liquidations (below current price)
        # These trigger when price goes DOWN
        leverage_levels = [10, 20, 50, 100]
        for leverage in leverage_levels:
            # Liquidation price for long = entry * (1 - 1/leverage)
            # Assuming entries at current price
            liq_price = current_price * (1 - 1/leverage)
            
            # Estimate volume (higher leverage = more volume)
            volume = (leverage / 10) * np.random.uniform(50, 200)
            
            clusters.append(LiquidationCluster(
                price=liq_price,
                volume=volume,
                side='long',
                timestamp=datetime.utcnow()
            ))
        
        # Short liquidations (above current price)
        # These trigger when price goes UP
        for leverage in leverage_levels:
            # Liquidation price for short = entry * (1 + 1/leverage)
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
        """Get current market price"""
        # In production, fetch from exchange
        # For now, return cached or default
        return self.cache.get('price', 93000.0)
    
    def set_current_price(self, price: float):
        """Set current price (for testing)"""
        self.cache['price'] = price


class LiquidationHunter:
    """
    Liquidation hunting strategy
    
    Entry conditions:
    - Large liquidation cluster detected
    - Price within 1-2% of cluster
    - Momentum in direction of liquidations
    
    Exit conditions:
    - Take profit: 0.8-1.5% from entry
    - Stop loss: 1.2% against entry
    - Time stop: 30 minutes max hold
    """
    
    def __init__(self,
                 min_cluster_volume: float = 100.0,  # Min 100 BTC cluster
                 entry_distance_pct: float = 0.015,  # Enter when 1.5% from cluster
                 take_profit_pct: float = 0.012,     # Take profit at 1.2%
                 stop_loss_pct: float = 0.012,       # Stop loss at 1.2%
                 max_hold_time: int = 1800):         # Max 30 minutes
        
        self.min_cluster_volume = min_cluster_volume
        self.entry_distance_pct = entry_distance_pct
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_hold_time = max_hold_time
        
        # Data provider
        self.data_provider = LiquidationDataProvider()
        
        # State
        self.active_position: Optional[Dict] = None
        self.target_cluster: Optional[LiquidationCluster] = None
        
        # Statistics
        self.signals_generated = 0
        self.trades_executed = 0
        self.wins = 0
        self.losses = 0
        
    async def analyze_market(self, current_price: float, symbol: str = 'BTC/USDT') -> Optional[Dict]:
        """
        Analyze market for liquidation opportunities
        
        Returns signal dict or None
        """
        # Update current price
        self.data_provider.set_current_price(current_price)
        
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
        
        # Calculate distance to cluster
        distance = abs(closest_cluster.price - current_price) / current_price
        
        # Check if we're close enough to enter
        if distance <= self.entry_distance_pct:
            return self._generate_signal(closest_cluster, current_price)
        
        return None
    
    def _generate_signal(self, cluster: LiquidationCluster, current_price: float) -> Dict:
        """Generate trading signal based on cluster"""
        
        # Determine trade direction
        if cluster.side == 'long':
            # Long liquidations trigger on price drop
            # We SHORT to profit from the cascade
            side = 'sell'
            entry_price = current_price * 0.9995  # Slight discount
            take_profit = entry_price * (1 - self.take_profit_pct)
            stop_loss = entry_price * (1 + self.stop_loss_pct)
        else:
            # Short liquidations trigger on price rise
            # We LONG to profit from the cascade
            side = 'buy'
            entry_price = current_price * 1.0005  # Slight premium
            take_profit = entry_price * (1 + self.take_profit_pct)
            stop_loss = entry_price * (1 - self.stop_loss_pct)
        
        self.signals_generated += 1
        self.target_cluster = cluster
        
        signal = {
            'strategy': 'liquidation_hunter',
            'side': side,
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'size': 0.01,  # 0.01 BTC default
            'cluster': cluster,
            'reason': f'Liquidation cluster at ${cluster.price:,.0f} ({cluster.volume:.0f} BTC)',
            'timestamp': datetime.utcnow()
        }
        
        return signal
    
    def check_exit(self, current_price: float, position: Dict) -> Tuple[bool, str]:
        """
        Check if position should be exited
        
        Returns: (should_exit, reason)
        """
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
        
        # Account for fees (0.1% maker + 0.1% taker)
        fees = 0.002
        pnl_pct -= fees
        
        # Calculate dollar PnL
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
            'strategy': 'liquidation_hunter',
            'signals_generated': self.signals_generated,
            'trades_executed': self.trades_executed,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': win_rate
        }


async def backtest_liquidation_hunter(historical_data: pd.DataFrame, 
                                      initial_capital: float = 10000.0) -> Dict:
    """
    Backtest liquidation hunter on historical data
    
    Note: This is simplified - real liquidation data would be needed for accurate backtest
    """
    print("="*80)
    print("🎯 LIQUIDATION HUNTER BACKTEST")
    print("="*80)
    print()
    
    strategy = LiquidationHunter(
        min_cluster_volume=100.0,
        entry_distance_pct=0.015,
        take_profit_pct=0.012,
        stop_loss_pct=0.012
    )
    
    capital = initial_capital
    position = None
    trades = []
    
    print(f"💰 Initial capital: ${capital:,.2f}")
    print(f"📊 Data points: {len(historical_data)}")
    print(f"📅 Period: {historical_data['timestamp'].iloc[0]} to {historical_data['timestamp'].iloc[-1]}")
    print()
    print("🔄 Running backtest...")
    print()
    
    for idx, row in historical_data.iterrows():
        current_price = row['close']
        
        # If we have a position, check exit
        if position:
            should_exit, reason = strategy.check_exit(current_price, position)
            
            if should_exit:
                # Exit position
                pnl = strategy.calculate_pnl(position, current_price)
                capital += pnl
                
                strategy.update_stats(pnl)
                
                trades.append({
                    'entry_time': position['timestamp'],
                    'exit_time': row['timestamp'],
                    'side': position['side'],
                    'entry_price': position['entry_price'],
                    'exit_price': current_price,
                    'pnl': pnl,
                    'reason': reason,
                    'capital': capital
                })
                
                pnl_pct = (pnl / (position['entry_price'] * position['size'])) * 100
                print(f"{'✅' if pnl > 0 else '❌'} {position['side'].upper():4s} | "
                      f"Entry: ${position['entry_price']:,.2f} | "
                      f"Exit: ${current_price:,.2f} | "
                      f"PnL: ${pnl:+.2f} ({pnl_pct:+.2f}%) | "
                      f"Reason: {reason} | "
                      f"Capital: ${capital:,.2f}")
                
                position = None
        
        # If no position, look for entry
        else:
            signal = await strategy.analyze_market(current_price)
            
            if signal:
                # Enter position
                position = signal
                print(f"\n🎯 SIGNAL: {signal['reason']}")
                print(f"   Entry: ${signal['entry_price']:,.2f} | "
                      f"TP: ${signal['take_profit']:,.2f} | "
                      f"SL: ${signal['stop_loss']:,.2f}\n")
    
    # Calculate metrics
    if trades:
        trades_df = pd.DataFrame(trades)
        total_pnl = trades_df['pnl'].sum()
        win_rate = (trades_df['pnl'] > 0).sum() / len(trades_df) * 100
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if (trades_df['pnl'] > 0).any() else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if (trades_df['pnl'] < 0).any() else 0
        
        print()
        print("="*80)
        print("📊 RESULTS")
        print("="*80)
        print()
        print(f"💰 Initial Capital:     ${initial_capital:>12,.2f}")
        print(f"💰 Final Capital:       ${capital:>12,.2f}")
        print(f"💰 Total PnL:           ${total_pnl:>12,.2f}")
        print(f"📈 Return:              {(capital/initial_capital-1)*100:>12.2f}%")
        print()
        print(f"📊 Total Trades:        {len(trades_df):>12}")
        print(f"✅ Winning Trades:      {(trades_df['pnl'] > 0).sum():>12}")
        print(f"❌ Losing Trades:       {(trades_df['pnl'] < 0).sum():>12}")
        print(f"📈 Win Rate:            {win_rate:>12.2f}%")
        print()
        print(f"💚 Avg Win:             ${avg_win:>12.2f}")
        print(f"💔 Avg Loss:            ${avg_loss:>12.2f}")
        print(f"📊 Profit Factor:       {abs(avg_win/avg_loss) if avg_loss != 0 else 0:>12.2f}")
        print()
        print("="*80)
        
        return {
            'trades': trades_df,
            'final_capital': capital,
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'stats': strategy.get_stats()
        }
    else:
        print("\n❌ No trades executed")
        return {'trades': pd.DataFrame(), 'final_capital': capital, 'total_pnl': 0}


if __name__ == "__main__":
    # Test with sample data
    import os
    
    data_file = "data/historical/BTC_USDT_1m_20251230_20260106.csv"
    
    if os.path.exists(data_file):
        df = pd.read_csv(data_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Run backtest
        results = asyncio.run(backtest_liquidation_hunter(df, initial_capital=10000.0))
    else:
        print(f"❌ Data file not found: {data_file}")
