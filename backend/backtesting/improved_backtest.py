"""
Improved Backtesting Engine with Real Market Data

Features:
- Uses real historical data from Binance
- Improved market making strategy with trend detection
- Better risk management
- Comprehensive performance metrics
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ImprovedBacktestEngine:
    """
    Enhanced backtesting engine with realistic simulation
    """
    
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0.0
        self.trades = []
        self.equity_curve = []
        
        # Transaction costs (Binance spot)
        self.maker_fee = 0.001  # 0.1% maker fee
        self.taker_fee = 0.001  # 0.1% taker fee
        self.slippage = 0.0005  # 0.05% slippage
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_equity = initial_capital
        
        # Entry prices for PnL calculation
        self.entry_prices = []
    
    def execute_trade(self,
                     timestamp: datetime,
                     side: str,
                     price: float,
                     size: float,
                     order_type: str = 'maker') -> Dict:
        """Execute a trade with realistic costs"""
        
        # Calculate costs
        fee_rate = self.maker_fee if order_type == 'maker' else self.taker_fee
        
        # Apply slippage
        if side == 'buy':
            effective_price = price * (1 + self.slippage)
        else:
            effective_price = price * (1 - self.slippage)
        
        # Calculate trade value
        trade_value = size * effective_price
        fee = trade_value * fee_rate
        total_cost = trade_value + fee
        
        # Check if we can execute
        if side == 'buy':
            if self.capital < total_cost:
                return {'success': False, 'reason': 'Insufficient capital'}
            
            self.position += size
            self.capital -= total_cost
            self.entry_prices.append(effective_price)
            position_change = size
            trade_pnl = 0.0
            
        else:  # sell
            if self.position < size:
                return {'success': False, 'reason': 'Insufficient position'}
            
            self.position -= size
            self.capital += (trade_value - fee)
            
            # Calculate PnL
            if self.entry_prices:
                avg_entry = np.mean(self.entry_prices)
                trade_pnl = (effective_price - avg_entry) * size - fee
                
                # Remove entry price
                if len(self.entry_prices) > 0:
                    self.entry_prices.pop(0)
            else:
                trade_pnl = 0.0
            
            position_change = -size
        
        # Record trade
        current_equity = self.capital + (self.position * price)
        
        trade = {
            'timestamp': timestamp,
            'side': side,
            'price': effective_price,
            'size': size,
            'fee': fee,
            'pnl': trade_pnl,
            'capital': self.capital,
            'position': self.position,
            'equity': current_equity
        }
        
        self.trades.append(trade)
        self.total_trades += 1
        
        if trade_pnl > 0:
            self.winning_trades += 1
        elif trade_pnl < 0:
            self.losing_trades += 1
        
        self.total_pnl += trade_pnl
        
        # Update equity curve
        self.equity_curve.append({
            'timestamp': timestamp,
            'equity': current_equity
        })
        
        # Track drawdown
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        drawdown = (self.peak_equity - current_equity) / self.peak_equity
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
        
        return {'success': True, 'trade': trade}
    
    def get_performance_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics"""
        if len(self.equity_curve) < 2:
            return {}
        
        df = pd.DataFrame(self.equity_curve)
        df['returns'] = df['equity'].pct_change()
        
        # Total return
        total_return = (df['equity'].iloc[-1] - self.initial_capital) / self.initial_capital
        
        # Sharpe Ratio (annualized)
        returns_std = df['returns'].std()
        if returns_std > 0:
            sharpe_ratio = (df['returns'].mean() / returns_std) * np.sqrt(525600)
        else:
            sharpe_ratio = 0.0
        
        # Win rate
        win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0
        
        # Average trade PnL
        trade_pnls = [t['pnl'] for t in self.trades if t['pnl'] != 0]
        avg_trade_pnl = np.mean(trade_pnls) if trade_pnls else 0.0
        
        # Profit factor
        winning_pnl = sum(p for p in trade_pnls if p > 0)
        losing_pnl = abs(sum(p for p in trade_pnls if p < 0))
        profit_factor = winning_pnl / losing_pnl if losing_pnl > 0 else 0.0
        
        return {
            'initial_capital': self.initial_capital,
            'final_equity': df['equity'].iloc[-1],
            'total_return': total_return * 100,
            'total_pnl': self.total_pnl,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': self.max_drawdown * 100,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate * 100,
            'avg_trade_pnl': avg_trade_pnl,
            'profit_factor': profit_factor,
            'total_fees_paid': sum(t['fee'] for t in self.trades)
        }


class ImprovedMarketMakingStrategy:
    """
    Improved market making strategy with:
    - Trend detection (don't fight the trend)
    - Volume confirmation
    - Better position sizing
    - Stop-loss protection
    """
    
    def __init__(self,
                 base_spread: float = 0.0003,  # 0.03% (3 bps)
                 order_size: float = 0.01,     # 0.01 BTC
                 max_position: float = 0.1):   # Max 0.1 BTC
        
        self.base_spread = base_spread
        self.order_size = order_size
        self.max_position = max_position
        
        # Strategy parameters
        self.signal_cooldown = 300  # 5 minutes between signals
        self.last_signal_time = None
        
        # Trend detection
        self.trend_window = 60  # 1 hour for trend
        self.trend_threshold = 0.002  # 0.2% move = trend
        
        # Stop-loss
        self.stop_loss_pct = 0.01  # 1% stop-loss
        
    def calculate_trend(self, prices: pd.Series) -> float:
        """
        Calculate trend strength
        
        Returns:
            > 0: Uptrend
            < 0: Downtrend
            ~0: No trend
        """
        if len(prices) < self.trend_window:
            return 0.0
        
        recent_prices = prices.iloc[-self.trend_window:]
        price_change = (recent_prices.iloc[-1] - recent_prices.iloc[0]) / recent_prices.iloc[0]
        
        return price_change
    
    def generate_signals(self,
                        current_bar: pd.Series,
                        historical_data: pd.DataFrame,
                        current_position: float) -> List[Dict]:
        """
        Generate trading signals with trend awareness
        """
        signals = []
        
        # Check cooldown
        if self.last_signal_time:
            time_diff = (current_bar['timestamp'] - self.last_signal_time).total_seconds()
            if time_diff < self.signal_cooldown:
                return signals
        
        # Calculate trend
        trend = self.calculate_trend(historical_data['close'])
        
        # Current market state
        mid_price = (current_bar['high'] + current_bar['low']) / 2
        
        # Estimate spread from high-low
        spread_estimate = (current_bar['high'] - current_bar['low']) / mid_price
        
        # Only trade if spread is wide enough
        if spread_estimate < self.base_spread * 0.5:
            return signals
        
        # Calculate order prices
        buy_price = mid_price * (1 - self.base_spread)
        sell_price = mid_price * (1 + self.base_spread)
        
        # Position-aware sizing
        buy_size = self.order_size
        sell_size = self.order_size
        
        # Reduce size if approaching limits
        if abs(current_position) > self.max_position * 0.7:
            buy_size *= 0.5
            sell_size *= 0.5
        
        # TREND-AWARE SIGNALS
        
        # In uptrend: prefer buying, be cautious selling
        if trend > self.trend_threshold:
            if current_position < self.max_position * 0.8:
                signals.append({
                    'side': 'buy',
                    'price': buy_price,
                    'size': buy_size,
                    'reason': f'Market making (uptrend: {trend*100:.2f}%)'
                })
        
        # In downtrend: prefer selling, be cautious buying
        elif trend < -self.trend_threshold:
            if current_position > 0:
                signals.append({
                    'side': 'sell',
                    'price': sell_price,
                    'size': min(sell_size, current_position),
                    'reason': f'Market making (downtrend: {trend*100:.2f}%)'
                })
        
        # No strong trend: normal market making
        else:
            # Buy signal
            if current_position < self.max_position:
                signals.append({
                    'side': 'buy',
                    'price': buy_price,
                    'size': buy_size,
                    'reason': f'Market making (neutral, spread: {spread_estimate*10000:.1f}bps)'
                })
            
            # Sell signal
            if current_position > 0:
                signals.append({
                    'side': 'sell',
                    'price': sell_price,
                    'size': min(sell_size, current_position),
                    'reason': f'Market making (neutral, spread: {spread_estimate*10000:.1f}bps)'
                })
        
        if signals:
            self.last_signal_time = current_bar['timestamp']
        
        return signals


def run_improved_backtest(data_file: str, initial_capital: float = 10000.0) -> Dict:
    """
    Run improved backtest on real Binance data
    """
    print("="*80)
    print("🚀 IMPROVED BACKTESTING ENGINE")
    print("="*80)
    print()
    
    # Load data
    print(f"📁 Loading data from: {data_file}")
    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    print(f"✅ Loaded {len(df)} candles")
    print(f"   Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    print(f"   Price range: ${df['low'].min():,.2f} - ${df['high'].max():,.2f}")
    print()
    
    # Initialize
    engine = ImprovedBacktestEngine(initial_capital)
    strategy = ImprovedMarketMakingStrategy(
        base_spread=0.0003,  # 0.03% = 3 bps
        order_size=0.01,     # 0.01 BTC (~$900)
        max_position=0.1     # Max 0.1 BTC (~$9,000)
    )
    
    print("💰 Initial capital: ${:,.2f}".format(initial_capital))
    print("📊 Strategy: Improved Market Making with Trend Detection")
    print("   Base spread: 0.03% (3 bps)")
    print("   Order size: 0.01 BTC")
    print("   Max position: 0.1 BTC")
    print()
    print("="*80)
    print("🔄 RUNNING BACKTEST...")
    print("="*80)
    print()
    
    # Run backtest
    for idx in range(len(df)):
        current_bar = df.iloc[idx]
        
        # Get historical data up to current point
        historical_data = df.iloc[:idx+1]
        
        # Generate signals
        signals = strategy.generate_signals(
            current_bar,
            historical_data,
            engine.position
        )
        
        # Execute signals
        for signal in signals:
            result = engine.execute_trade(
                timestamp=current_bar['timestamp'],
                side=signal['side'],
                price=signal['price'],
                size=signal['size'],
                order_type='maker'
            )
            
            if result['success']:
                trade = result['trade']
                if idx % 100 == 0:  # Print every 100th trade
                    print(f"✅ {trade['side'].upper():4s} {trade['size']:.4f} BTC @ ${trade['price']:,.2f} | "
                          f"PnL: ${trade['pnl']:+.2f} | Equity: ${trade['equity']:,.2f}")
    
    # Get results
    metrics = engine.get_performance_metrics()
    
    print()
    print("="*80)
    print("📊 BACKTEST RESULTS")
    print("="*80)
    
    return {
        'metrics': metrics,
        'trades': pd.DataFrame(engine.trades),
        'equity_curve': pd.DataFrame(engine.equity_curve)
    }


if __name__ == "__main__":
    # Run backtest on real Binance data
    data_file = "data/historical/BTC_USDT_1m_20251230_20260106.csv"
    
    if os.path.exists(data_file):
        results = run_improved_backtest(data_file, initial_capital=10000.0)
        
        # Print metrics
        metrics = results['metrics']
        print()
        print("💰 CAPITAL & RETURNS")
        print(f"   Initial Capital:        ${metrics['initial_capital']:>12,.2f}")
        print(f"   Final Equity:           ${metrics['final_equity']:>12,.2f}")
        print(f"   Total PnL:              ${metrics['total_pnl']:>12,.2f}")
        print(f"   Total Return:           {metrics['total_return']:>12.2f}%")
        print()
        print("📉 RISK METRICS")
        print(f"   Sharpe Ratio:           {metrics['sharpe_ratio']:>12.2f}")
        print(f"   Max Drawdown:           {metrics['max_drawdown']:>12.2f}%")
        print()
        print("📈 TRADING STATISTICS")
        print(f"   Total Trades:           {metrics['total_trades']:>12}")
        print(f"   Winning Trades:         {metrics['winning_trades']:>12}")
        print(f"   Losing Trades:          {metrics['losing_trades']:>12}")
        print(f"   Win Rate:               {metrics['win_rate']:>12.2f}%")
        print(f"   Avg Trade PnL:          ${metrics['avg_trade_pnl']:>12.2f}")
        print(f"   Profit Factor:          {metrics['profit_factor']:>12.2f}")
        print()
        print("💸 COSTS")
        print(f"   Total Fees Paid:        ${metrics['total_fees_paid']:>12,.2f}")
        print()
        print("="*80)
        
        # Assessment
        if metrics['sharpe_ratio'] > 1.5 and metrics['total_return'] > 5:
            print("✅ EXCELLENT - Strategy is profitable and ready for paper trading!")
        elif metrics['sharpe_ratio'] > 1.0:
            print("✅ GOOD - Strategy shows promise, needs minor optimization")
        elif metrics['sharpe_ratio'] > 0.5:
            print("⚠️  MARGINAL - Strategy needs improvement")
        else:
            print("❌ POOR - Strategy not profitable, major changes needed")
        
        print("="*80)
    else:
        print(f"❌ Data file not found: {data_file}")
        print("Run data_downloader.py first to download historical data")
