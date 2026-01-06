#!/usr/bin/env python3
"""
Final comprehensive backtest with optimized strategy
Simplified to work with existing class signatures
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
import time

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from strategies.optimized_liquidation_hunter import OptimizedLiquidationHunter

class SimplifiedBacktestEngine:
    """Simplified backtest engine that focuses on strategy performance"""
    
    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        
        # Strategy
        self.strategy = OptimizedLiquidationHunter(
            signal_threshold=0.7,
            take_profit_pct=0.02,
            stop_loss_pct=0.008
        )
        
        # Trading parameters
        self.position_size_pct = 0.05  # 5% per trade
        self.maker_fee = 0.001  # 0.1%
        self.taker_fee = 0.001  # 0.1%
        
        # State
        self.position = None  # Current position
        self.trades = []
        
        # Stats
        self.stats = {
            'ticks_processed': 0,
            'signals_generated': 0,
            'trades_executed': 0,
            'trades_closed': 0,
            'tp_exits': 0,
            'sl_exits': 0
        }
    
    def run_backtest(self, data_file):
        """Run backtest on historical data"""
        print(f"\n🚀 Starting backtest: {Path(data_file).name}")
        print(f"Initial capital: ${self.initial_capital:,.2f}\n")
        
        # Load data
        df = pd.read_csv(data_file)
        print(f"📊 Data loaded:")
        print(f"  Candles: {len(df):,}")
        print(f"  Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
        print(f"  Price: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        print(f"  Return: {((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.2f}%\n")
        
        start_time = time.time()
        
        # Process each tick
        for idx, row in df.iterrows():
            self.process_tick(row.to_dict())
            
            # Progress
            if (idx + 1) % 10000 == 0:
                elapsed = time.time() - start_time
                rate = (idx + 1) / elapsed
                pct = ((idx + 1) / len(df)) * 100
                print(f"Progress: {idx+1:,}/{len(df):,} ({pct:.1f}%) - {rate:.0f} ticks/sec")
        
        # Close any open position
        if self.position:
            self._close_position(df['close'].iloc[-1], 'END_OF_BACKTEST')
        
        elapsed = time.time() - start_time
        print(f"\n✅ Backtest complete: {elapsed:.1f}s ({len(df)/elapsed:.0f} ticks/sec)\n")
        
        return self.generate_report()
    
    def process_tick(self, tick):
        """Process single tick"""
        self.stats['ticks_processed'] += 1
        
        price = tick['close']
        
        # Check existing position for TP/SL
        if self.position:
            self._check_position_exit(price)
        
        # Generate new signal if no position
        if not self.position:
            signal = self.strategy.analyze(tick)
            if signal:
                self.stats['signals_generated'] += 1
                self._execute_trade(signal)
    
    def _check_position_exit(self, price):
        """Check if position should be closed"""
        if not self.position:
            return
        
        pos = self.position
        
        # Calculate P&L %
        if pos['side'] == 'LONG':
            pnl_pct = (price - pos['entry_price']) / pos['entry_price']
        else:  # SHORT
            pnl_pct = (pos['entry_price'] - price) / pos['entry_price']
        
        # Check TP
        if pnl_pct >= pos['take_profit_pct']:
            self._close_position(price, 'TAKE_PROFIT')
            self.stats['tp_exits'] += 1
        
        # Check SL
        elif pnl_pct <= -pos['stop_loss_pct']:
            self._close_position(price, 'STOP_LOSS')
            self.stats['sl_exits'] += 1
    
    def _execute_trade(self, signal):
        """Execute trade"""
        price = signal['price']
        side = signal['side']
        
        # Position size
        position_value = self.capital * self.position_size_pct
        quantity = position_value / price
        
        # Entry fee
        entry_fee = position_value * self.taker_fee
        self.capital -= entry_fee
        
        # Create position
        self.position = {
            'side': side,
            'entry_price': price,
            'quantity': quantity,
            'position_value': position_value,
            'take_profit_pct': signal['take_profit_pct'],
            'stop_loss_pct': signal['stop_loss_pct'],
            'entry_fee': entry_fee,
            'reason': signal.get('reason', 'unknown')
        }
        
        self.stats['trades_executed'] += 1
    
    def _close_position(self, price, exit_reason):
        """Close position"""
        if not self.position:
            return
        
        pos = self.position
        
        # Calculate P&L
        if pos['side'] == 'LONG':
            pnl = (price - pos['entry_price']) * pos['quantity']
        else:  # SHORT
            pnl = (pos['entry_price'] - price) * pos['quantity']
        
        # Exit fee
        exit_value = price * pos['quantity']
        exit_fee = exit_value * self.taker_fee
        
        # Net P&L
        net_pnl = pnl - pos['entry_fee'] - exit_fee
        
        # Update capital
        self.capital += net_pnl
        
        # Record trade
        self.trades.append({
            'side': pos['side'],
            'entry_price': pos['entry_price'],
            'exit_price': price,
            'quantity': pos['quantity'],
            'gross_pnl': pnl,
            'entry_fee': pos['entry_fee'],
            'exit_fee': exit_fee,
            'net_pnl': net_pnl,
            'return_pct': (net_pnl / pos['position_value']) * 100,
            'exit_reason': exit_reason,
            'entry_reason': pos['reason']
        })
        
        # Clear position
        self.position = None
        self.stats['trades_closed'] += 1
    
    def generate_report(self):
        """Generate performance report"""
        if not self.trades:
            return {
                'error': 'No trades executed',
                'stats': self.stats
            }
        
        df = pd.DataFrame(self.trades)
        
        # Financial metrics
        total_pnl = df['net_pnl'].sum()
        total_return_pct = (total_pnl / self.initial_capital) * 100
        
        # Trading metrics
        wins = df[df['net_pnl'] > 0]
        losses = df[df['net_pnl'] <= 0]
        win_rate = (len(wins) / len(df)) * 100
        
        avg_win = wins['net_pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['net_pnl'].mean() if len(losses) > 0 else 0
        
        total_fees = df['entry_fee'].sum() + df['exit_fee'].sum()
        
        # Profit factor
        if len(losses) > 0 and losses['net_pnl'].sum() != 0:
            profit_factor = abs(wins['net_pnl'].sum() / losses['net_pnl'].sum())
        else:
            profit_factor = float('inf') if len(wins) > 0 else 0
        
        # Risk metrics
        returns = df['return_pct'] / 100
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        
        # Drawdown
        cumulative = self.initial_capital + df['net_pnl'].cumsum()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max * 100
        max_drawdown = drawdown.min()
        
        # Exit reasons
        exit_reasons = df['exit_reason'].value_counts().to_dict()
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'total_pnl': total_pnl,
            'total_return_pct': total_return_pct,
            'total_trades': len(df),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_win_pct': wins['return_pct'].mean() if len(wins) > 0 else 0,
            'avg_loss_pct': losses['return_pct'].mean() if len(losses) > 0 else 0,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_drawdown,
            'total_fees': total_fees,
            'exit_reasons': exit_reasons,
            'stats': self.stats
        }


def print_report(report):
    """Print formatted report"""
    print("="*70)
    print("📊 BACKTEST RESULTS")
    print("="*70)
    
    if 'error' in report:
        print(f"\n❌ {report['error']}")
        print(f"\nStats:")
        for key, value in report['stats'].items():
            print(f"  {key:25s} {value:,}")
        return
    
    print(f"\n💰 Financial Performance:")
    print(f"  Initial Capital:      ${report['initial_capital']:>12,.2f}")
    print(f"  Final Capital:        ${report['final_capital']:>12,.2f}")
    print(f"  Total P&L:            ${report['total_pnl']:>12,.2f}")
    print(f"  Total Return:         {report['total_return_pct']:>12.2f}%")
    print(f"  Total Fees Paid:      ${report['total_fees']:>12,.2f}")
    
    print(f"\n📈 Trading Statistics:")
    print(f"  Total Trades:         {report['total_trades']:>12,}")
    print(f"  Wins:                 {report['wins']:>12,}")
    print(f"  Losses:               {report['losses']:>12,}")
    print(f"  Win Rate:             {report['win_rate']:>12.1f}%")
    
    print(f"\n💵 Average Trade:")
    print(f"  Avg Win:              ${report['avg_win']:>12,.2f} ({report['avg_win_pct']:>6.2f}%)")
    print(f"  Avg Loss:             ${report['avg_loss']:>12,.2f} ({report['avg_loss_pct']:>6.2f}%)")
    print(f"  Profit Factor:        {report['profit_factor']:>12.2f}")
    
    print(f"\n📊 Risk Metrics:")
    print(f"  Sharpe Ratio:         {report['sharpe_ratio']:>12.2f}")
    print(f"  Max Drawdown:         {report['max_drawdown_pct']:>12.2f}%")
    
    print(f"\n🚪 Exit Reasons:")
    for reason, count in report['exit_reasons'].items():
        pct = (count / report['total_trades']) * 100
        print(f"  {reason:25s} {count:>5,} ({pct:>5.1f}%)")
    
    print(f"\n⚙️ System Stats:")
    for key, value in report['stats'].items():
        print(f"  {key:25s} {value:>12,}")
    
    print("\n" + "="*70)


if __name__ == '__main__':
    # Run backtest
    engine = SimplifiedBacktestEngine(initial_capital=10000)
    report = engine.run_backtest('/home/ubuntu/HFT/data/historical/BTCUSDT_60d_synthetic.csv')
    
    # Print report
    print_report(report)
