"""
Comprehensive Testing Script for HFT Trading Pairs
Tests multiple strategies on various trading pairs
"""

import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import json

# Configuration
TRADING_PAIRS = [
    'BTC/USDT',   # High liquidity, main pair
    'ETH/USDT',   # Second highest volume
    'SOL/USDT',   # High volatility
    'XRP/USDT',   # High volume altcoin
    'DOGE/USDT',  # Meme coin, very volatile
]

INITIAL_CAPITAL = 10000.0
DAYS_TO_TEST = 7
TIMEFRAME = '1m'


class DataDownloader:
    """Simple data downloader for backtesting"""

    def __init__(self):
        self.exchange = None
        self.cache_dir = 'data/historical'
        os.makedirs(self.cache_dir, exist_ok=True)

    async def initialize(self):
        """Initialize exchange"""
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        await self.exchange.load_markets()
        print("✅ Connected to Binance")

    async def download_ohlcv(self, symbol: str, days: int = 7) -> pd.DataFrame:
        """Download OHLCV data"""
        if not self.exchange:
            await self.initialize()

        # Check cache
        cache_file = os.path.join(self.cache_dir, f"{symbol.replace('/', '_')}_{TIMEFRAME}_{days}d.csv")
        if os.path.exists(cache_file):
            print(f"📁 Loading cached: {symbol}")
            df = pd.read_csv(cache_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df

        print(f"📥 Downloading {symbol}...")

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        all_candles = []
        current_time = int(start_date.timestamp() * 1000)
        end_time = int(end_date.timestamp() * 1000)

        while current_time < end_time:
            try:
                candles = await self.exchange.fetch_ohlcv(
                    symbol, TIMEFRAME, since=current_time, limit=1000
                )
                if not candles:
                    break
                all_candles.extend(candles)
                current_time = candles[-1][0] + 1
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"⚠️ Error: {e}")
                break

        if not all_candles:
            return pd.DataFrame()

        df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset=['timestamp']).reset_index(drop=True)

        # Cache
        df.to_csv(cache_file, index=False)
        print(f"✅ Downloaded {len(df)} candles for {symbol}")

        return df

    async def close(self):
        if self.exchange:
            await self.exchange.close()


class SimpleBacktestEngine:
    """Simple backtesting engine"""

    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0.0
        self.entry_price = 0.0
        self.trades = []
        self.equity_curve = []

        # Costs
        self.maker_fee = 0.001
        self.taker_fee = 0.001
        self.slippage = 0.0005

        # Stats
        self.peak_equity = initial_capital
        self.max_drawdown = 0.0

    def execute_trade(self, timestamp, side: str, price: float, size: float) -> bool:
        """Execute a trade"""
        effective_price = price * (1 + self.slippage) if side == 'buy' else price * (1 - self.slippage)
        trade_value = size * effective_price
        fee = trade_value * self.maker_fee

        pnl = 0.0

        if side == 'buy':
            if self.capital < trade_value + fee:
                return False
            self.position += size
            self.capital -= (trade_value + fee)
            self.entry_price = effective_price
        else:
            if self.position < size:
                return False
            self.position -= size
            self.capital += (trade_value - fee)
            if self.entry_price > 0:
                pnl = (effective_price - self.entry_price) * size - fee

        # Track equity
        current_equity = self.capital + (self.position * price)
        self.equity_curve.append({'timestamp': timestamp, 'equity': current_equity})

        # Track drawdown
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        drawdown = (self.peak_equity - current_equity) / self.peak_equity
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

        self.trades.append({
            'timestamp': timestamp,
            'side': side,
            'price': effective_price,
            'size': size,
            'fee': fee,
            'pnl': pnl,
            'equity': current_equity
        })

        return True

    def get_metrics(self) -> Dict:
        """Calculate performance metrics"""
        if len(self.equity_curve) < 2:
            return {}

        df = pd.DataFrame(self.equity_curve)
        df['returns'] = df['equity'].pct_change()

        final_equity = df['equity'].iloc[-1]
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100

        # Sharpe (annualized for minute data)
        returns_std = df['returns'].std()
        sharpe = (df['returns'].mean() / returns_std) * np.sqrt(525600) if returns_std > 0 else 0

        # Win rate
        winning = sum(1 for t in self.trades if t['pnl'] > 0)
        total = sum(1 for t in self.trades if t['pnl'] != 0)
        win_rate = (winning / total * 100) if total > 0 else 0

        # Profit factor
        wins = sum(t['pnl'] for t in self.trades if t['pnl'] > 0)
        losses = abs(sum(t['pnl'] for t in self.trades if t['pnl'] < 0))
        profit_factor = wins / losses if losses > 0 else 0

        return {
            'initial_capital': self.initial_capital,
            'final_equity': final_equity,
            'total_return_pct': total_return,
            'total_pnl': final_equity - self.initial_capital,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': self.max_drawdown * 100,
            'total_trades': len(self.trades),
            'win_rate_pct': win_rate,
            'profit_factor': profit_factor,
            'total_fees': sum(t['fee'] for t in self.trades)
        }


class MarketMakingStrategy:
    """Simple market making strategy"""

    def __init__(self, spread_bps: float = 5.0, order_size_pct: float = 1.0, max_position_pct: float = 10.0):
        self.spread_bps = spread_bps / 10000  # Convert to decimal
        self.order_size_pct = order_size_pct / 100
        self.max_position_pct = max_position_pct / 100
        self.cooldown_bars = 60  # 1 hour cooldown
        self.last_trade_idx = -self.cooldown_bars

    def generate_signals(self, idx: int, row: pd.Series, df: pd.DataFrame,
                        capital: float, position: float, entry_price: float) -> List[Dict]:
        """Generate trading signals"""
        signals = []

        # Cooldown check
        if idx - self.last_trade_idx < self.cooldown_bars:
            return signals

        price = row['close']

        # Position value limits
        position_value = position * price
        max_position_value = capital * self.max_position_pct

        # Calculate trend (simple)
        if idx < 60:
            return signals

        ma_short = df['close'].iloc[idx-20:idx].mean()
        ma_long = df['close'].iloc[idx-60:idx].mean()

        # Calculate volatility
        volatility = df['close'].iloc[idx-60:idx].std() / price

        # Spread from high-low
        spread = (row['high'] - row['low']) / price

        # Only trade if spread is meaningful
        if spread < self.spread_bps:
            return signals

        order_size = (capital * self.order_size_pct) / price

        # Trend following + mean reversion hybrid
        if ma_short > ma_long * 1.001:  # Uptrend
            if position_value < max_position_value * 0.8:
                signals.append({
                    'side': 'buy',
                    'price': price,
                    'size': order_size,
                    'reason': 'uptrend'
                })
                self.last_trade_idx = idx

        elif ma_short < ma_long * 0.999:  # Downtrend
            if position > order_size:
                signals.append({
                    'side': 'sell',
                    'price': price,
                    'size': min(order_size, position),
                    'reason': 'downtrend'
                })
                self.last_trade_idx = idx

        # Mean reversion on high volatility
        elif volatility > 0.01:  # High volatility
            if position_value < max_position_value * 0.5:
                signals.append({
                    'side': 'buy',
                    'price': price,
                    'size': order_size * 0.5,
                    'reason': 'volatility_buy'
                })
                self.last_trade_idx = idx

        return signals


class MomentumStrategy:
    """Momentum-based strategy"""

    def __init__(self, lookback: int = 30, threshold: float = 0.02):
        self.lookback = lookback
        self.threshold = threshold
        self.cooldown_bars = 120
        self.last_trade_idx = -self.cooldown_bars

    def generate_signals(self, idx: int, row: pd.Series, df: pd.DataFrame,
                        capital: float, position: float, entry_price: float) -> List[Dict]:
        """Generate momentum signals"""
        signals = []

        if idx < self.lookback + 10:
            return signals

        if idx - self.last_trade_idx < self.cooldown_bars:
            return signals

        price = row['close']

        # Calculate momentum
        past_price = df['close'].iloc[idx - self.lookback]
        momentum = (price - past_price) / past_price

        # Calculate RSI-like indicator
        gains = []
        losses = []
        for i in range(idx - 14, idx):
            change = df['close'].iloc[i] - df['close'].iloc[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = 100 - (100 / (1 + rs))

        order_size = (capital * 0.02) / price
        max_position = (capital * 0.15) / price

        # Strong momentum + not overbought
        if momentum > self.threshold and rsi < 70:
            if position < max_position:
                signals.append({
                    'side': 'buy',
                    'price': price,
                    'size': order_size,
                    'reason': f'momentum_buy (rsi:{rsi:.0f})'
                })
                self.last_trade_idx = idx

        # Take profit on overbought
        elif rsi > 75 and position > 0:
            signals.append({
                'side': 'sell',
                'price': price,
                'size': position * 0.5,
                'reason': f'overbought_sell (rsi:{rsi:.0f})'
            })
            self.last_trade_idx = idx

        # Stop loss
        elif position > 0 and entry_price > 0:
            pnl_pct = (price - entry_price) / entry_price
            if pnl_pct < -0.02:  # -2% stop loss
                signals.append({
                    'side': 'sell',
                    'price': price,
                    'size': position,
                    'reason': 'stop_loss'
                })
                self.last_trade_idx = idx

        return signals


def run_backtest(df: pd.DataFrame, strategy, initial_capital: float) -> Dict:
    """Run backtest on data with strategy"""
    engine = SimpleBacktestEngine(initial_capital)

    for idx in range(len(df)):
        row = df.iloc[idx]

        signals = strategy.generate_signals(
            idx, row, df,
            engine.capital, engine.position, engine.entry_price
        )

        for signal in signals:
            engine.execute_trade(
                row['timestamp'],
                signal['side'],
                signal['price'],
                signal['size']
            )

    return engine.get_metrics()


async def main():
    """Main test function"""
    print("=" * 80)
    print("🚀 HFT TRADING PAIRS TEST SUITE")
    print("=" * 80)
    print(f"Trading Pairs: {', '.join(TRADING_PAIRS)}")
    print(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"Test Period: {DAYS_TO_TEST} days")
    print(f"Timeframe: {TIMEFRAME}")
    print("=" * 80)
    print()

    # Download data
    downloader = DataDownloader()
    await downloader.initialize()

    data = {}
    for symbol in TRADING_PAIRS:
        try:
            df = await downloader.download_ohlcv(symbol, DAYS_TO_TEST)
            if not df.empty:
                data[symbol] = df
        except Exception as e:
            print(f"❌ Failed to download {symbol}: {e}")

    await downloader.close()

    print()
    print("=" * 80)
    print("📊 RUNNING BACKTESTS")
    print("=" * 80)
    print()

    # Test strategies
    strategies = {
        'Market Making': MarketMakingStrategy(spread_bps=5.0, order_size_pct=1.0, max_position_pct=10.0),
        'Momentum': MomentumStrategy(lookback=30, threshold=0.02),
    }

    results = {}

    for symbol, df in data.items():
        print(f"\n{'='*60}")
        print(f"Testing {symbol}")
        print(f"{'='*60}")
        print(f"Data points: {len(df)}")
        print(f"Price range: ${df['low'].min():,.2f} - ${df['high'].max():,.2f}")
        print(f"Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")

        results[symbol] = {}

        for strategy_name, strategy in strategies.items():
            # Reset strategy state
            if hasattr(strategy, 'last_trade_idx'):
                strategy.last_trade_idx = -1000

            metrics = run_backtest(df, strategy, INITIAL_CAPITAL)
            results[symbol][strategy_name] = metrics

            if metrics:
                emoji = "✅" if metrics['total_return_pct'] > 0 else "❌"
                print(f"\n{emoji} {strategy_name}:")
                print(f"   Return: {metrics['total_return_pct']:+.2f}%")
                print(f"   Sharpe: {metrics['sharpe_ratio']:.2f}")
                print(f"   Max DD: {metrics['max_drawdown_pct']:.2f}%")
                print(f"   Trades: {metrics['total_trades']}")
                print(f"   Win Rate: {metrics['win_rate_pct']:.1f}%")

    # Summary table
    print()
    print("=" * 80)
    print("📊 SUMMARY TABLE")
    print("=" * 80)
    print()

    print(f"{'Symbol':<12} | {'Strategy':<15} | {'Return %':>10} | {'Sharpe':>8} | {'Max DD %':>10} | {'Win Rate':>10}")
    print("-" * 80)

    best_combinations = []

    for symbol, strats in results.items():
        for strat_name, metrics in strats.items():
            if metrics:
                print(f"{symbol:<12} | {strat_name:<15} | {metrics['total_return_pct']:>+10.2f} | "
                      f"{metrics['sharpe_ratio']:>8.2f} | {metrics['max_drawdown_pct']:>10.2f} | "
                      f"{metrics['win_rate_pct']:>9.1f}%")

                best_combinations.append({
                    'symbol': symbol,
                    'strategy': strat_name,
                    'return': metrics['total_return_pct'],
                    'sharpe': metrics['sharpe_ratio'],
                    'max_dd': metrics['max_drawdown_pct'],
                    'win_rate': metrics['win_rate_pct']
                })

    # Best performers
    print()
    print("=" * 80)
    print("🏆 TOP PERFORMERS (by Sharpe Ratio)")
    print("=" * 80)

    best_combinations.sort(key=lambda x: x['sharpe'], reverse=True)

    for i, combo in enumerate(best_combinations[:5], 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"{emoji} #{i}: {combo['symbol']} + {combo['strategy']}")
        print(f"      Return: {combo['return']:+.2f}% | Sharpe: {combo['sharpe']:.2f} | "
              f"Max DD: {combo['max_dd']:.2f}% | Win Rate: {combo['win_rate']:.1f}%")

    # Save results
    results_file = 'test_results.json'
    with open(results_file, 'w') as f:
        # Convert to serializable format
        serializable_results = {}
        for symbol, strats in results.items():
            serializable_results[symbol] = {}
            for strat_name, metrics in strats.items():
                if metrics:
                    serializable_results[symbol][strat_name] = {
                        k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                        for k, v in metrics.items()
                    }
        json.dump(serializable_results, f, indent=2, default=str)

    print()
    print(f"📁 Results saved to: {results_file}")
    print()
    print("=" * 80)
    print("✅ TESTING COMPLETE")
    print("=" * 80)

    return results


if __name__ == "__main__":
    asyncio.run(main())
