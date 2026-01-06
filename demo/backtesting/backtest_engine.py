"""
Backtesting Engine - Demo Version
Shows how backtesting will work with real historical data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json


class BacktestEngine:
    """
    Backtesting engine for HFT strategies
    
    Features:
    - Historical data replay
    - Transaction cost modeling
    - Slippage simulation
    - Performance metrics (Sharpe, drawdown, win rate)
    - Trade-by-trade analysis
    """
    
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0.0
        self.trades = []
        self.equity_curve = []
        
        # Transaction costs
        self.maker_fee = 0.0002  # 0.02% (Binance maker)
        self.taker_fee = 0.0004  # 0.04% (Binance taker)
        self.slippage = 0.0001   # 0.01% average slippage
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_equity = initial_capital
        
    def execute_trade(self, 
                     timestamp: datetime,
                     side: str,  # 'buy' or 'sell'
                     price: float,
                     size: float,
                     order_type: str = 'maker') -> Dict:
        """
        Execute a trade with realistic costs
        
        Returns trade result with PnL calculation
        """
        # Calculate costs
        fee_rate = self.maker_fee if order_type == 'maker' else self.taker_fee
        effective_price = price * (1 + self.slippage) if side == 'buy' else price * (1 - self.slippage)
        
        # Calculate trade value
        trade_value = size * effective_price
        fee = trade_value * fee_rate
        total_cost = trade_value + fee
        
        # Update position
        if side == 'buy':
            if self.capital < total_cost:
                return {'success': False, 'reason': 'Insufficient capital'}
            
            self.position += size
            self.capital -= total_cost
            position_change = size
            
        else:  # sell
            if self.position < size:
                return {'success': False, 'reason': 'Insufficient position'}
            
            self.position -= size
            self.capital += (trade_value - fee)
            position_change = -size
        
        # Calculate PnL for this trade
        trade_pnl = 0.0
        if len(self.trades) > 0 and side == 'sell':
            # Find matching buy trades
            avg_buy_price = self._get_average_entry_price()
            if avg_buy_price > 0:
                trade_pnl = (effective_price - avg_buy_price) * size - fee
        
        # Record trade
        trade = {
            'timestamp': timestamp,
            'side': side,
            'price': effective_price,
            'size': size,
            'fee': fee,
            'pnl': trade_pnl,
            'capital': self.capital,
            'position': self.position,
            'equity': self.capital + (self.position * price)
        }
        
        self.trades.append(trade)
        self.total_trades += 1
        
        if trade_pnl > 0:
            self.winning_trades += 1
        elif trade_pnl < 0:
            self.losing_trades += 1
        
        self.total_pnl += trade_pnl
        
        # Update equity curve
        current_equity = self.capital + (self.position * price)
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
    
    def _get_average_entry_price(self) -> float:
        """Calculate average entry price from buy trades"""
        buy_trades = [t for t in self.trades if t['side'] == 'buy']
        if not buy_trades:
            return 0.0
        
        total_value = sum(t['price'] * t['size'] for t in buy_trades)
        total_size = sum(t['size'] for t in buy_trades)
        
        return total_value / total_size if total_size > 0 else 0.0
    
    def get_performance_metrics(self) -> Dict:
        """
        Calculate comprehensive performance metrics
        """
        if len(self.equity_curve) < 2:
            return {}
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(self.equity_curve)
        df['returns'] = df['equity'].pct_change()
        
        # Calculate metrics
        total_return = (df['equity'].iloc[-1] - self.initial_capital) / self.initial_capital
        
        # Sharpe Ratio (annualized, assuming 1-minute bars)
        returns_std = df['returns'].std()
        if returns_std > 0:
            sharpe_ratio = (df['returns'].mean() / returns_std) * np.sqrt(525600)  # 525600 minutes/year
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
            'total_return': total_return * 100,  # percentage
            'total_pnl': self.total_pnl,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': self.max_drawdown * 100,  # percentage
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate * 100,  # percentage
            'avg_trade_pnl': avg_trade_pnl,
            'profit_factor': profit_factor,
            'total_fees_paid': sum(t['fee'] for t in self.trades)
        }
    
    def get_trades_df(self) -> pd.DataFrame:
        """Return trades as DataFrame for analysis"""
        return pd.DataFrame(self.trades)
    
    def get_equity_curve_df(self) -> pd.DataFrame:
        """Return equity curve as DataFrame"""
        return pd.DataFrame(self.equity_curve)


class MarketMakingStrategy:
    """
    Demo Market Making Strategy
    
    Improved version with:
    - Dynamic spread adjustment
    - Order book imbalance
    - Volume profile
    - Adaptive position sizing
    """
    
    def __init__(self, 
                 base_spread: float = 0.0005,  # 0.05% (5 bps)
                 order_size: float = 0.1,
                 max_position: float = 1.0):
        
        self.base_spread = base_spread
        self.order_size = order_size
        self.max_position = max_position
        
        # Strategy state
        self.last_signal_time = None
        self.signal_cooldown = 60  # seconds
        
    def generate_signals(self, 
                        market_data: Dict,
                        current_position: float,
                        timestamp: datetime) -> List[Dict]:
        """
        Generate trading signals based on market conditions
        
        Returns list of orders to place
        """
        signals = []
        
        # Check cooldown
        if self.last_signal_time:
            time_diff = (timestamp - self.last_signal_time).total_seconds()
            if time_diff < self.signal_cooldown:
                return signals
        
        # Extract market data
        bid = market_data.get('bid', 0)
        ask = market_data.get('ask', 0)
        mid_price = (bid + ask) / 2
        
        if mid_price == 0:
            return signals
        
        # Calculate current spread
        current_spread = (ask - bid) / mid_price
        
        # Order book imbalance (if available)
        bid_volume = market_data.get('bid_volume', 1.0)
        ask_volume = market_data.get('ask_volume', 1.0)
        imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
        
        # Only trade if spread is wide enough
        if current_spread < self.base_spread * 0.5:
            return signals  # Spread too tight
        
        # Adjust spread based on imbalance
        spread_adjustment = 1.0 + (abs(imbalance) * 0.5)
        effective_spread = self.base_spread * spread_adjustment
        
        # Calculate order prices
        buy_price = mid_price * (1 - effective_spread / 2)
        sell_price = mid_price * (1 + effective_spread / 2)
        
        # Position-aware sizing
        buy_size = self.order_size
        sell_size = self.order_size
        
        # Reduce size if approaching position limits
        if current_position > self.max_position * 0.7:
            buy_size *= 0.5  # Reduce buying
        elif current_position < -self.max_position * 0.7:
            sell_size *= 0.5  # Reduce selling
        
        # Generate signals
        # Buy signal (stronger if negative imbalance = selling pressure)
        if current_position < self.max_position and imbalance < 0.2:
            signals.append({
                'side': 'buy',
                'price': buy_price,
                'size': buy_size,
                'reason': f'Market making (imbalance: {imbalance:.3f})'
            })
        
        # Sell signal (stronger if positive imbalance = buying pressure)
        if current_position > 0 and imbalance > -0.2:
            signals.append({
                'side': 'sell',
                'price': sell_price,
                'size': min(sell_size, current_position),
                'reason': f'Market making (imbalance: {imbalance:.3f})'
            })
        
        if signals:
            self.last_signal_time = timestamp
        
        return signals


def run_backtest_demo(historical_data: pd.DataFrame, 
                     initial_capital: float = 10000.0) -> Dict:
    """
    Run a complete backtest demonstration
    
    Args:
        historical_data: DataFrame with columns ['timestamp', 'bid', 'ask', 'bid_volume', 'ask_volume']
        initial_capital: Starting capital in USD
    
    Returns:
        Dictionary with backtest results and performance metrics
    """
    # Initialize
    engine = BacktestEngine(initial_capital)
    strategy = MarketMakingStrategy(
        base_spread=0.0005,  # 0.05%
        order_size=0.1,      # 0.1 BTC
        max_position=1.0     # Max 1 BTC position
    )
    
    print("🚀 Starting backtest...")
    print(f"📊 Data points: {len(historical_data)}")
    print(f"💰 Initial capital: ${initial_capital:,.2f}")
    print(f"📅 Period: {historical_data['timestamp'].iloc[0]} to {historical_data['timestamp'].iloc[-1]}")
    print()
    
    # Run backtest
    for idx, row in historical_data.iterrows():
        market_data = {
            'bid': row['bid'],
            'ask': row['ask'],
            'bid_volume': row.get('bid_volume', 1.0),
            'ask_volume': row.get('ask_volume', 1.0)
        }
        
        # Generate signals
        signals = strategy.generate_signals(
            market_data,
            engine.position,
            row['timestamp']
        )
        
        # Execute signals
        for signal in signals:
            result = engine.execute_trade(
                timestamp=row['timestamp'],
                side=signal['side'],
                price=signal['price'],
                size=signal['size'],
                order_type='maker'
            )
            
            if result['success']:
                trade = result['trade']
                print(f"✅ {signal['side'].upper():4s} {trade['size']:.4f} BTC @ ${trade['price']:,.2f} | "
                      f"PnL: ${trade['pnl']:+.2f} | Equity: ${trade['equity']:,.2f}")
    
    # Get results
    metrics = engine.get_performance_metrics()
    
    print()
    print("=" * 80)
    print("📊 BACKTEST RESULTS")
    print("=" * 80)
    
    return {
        'metrics': metrics,
        'trades': engine.get_trades_df(),
        'equity_curve': engine.get_equity_curve_df()
    }


if __name__ == "__main__":
    # This will be used in the demo
    print("Backtesting Engine Demo - Ready to use!")
