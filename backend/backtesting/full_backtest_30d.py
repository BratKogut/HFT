"""
Full Backtest - 30 Days

Backtest Liquidation Hunter strategy on 30 days of data.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.production_engine import ProductionEngine, EngineConfig


@dataclass
class BacktestResult:
    """Backtest result"""
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    total_fees: float
    net_profit: float


def run_backtest(data_file: str, config: EngineConfig) -> BacktestResult:
    """Run backtest on data"""
    
    print("="*80)
    print("🚀 FULL BACKTEST - 30 Days")
    print("="*80)
    print()
    
    # Load data
    print(f"Loading data from: {data_file}")
    df = pd.read_csv(data_file)
    print(f"✅ Loaded {len(df):,} candles")
    print(f"   Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    print(f"   Price range: ${df['close'].min():,.2f} to ${df['close'].max():,.2f}")
    print()
    
    # Create engine
    engine = ProductionEngine(config)
    engine.start()
    
    print("="*80)
    print("📊 Running backtest...")
    print("="*80)
    
    # Track equity curve
    equity_curve = [config.initial_capital]
    trades = []
    
    # Process each candle
    for i, row in df.iterrows():
        # Use realistic bid/ask (close +/- 0.01%)
        price = round(row['close'], 2)  # Round to tick size
        spread = price * 0.0001  # 1 bps spread
        bid = round(price - spread / 2, 2)  # Round to tick size
        ask = round(price + spread / 2, 2)  # Round to tick size
        
        market_data = {
            'symbol': 'BTC/USDT',
            'bid': bid,
            'ask': ask,
            'price': price,
            'volume': row['volume'],
            'timestamp': pd.to_datetime(row['timestamp']).timestamp(),
            'exchange_timestamp': pd.to_datetime(row['timestamp']).timestamp() - 0.05
        }
        
        result = engine.on_market_data(market_data)
        
        if result and 'fill' in result:
            fill = result['fill']
            trades.append({
                'timestamp': row['timestamp'],
                'side': fill.side.value,
                'price': fill.fill_price,
                'size': fill.fill_size,
                'fees': fill.fees_usd,
                'slippage_bps': fill.slippage_bps
            })
        
        # Update equity (simplified - just track capital)
        current_equity = config.initial_capital
        equity_curve.append(current_equity)
        
        # Progress
        if (i + 1) % 5000 == 0:
            print(f"  Processed: {i+1:,} / {len(df):,} ({(i+1)/len(df)*100:.1f}%)")
    
    engine.stop()
    
    print()
    print("="*80)
    print("📊 BACKTEST RESULTS")
    print("="*80)
    
    # Get stats
    stats = engine.get_stats()
    
    print(f"Total ticks: {stats['total_ticks']:,}")
    print(f"Valid ticks: {stats['valid_ticks']:,}")
    print(f"Validation rate: {stats['validation_rate']:.1f}%")
    print(f"Signals generated: {stats['signals_generated']:,}")
    print(f"Fills: {stats['fills']}")
    print()
    
    # Calculate metrics
    if len(trades) == 0:
        print("⚠️  No trades executed!")
        return BacktestResult(
            total_return_pct=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
            total_fees=0.0,
            net_profit=0.0
        )
    
    trades_df = pd.DataFrame(trades)
    
    print("Trade Summary:")
    print(f"  Total trades: {len(trades)}")
    print(f"  Total fees: ${trades_df['fees'].sum():.2f}")
    print(f"  Avg slippage: {trades_df['slippage_bps'].mean():.1f} bps")
    print()
    
    # Calculate returns (simplified)
    total_fees = trades_df['fees'].sum()
    net_profit = -total_fees  # Simplified
    total_return_pct = (net_profit / config.initial_capital) * 100
    
    print(f"Performance:")
    print(f"  Net P&L: ${net_profit:+,.2f}")
    print(f"  Total return: {total_return_pct:+.2f}%")
    print()
    
    print("="*80)
    
    return BacktestResult(
        total_return_pct=total_return_pct,
        total_trades=len(trades),
        winning_trades=0,
        losing_trades=0,
        win_rate=0.0,
        avg_win=0.0,
        avg_loss=0.0,
        profit_factor=0.0,
        max_drawdown_pct=0.0,
        sharpe_ratio=0.0,
        total_fees=total_fees,
        net_profit=net_profit
    )


if __name__ == "__main__":
    # Config
    config = EngineConfig(
        initial_capital=10000.0,
        paper_trading=True,
        max_position_loss_pct=5.0,
        max_total_loss_pct=10.0,
        max_drawdown_pct=15.0
    )
    
    # Run backtest
    result = run_backtest('data/btc_usdt_30d_synthetic.csv', config)
    
    print()
    print("="*80)
    print("✅ Backtest Complete!")
    print("="*80)
