#!/usr/bin/env python3
"""
Comprehensive backtest with optimized strategy on 60 days of data
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from strategies.optimized_liquidation_hunter import OptimizedLiquidationHunter
from core.l0_sanitizer import L0Sanitizer
from core.deterministic_fee_model import DeterministicFeeModel, OrderSide, OrderType
from core.drb_guard import DRBGuard, Position
from core.tca_analyzer import TCAAnalyzer
from core.wal_logger import WALLogger
from core.event_bus import EventBus, Event, EventType
from core.reason_codes import ReasonCodeTracker
import time

class OptimizedBacktestEngine:
    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        
        # Initialize components
        self.strategy = OptimizedLiquidationHunter(
            signal_threshold=0.75,      # Balanced - quality signals
            take_profit_pct=0.022,      # 2.2% TP - realistic
            stop_loss_pct=0.007,        # 0.7% SL - not too tight (3.1:1)
            min_volume_ratio=1.4,       # Balanced volume
            min_price_extremity=0.83    # Balanced extremity (83%)
        )
        
        self.l0_sanitizer = L0Sanitizer(
            max_latency_ms=1000,
            max_spread_bps=50,
            max_data_age_sec=60.0  # 1 minute for backtest
        )
        
        self.fee_model = DeterministicFeeModel(exchange='binance')
        self.drb_guard = DRBGuard(
            initial_capital=initial_capital,
            max_position_loss_pct=5.0,
            max_total_loss_pct=10.0,
            max_drawdown_pct=15.0,
            max_position_concentration=1.0  # Allow 100% for single-symbol backtest
        )
        self.tca = TCAAnalyzer()
        self.wal = WALLogger(log_path='/tmp/wal_backtest/wal.jsonl')
        self.event_bus = EventBus()
        self.reason_tracker = ReasonCodeTracker()
        
        # State
        self.positions = {}  # symbol -> Position
        self.closed_trades = []
        self.stats = {
            'ticks_processed': 0,
            'ticks_validated': 0,
            'signals_generated': 0,
            'trades_executed': 0,
            'trades_closed': 0,
            'tp_exits': 0,
            'sl_exits': 0
        }
        
    def run_backtest(self, data_file):
        """Run backtest on historical data"""
        print(f"\n🚀 Starting backtest on {data_file}")
        print(f"Initial capital: ${self.initial_capital:,.2f}\n")
        
        # Load data
        df = pd.read_csv(data_file)
        print(f"Loaded {len(df)} candles")
        print(f"Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
        print(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}\n")
        
        start_time = time.time()
        
        # Process each tick
        for idx, row in df.iterrows():
            self.process_tick(row.to_dict(), idx)
            
            # Progress update
            if (idx + 1) % 10000 == 0:
                elapsed = time.time() - start_time
                rate = (idx + 1) / elapsed
                print(f"Processed {idx+1}/{len(df)} ticks ({rate:.0f} ticks/sec)")
        
        # Close any open positions at end
        for symbol, pos in list(self.positions.items()):
            self._close_position(symbol, df['close'].iloc[-1], 'END_OF_BACKTEST')
        
        elapsed = time.time() - start_time
        print(f"\n✅ Backtest complete in {elapsed:.1f}s ({len(df)/elapsed:.0f} ticks/sec)")
        
        return self.generate_report()
    
    def process_tick(self, tick, idx):
        """Process single tick"""
        self.stats['ticks_processed'] += 1
        
        # Add required fields
        tick['symbol'] = 'BTC/USDT'
        tick['timestamp'] = time.time()  # Use current time for backtest
        
        # Calculate bid/ask from close
        spread_pct = 0.0001  # 0.01% spread
        tick['bid'] = round(tick['close'] * (1 - spread_pct), 2)
        tick['ask'] = round(tick['close'] * (1 + spread_pct), 2)
        
        # 1. L0 Sanitizer validation
        validation = self.l0_sanitizer.validate(tick)
        if not validation.valid:
            return
        
        self.stats['ticks_validated'] += 1
        
        # 2. Check existing positions for TP/SL
        self._check_positions(tick)
        
        # 3. Generate signal
        signal = self.strategy.analyze(tick)
        if signal:
            self.stats['signals_generated'] += 1
            
            # 4. Risk check
            can_trade = self._can_trade(signal)
            if can_trade:
                self._execute_trade(signal, tick)
            elif idx < 1000:  # Debug first 1000 ticks
                print(f"Trade blocked at tick {idx}: signal={signal['side']}, confidence={signal['confidence']:.2f}")
    
    def _check_positions(self, tick):
        """Check existing positions for TP/SL"""
        price = tick['close']
        
        for symbol, pos in list(self.positions.items()):
            # Calculate P&L
            if pos.side == 'LONG':
                pnl_pct = (price - pos.entry_price) / pos.entry_price
            else:  # SHORT
                pnl_pct = (pos.entry_price - price) / pos.entry_price
            
            # Check TP
            if pnl_pct >= pos.take_profit_pct:
                self._close_position(symbol, price, 'TAKE_PROFIT')
                self.stats['tp_exits'] += 1
            
            # Check SL
            elif pnl_pct <= -pos.stop_loss_pct:
                self._close_position(symbol, price, 'STOP_LOSS')
                self.stats['sl_exits'] += 1
    
    def _can_trade(self, signal):
        """Check if we can trade (risk management)"""
        # Check if position already exists
        if 'BTC/USDT' in self.positions:
            return False
        
        # DRB-Guard check - temporarily add position to check risk
        test_pos = Position(
            symbol='BTC/USDT',
            side=signal['side'],
            entry_price=signal['price'],
            size=self.capital * 0.05,  # 5% position
            current_price=signal['price']
        )
        
        # Temporarily add position
        self.drb_guard.update_position(test_pos)
        risk_check = self.drb_guard.check_risk()
        # Remove test position
        self.drb_guard.remove_position('BTC/USDT')
        
        # Debug
        if self.stats['ticks_processed'] < 1000 and risk_check.action not in ['allow', 'warn']:
            print(f"  Risk check failed: {risk_check.action} - {risk_check.reason}")
        
        # Accept ALLOW and WARN (WARN is just a warning, not a hard block)
        return risk_check.action in ['allow', 'warn']
    
    def _execute_trade(self, signal, tick):
        """Execute trade"""
        symbol = 'BTC/USDT'
        price = signal['price']
        side = signal['side']
        
        # Position size (5% of capital)
        position_value = self.capital * 0.05
        quantity = position_value / price
        
        # Simulate fill
        fill_result = self.fee_model.simulate_fill(
            order_id=f"backtest_{self.stats['trades_executed']}",
            symbol=symbol,
            side=OrderSide.BUY if side == 'LONG' else OrderSide.SELL,
            order_type=OrderType.MARKET,
            order_price=price,
            order_size=quantity,
            orderbook={'bid': tick.get('bid', price), 'ask': tick.get('ask', price)}
        )
        
        # Deduct fee from capital
        self.capital -= fill_result.fees_usd
        
        # Create position
        pos = Position(
            symbol=symbol,
            side=side,
            entry_price=fill_result.fill_price,
            size=quantity,  # Size in BTC, not USD
            current_price=price
        )
        
        # Store TP/SL separately
        pos.take_profit_pct = signal['take_profit_pct']
        pos.stop_loss_pct = signal['stop_loss_pct']
        
        self.positions[symbol] = pos
        self.stats['trades_executed'] += 1
    
    def _close_position(self, symbol, price, reason):
        """Close position"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        
        # Calculate P&L
        if pos.side == 'LONG':
            pnl = (price - pos.entry_price) * pos.size
        else:  # SHORT
            pnl = (pos.entry_price - price) * pos.size
        
        # Simulate fill (exit)
        fill_result = self.fee_model.simulate_fill(
            order_id=f"backtest_close_{self.stats['trades_closed']}",
            symbol=symbol,
            side=OrderSide.SELL if pos.side == 'LONG' else OrderSide.BUY,
            order_type=OrderType.MARKET,
            order_price=price,
            order_size=pos.size,
            orderbook={'bid': price * 0.9999, 'ask': price * 1.0001}
        )
        
        # Deduct fee
        pnl -= fill_result.fees_usd
        
        # Update capital
        self.capital += pnl
        
        # Record trade
        self.closed_trades.append({
            'symbol': symbol,
            'side': pos.side,
            'entry_price': pos.entry_price,
            'exit_price': price,
            'pnl': pnl,
            'pnl_pct': (pnl / (pos.size * pos.entry_price)) * 100,
            'reason': reason
        })
        
        # Remove position
        del self.positions[symbol]
        self.stats['trades_closed'] += 1
    
    def generate_report(self):
        """Generate performance report"""
        if not self.closed_trades:
            return {
                'error': 'No trades executed',
                'stats': self.stats
            }
        
        df_trades = pd.DataFrame(self.closed_trades)
        
        # Calculate metrics
        total_pnl = df_trades['pnl'].sum()
        total_return_pct = (total_pnl / self.initial_capital) * 100
        
        wins = df_trades[df_trades['pnl'] > 0]
        losses = df_trades[df_trades['pnl'] <= 0]
        
        win_rate = len(wins) / len(df_trades) * 100
        
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
        
        profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else float('inf')
        
        # Sharpe ratio (simplified)
        returns = df_trades['pnl'] / self.initial_capital
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        
        # Max drawdown
        cumulative = (self.initial_capital + df_trades['pnl'].cumsum())
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max * 100
        max_drawdown = drawdown.min()
        
        report = {
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'total_pnl': total_pnl,
            'total_return_pct': total_return_pct,
            'total_trades': len(df_trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_drawdown,
            'stats': self.stats,
            'exit_reasons': df_trades['reason'].value_counts().to_dict()
        }
        
        return report


if __name__ == '__main__':
    # Run backtest
    engine = OptimizedBacktestEngine(initial_capital=10000)
    report = engine.run_backtest('/home/ubuntu/HFT/data/historical/BTCUSDT_60d_synthetic.csv')
    
    # Print report
    print("\n" + "="*60)
    print("📊 BACKTEST RESULTS")
    print("="*60)
    
    if 'error' in report:
        print(f"\n❌ {report['error']}")
        print(f"\nStats: {report['stats']}")
    else:
        print(f"\n💰 Financial Performance:")
        print(f"  Initial Capital:    ${report['initial_capital']:,.2f}")
        print(f"  Final Capital:      ${report['final_capital']:,.2f}")
        print(f"  Total P&L:          ${report['total_pnl']:,.2f}")
        print(f"  Total Return:       {report['total_return_pct']:.2f}%")
        
        print(f"\n📈 Trading Statistics:")
        print(f"  Total Trades:       {report['total_trades']}")
        print(f"  Wins:               {report['wins']}")
        print(f"  Losses:             {report['losses']}")
        print(f"  Win Rate:           {report['win_rate']:.1f}%")
        print(f"  Avg Win:            ${report['avg_win']:.2f}")
        print(f"  Avg Loss:           ${report['avg_loss']:.2f}")
        print(f"  Profit Factor:      {report['profit_factor']:.2f}")
        
        print(f"\n📊 Risk Metrics:")
        print(f"  Sharpe Ratio:       {report['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown:       {report['max_drawdown_pct']:.2f}%")
        
        print(f"\n🚪 Exit Reasons:")
        for reason, count in report['exit_reasons'].items():
            print(f"  {reason:20s} {count:3d}")
        
        print(f"\n⚙️ System Stats:")
        for key, value in report['stats'].items():
            print(f"  {key:25s} {value}")
        
        print("\n" + "="*60)
