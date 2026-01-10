"""
Backtest Liquidation Hunter V2 on real Binance data
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

from liquidation_hunter_v2 import LiquidationHunterV2


async def backtest_liquidation_hunter_v2(data_file: str, initial_capital: float = 10000.0):
    """Run backtest on historical data"""
    
    print("="*80)
    print("🎯 LIQUIDATION HUNTER V2 BACKTEST")
    print("   Enhanced with CVD + Trend Filter")
    print("="*80)
    print()
    
    # Load data
    print(f"📁 Loading data: {data_file}")
    df = pd.read_csv(data_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    print(f"✅ Loaded {len(df)} candles")
    print(f"   Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    print(f"   Price: ${df['close'].iloc[0]:,.2f} → ${df['close'].iloc[-1]:,.2f}")
    print(f"   Change: {((df['close'].iloc[-1]/df['close'].iloc[0])-1)*100:+.2f}%")
    print()
    
    # Initialize
    strategy = LiquidationHunterV2(
        min_cluster_volume=100.0,
        entry_distance_pct=0.015,
        base_take_profit_pct=0.012,
        base_stop_loss_pct=0.012
    )
    
    capital = initial_capital
    position = None
    trades = []
    
    print(f"💰 Initial capital: ${capital:,.2f}")
    print()
    print("="*80)
    print("🔄 RUNNING BACKTEST...")
    print("="*80)
    print()
    
    # Run backtest
    for idx, row in df.iterrows():
        current_price = row['close']
        high = row['high']
        low = row['low']
        volume = row['volume']
        
        # Simulate CVD data (in production, use real aggTrades)
        is_buyer_maker = np.random.rand() > 0.5
        
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
                    'size': position['size'],
                    'pnl': pnl,
                    'reason': reason,
                    'confidence': position['confidence'],
                    'capital': capital
                })
                
                pnl_pct = (pnl / (position['entry_price'] * position['size'])) * 100
                emoji = '✅' if pnl > 0 else '❌'
                
                print(f"{emoji} {position['side'].upper():4s} | "
                      f"Entry: ${position['entry_price']:,.2f} | "
                      f"Exit: ${current_price:,.2f} | "
                      f"PnL: ${pnl:+7.2f} ({pnl_pct:+.2f}%) | "
                      f"Conf: {position['confidence']:.2f} | "
                      f"{reason:12s} | "
                      f"Capital: ${capital:,.2f}")
                
                position = None
        
        # If no position, look for entry
        else:
            signal = await strategy.analyze_market(
                current_price=current_price,
                high=high,
                low=low,
                volume=volume,
                is_buyer_maker=is_buyer_maker
            )
            
            if signal:
                # Enter position
                position = signal
                print(f"\n🎯 SIGNAL: {signal['reason']}")
                print(f"   {signal['side'].upper()} {signal['size']:.4f} BTC @ ${signal['entry_price']:,.2f}")
                print(f"   TP: ${signal['take_profit']:,.2f} | SL: ${signal['stop_loss']:,.2f}")
                print(f"   Confidence: {signal['confidence']:.2%}\n")
    
    # Calculate metrics
    print()
    print("="*80)
    print("📊 RESULTS")
    print("="*80)
    print()
    
    if trades:
        trades_df = pd.DataFrame(trades)
        
        total_pnl = trades_df['pnl'].sum()
        final_return = (capital / initial_capital - 1) * 100
        
        wins = (trades_df['pnl'] > 0).sum()
        losses = (trades_df['pnl'] < 0).sum()
        win_rate = wins / len(trades_df) * 100
        
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losses > 0 else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # Calculate Sharpe ratio
        returns = trades_df['pnl'] / (trades_df['entry_price'] * trades_df['size'])
        sharpe = (returns.mean() / returns.std()) * np.sqrt(len(trades_df)) if returns.std() > 0 else 0
        
        print(f"💰 CAPITAL & RETURNS")
        print(f"   Initial Capital:        ${initial_capital:>12,.2f}")
        print(f"   Final Capital:          ${capital:>12,.2f}")
        print(f"   Total PnL:              ${total_pnl:>12,.2f}")
        print(f"   Return:                 {final_return:>12.2f}%")
        print()
        
        print(f"📈 TRADING STATISTICS")
        print(f"   Total Trades:           {len(trades_df):>12}")
        print(f"   Winning Trades:         {wins:>12}")
        print(f"   Losing Trades:          {losses:>12}")
        print(f"   Win Rate:               {win_rate:>12.2f}%")
        print()
        
        print(f"💚 Avg Win:                ${avg_win:>12.2f}")
        print(f"💔 Avg Loss:               ${avg_loss:>12.2f}")
        print(f"📊 Profit Factor:          {profit_factor:>12.2f}")
        print(f"📈 Sharpe Ratio:           {sharpe:>12.2f}")
        print()
        
        # Strategy stats
        stats = strategy.get_stats()
        print(f"🎯 STRATEGY STATS")
        print(f"   Signals Generated:      {stats['signals_generated']:>12}")
        print(f"   Signals Filtered:       {stats['signals_filtered']:>12}")
        print(f"   Filter Rate:            {stats['filter_rate']:>12.2f}%")
        print()
        
        print("="*80)
        
        # Assessment
        if win_rate > 60 and sharpe > 1.5:
            print("✅ EXCELLENT - Strategy ready for paper trading!")
        elif win_rate > 50 and sharpe > 1.0:
            print("✅ GOOD - Strategy shows promise")
        elif win_rate > 40:
            print("⚠️  MARGINAL - Needs optimization")
        else:
            print("❌ POOR - Major improvements needed")
        
        print("="*80)
        
        return {
            'trades': trades_df,
            'final_capital': capital,
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'sharpe': sharpe,
            'stats': stats
        }
    else:
        print("❌ No trades executed")
        return None


if __name__ == "__main__":
    data_file = "../../data/historical/BTC_USDT_1m_20251230_20260106.csv"
    
    if os.path.exists(data_file):
        results = asyncio.run(backtest_liquidation_hunter_v2(data_file, initial_capital=10000.0))
    else:
        print(f"❌ Data file not found: {data_file}")
        print("Run data_downloader.py first")
