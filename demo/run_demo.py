"""
HFT System Demo - Interactive Demonstration

This demo shows:
1. How backtesting works with realistic market data
2. Market making strategy in action
3. Performance metrics and analysis
4. What the improved system will look like
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backtesting.backtest_engine import run_backtest_demo, BacktestEngine, MarketMakingStrategy


def generate_realistic_market_data(
    base_price: float = 45000.0,
    num_points: int = 1000,
    volatility: float = 0.001,
    spread_bps: float = 5.0
) -> pd.DataFrame:
    """
    Generate realistic market data for demonstration
    
    Simulates BTC/USD market with:
    - Random walk price movement
    - Realistic bid-ask spread
    - Volume fluctuations
    - Order book imbalance
    """
    print("📊 Generating realistic market data...")
    print(f"   Base price: ${base_price:,.2f}")
    print(f"   Data points: {num_points}")
    print(f"   Volatility: {volatility*100:.2f}%")
    print(f"   Spread: {spread_bps} bps")
    print()
    
    # Generate timestamps (1-minute intervals)
    start_time = datetime.now() - timedelta(minutes=num_points)
    timestamps = [start_time + timedelta(minutes=i) for i in range(num_points)]
    
    # Generate price movement (random walk with drift)
    returns = np.random.normal(0, volatility, num_points)
    prices = base_price * np.exp(np.cumsum(returns))
    
    # Add some trends and mean reversion
    trend = np.sin(np.linspace(0, 4*np.pi, num_points)) * 0.02
    prices = prices * (1 + trend)
    
    # Generate bid-ask spread
    spread_pct = spread_bps / 10000  # Convert bps to percentage
    spreads = np.random.uniform(spread_pct * 0.5, spread_pct * 1.5, num_points)
    
    bids = prices * (1 - spreads / 2)
    asks = prices * (1 + spreads / 2)
    
    # Generate volumes (with some correlation to price movement)
    base_volume = 10.0
    volume_noise = np.random.uniform(0.5, 1.5, num_points)
    bid_volumes = base_volume * volume_noise
    ask_volumes = base_volume * np.random.uniform(0.5, 1.5, num_points)
    
    # Create DataFrame
    df = pd.DataFrame({
        'timestamp': timestamps,
        'bid': bids,
        'ask': asks,
        'mid': prices,
        'bid_volume': bid_volumes,
        'ask_volume': ask_volumes
    })
    
    return df


def print_performance_report(metrics: dict):
    """Print formatted performance report"""
    
    print()
    print("=" * 80)
    print("📊 PERFORMANCE METRICS")
    print("=" * 80)
    print()
    
    # Capital & Returns
    print("💰 CAPITAL & RETURNS")
    print(f"   Initial Capital:        ${metrics['initial_capital']:>12,.2f}")
    print(f"   Final Equity:           ${metrics['final_equity']:>12,.2f}")
    print(f"   Total PnL:              ${metrics['total_pnl']:>12,.2f}")
    print(f"   Total Return:           {metrics['total_return']:>12.2f}%")
    print()
    
    # Risk Metrics
    print("📉 RISK METRICS")
    print(f"   Sharpe Ratio:           {metrics['sharpe_ratio']:>12.2f}")
    print(f"   Max Drawdown:           {metrics['max_drawdown']:>12.2f}%")
    print()
    
    # Trading Stats
    print("📈 TRADING STATISTICS")
    print(f"   Total Trades:           {metrics['total_trades']:>12}")
    print(f"   Winning Trades:         {metrics['winning_trades']:>12}")
    print(f"   Losing Trades:          {metrics['losing_trades']:>12}")
    print(f"   Win Rate:               {metrics['win_rate']:>12.2f}%")
    print(f"   Avg Trade PnL:          ${metrics['avg_trade_pnl']:>12.2f}")
    print(f"   Profit Factor:          {metrics['profit_factor']:>12.2f}")
    print()
    
    # Costs
    print("💸 COSTS")
    print(f"   Total Fees Paid:        ${metrics['total_fees_paid']:>12,.2f}")
    print()
    
    # Assessment
    print("=" * 80)
    print("🎯 ASSESSMENT")
    print("=" * 80)
    print()
    
    if metrics['sharpe_ratio'] > 2.0:
        print("✅ EXCELLENT - Sharpe ratio > 2.0 (very good risk-adjusted returns)")
    elif metrics['sharpe_ratio'] > 1.0:
        print("✅ GOOD - Sharpe ratio > 1.0 (acceptable risk-adjusted returns)")
    elif metrics['sharpe_ratio'] > 0.5:
        print("⚠️  MARGINAL - Sharpe ratio > 0.5 (needs improvement)")
    else:
        print("❌ POOR - Sharpe ratio < 0.5 (strategy not profitable)")
    
    print()
    
    if metrics['win_rate'] > 60:
        print("✅ EXCELLENT - Win rate > 60%")
    elif metrics['win_rate'] > 50:
        print("✅ GOOD - Win rate > 50%")
    else:
        print("⚠️  NEEDS IMPROVEMENT - Win rate < 50%")
    
    print()
    
    if metrics['max_drawdown'] < 10:
        print("✅ LOW RISK - Max drawdown < 10%")
    elif metrics['max_drawdown'] < 20:
        print("✅ MEDIUM RISK - Max drawdown < 20%")
    elif metrics['max_drawdown'] < 30:
        print("⚠️  HIGH RISK - Max drawdown < 30%")
    else:
        print("❌ VERY HIGH RISK - Max drawdown > 30%")
    
    print()
    print("=" * 80)


def print_next_steps():
    """Print next steps for implementation"""
    
    print()
    print("=" * 80)
    print("🚀 NEXT STEPS - IMPLEMENTATION PLAN")
    print("=" * 80)
    print()
    
    print("This demo shows what the system will do. Now we'll implement:")
    print()
    
    print("📦 PHASE 1: CCXT Pro Integration (Week 1-2)")
    print("   ✅ Connect to Binance/Kraken via WebSocket")
    print("   ✅ Real-time market data feed")
    print("   ✅ Order placement API")
    print("   ✅ Test on testnet first")
    print()
    
    print("📊 PHASE 2: Backtesting (Week 2-3)")
    print("   ✅ Download historical data from Binance")
    print("   ✅ Run strategy on real historical data")
    print("   ✅ Optimize parameters")
    print("   ✅ Validate on out-of-sample data")
    print()
    
    print("🎯 PHASE 3: Strategy Enhancement (Week 3-4)")
    print("   ✅ Add volume profile analysis")
    print("   ✅ Add order flow indicators")
    print("   ✅ Improve position sizing")
    print("   ✅ Add multiple timeframe analysis")
    print()
    
    print("📝 PHASE 4: Paper Trading (Week 4-5)")
    print("   ✅ Connect to live market data")
    print("   ✅ Simulate orders (don't actually place)")
    print("   ✅ Monitor for 1-2 weeks")
    print("   ✅ Verify strategy works in live conditions")
    print()
    
    print("🚀 PHASE 5: Production (Week 5-6)")
    print("   ✅ Deploy to VPS")
    print("   ✅ Start with small capital ($1K-2K)")
    print("   ✅ Monitor 24/7")
    print("   ✅ Scale up gradually")
    print()
    
    print("=" * 80)
    print()
    print("💡 Ready to start implementation? (CCXT Pro + Backtesting)")
    print()


def main():
    """Run the complete demo"""
    
    print()
    print("=" * 80)
    print("🎬 HFT SYSTEM DEMO - INTERACTIVE DEMONSTRATION")
    print("=" * 80)
    print()
    print("This demo shows how your improved HFT system will work:")
    print("  • Backtesting with realistic market data")
    print("  • Market making strategy in action")
    print("  • Performance metrics and risk analysis")
    print("  • What to expect from the real system")
    print()
    print("=" * 80)
    print()
    
    # Configuration
    INITIAL_CAPITAL = 10000.0  # $10K (your budget range)
    NUM_DAYS = 7               # 7 days of data
    POINTS_PER_DAY = 1440      # 1-minute bars
    TOTAL_POINTS = NUM_DAYS * POINTS_PER_DAY
    
    # Generate market data
    market_data = generate_realistic_market_data(
        base_price=45000.0,
        num_points=TOTAL_POINTS,
        volatility=0.001,  # 0.1% per minute
        spread_bps=5.0     # 5 basis points
    )
    
    print(f"✅ Generated {len(market_data)} data points ({NUM_DAYS} days)")
    print(f"   Price range: ${market_data['mid'].min():,.2f} - ${market_data['mid'].max():,.2f}")
    print(f"   Avg spread: {((market_data['ask'] - market_data['bid']) / market_data['mid'] * 10000).mean():.2f} bps")
    print()
    
    # Run backtest
    print("=" * 80)
    print("🔄 RUNNING BACKTEST")
    print("=" * 80)
    print()
    
    results = run_backtest_demo(market_data, INITIAL_CAPITAL)
    
    # Print results
    print_performance_report(results['metrics'])
    
    # Show sample trades
    print()
    print("=" * 80)
    print("📋 SAMPLE TRADES (Last 10)")
    print("=" * 80)
    print()
    
    trades_df = results['trades']
    if len(trades_df) > 0:
        last_trades = trades_df.tail(10)
        for idx, trade in last_trades.iterrows():
            print(f"{trade['timestamp'].strftime('%Y-%m-%d %H:%M')} | "
                  f"{trade['side'].upper():4s} | "
                  f"{trade['size']:.4f} BTC @ ${trade['price']:>8,.2f} | "
                  f"PnL: ${trade['pnl']:>+8.2f} | "
                  f"Equity: ${trade['equity']:>10,.2f}")
    else:
        print("No trades executed (spread too tight or other constraints)")
    
    # Print next steps
    print_next_steps()
    
    # Save results
    output_dir = "demo/data"
    os.makedirs(output_dir, exist_ok=True)
    
    trades_df.to_csv(f"{output_dir}/demo_trades.csv", index=False)
    results['equity_curve'].to_csv(f"{output_dir}/demo_equity_curve.csv", index=False)
    
    print(f"💾 Results saved to {output_dir}/")
    print(f"   - demo_trades.csv")
    print(f"   - demo_equity_curve.csv")
    print()
    
    print("=" * 80)
    print("✅ DEMO COMPLETE")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
