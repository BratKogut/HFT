"""
Comprehensive HFT Testing with Synthetic Market Data
Simulates realistic market conditions for multiple trading pairs
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
import json

# Trading pairs with realistic characteristics
TRADING_PAIRS = {
    'BTC/USDT': {
        'base_price': 95000.0,
        'daily_volatility': 0.025,  # 2.5%
        'spread_bps': 1.0,
        'volume_daily': 50000,  # BTC
        'trend_strength': 0.3
    },
    'ETH/USDT': {
        'base_price': 3400.0,
        'daily_volatility': 0.035,  # 3.5%
        'spread_bps': 2.0,
        'volume_daily': 500000,
        'trend_strength': 0.35
    },
    'SOL/USDT': {
        'base_price': 190.0,
        'daily_volatility': 0.05,  # 5%
        'spread_bps': 3.0,
        'volume_daily': 5000000,
        'trend_strength': 0.4
    },
    'XRP/USDT': {
        'base_price': 2.20,
        'daily_volatility': 0.04,  # 4%
        'spread_bps': 3.0,
        'volume_daily': 100000000,
        'trend_strength': 0.3
    },
    'DOGE/USDT': {
        'base_price': 0.35,
        'daily_volatility': 0.06,  # 6%
        'spread_bps': 5.0,
        'volume_daily': 500000000,
        'trend_strength': 0.45
    },
    'AVAX/USDT': {
        'base_price': 38.0,
        'daily_volatility': 0.045,
        'spread_bps': 4.0,
        'volume_daily': 10000000,
        'trend_strength': 0.35
    },
    'LINK/USDT': {
        'base_price': 22.0,
        'daily_volatility': 0.04,
        'spread_bps': 3.0,
        'volume_daily': 15000000,
        'trend_strength': 0.3
    },
    'MATIC/USDT': {
        'base_price': 0.48,
        'daily_volatility': 0.05,
        'spread_bps': 4.0,
        'volume_daily': 200000000,
        'trend_strength': 0.35
    }
}

INITIAL_CAPITAL = 10000.0
DAYS_TO_TEST = 7
MINUTES_PER_DAY = 1440


def generate_synthetic_ohlcv(
    base_price: float,
    daily_volatility: float,
    spread_bps: float,
    volume_daily: float,
    trend_strength: float,
    days: int = 7,
    seed: int = None
) -> pd.DataFrame:
    """Generate realistic OHLCV data"""
    if seed is not None:
        np.random.seed(seed)

    n_candles = days * MINUTES_PER_DAY
    minute_volatility = daily_volatility / np.sqrt(MINUTES_PER_DAY)
    avg_minute_volume = volume_daily / MINUTES_PER_DAY

    # Generate price path with trend and mean reversion
    timestamps = []
    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []

    current_price = base_price
    trend = np.random.choice([-1, 0, 1], p=[0.3, 0.4, 0.3])  # Initial trend

    start_time = datetime(2026, 1, 1, 0, 0, 0)

    for i in range(n_candles):
        # Regime changes
        if i % 480 == 0:  # Every 8 hours, potentially change regime
            trend = np.random.choice([-1, 0, 1], p=[0.3, 0.4, 0.3])

        # Hour of day effect (volatility varies)
        hour = (i // 60) % 24
        if 8 <= hour <= 16:  # US/EU market hours
            vol_mult = 1.3
        elif 0 <= hour <= 8:  # Asian market hours
            vol_mult = 1.1
        else:
            vol_mult = 0.8

        # Generate return with trend component
        trend_component = trend * trend_strength * minute_volatility
        random_component = np.random.normal(0, minute_volatility * vol_mult)

        # Mean reversion
        deviation = (current_price - base_price) / base_price
        mean_reversion = -deviation * 0.001

        total_return = trend_component + random_component + mean_reversion

        # OHLC generation
        open_price = current_price

        # Intrabar movement
        intrabar_vol = minute_volatility * vol_mult * np.random.uniform(0.5, 2.0)
        high_factor = abs(np.random.normal(0, intrabar_vol))
        low_factor = abs(np.random.normal(0, intrabar_vol))

        close_price = open_price * (1 + total_return)

        if total_return >= 0:  # Bullish candle
            high_price = max(open_price, close_price) * (1 + high_factor * 0.5)
            low_price = min(open_price, close_price) * (1 - low_factor * 0.3)
        else:  # Bearish candle
            high_price = max(open_price, close_price) * (1 + high_factor * 0.3)
            low_price = min(open_price, close_price) * (1 - low_factor * 0.5)

        # Volume (higher during volatile periods)
        vol_base = avg_minute_volume * np.random.lognormal(0, 0.5)
        volume = vol_base * vol_mult * (1 + abs(total_return) * 10)

        timestamps.append(start_time + timedelta(minutes=i))
        opens.append(open_price)
        highs.append(high_price)
        lows.append(low_price)
        closes.append(close_price)
        volumes.append(volume)

        current_price = close_price

    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    })

    return df


class BacktestEngine:
    """Enhanced backtesting engine"""

    def __init__(self, initial_capital: float, maker_fee: float = 0.001, taker_fee: float = 0.001):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0.0
        self.entry_price = 0.0
        self.trades = []
        self.equity_curve = []
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage = 0.0005
        self.peak_equity = initial_capital
        self.max_drawdown = 0.0

    def execute_trade(self, timestamp, side: str, price: float, size: float, is_maker: bool = True) -> bool:
        """Execute trade with realistic costs"""
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        slip = self.slippage if not is_maker else self.slippage * 0.5

        if side == 'buy':
            effective_price = price * (1 + slip)
        else:
            effective_price = price * (1 - slip)

        trade_value = size * effective_price
        fee = trade_value * fee_rate
        pnl = 0.0

        if side == 'buy':
            total_cost = trade_value + fee
            if self.capital < total_cost:
                return False
            self.capital -= total_cost
            self.position += size
            self.entry_price = effective_price
        else:
            if self.position < size:
                size = self.position
            if size <= 0:
                return False

            self.capital += trade_value - fee
            if self.entry_price > 0:
                pnl = (effective_price - self.entry_price) * size - fee
            self.position -= size
            if self.position == 0:
                self.entry_price = 0.0

        current_equity = self.capital + self.position * price

        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        dd = (self.peak_equity - current_equity) / self.peak_equity if self.peak_equity > 0 else 0
        if dd > self.max_drawdown:
            self.max_drawdown = dd

        self.equity_curve.append({
            'timestamp': timestamp,
            'equity': current_equity,
            'capital': self.capital,
            'position': self.position
        })

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
        """Calculate comprehensive metrics"""
        if len(self.equity_curve) < 2:
            return {}

        df = pd.DataFrame(self.equity_curve)
        df['returns'] = df['equity'].pct_change()

        final_equity = df['equity'].iloc[-1]
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100

        # Risk metrics
        returns_std = df['returns'].std()
        sharpe = (df['returns'].mean() / returns_std) * np.sqrt(525600) if returns_std > 0 else 0

        # Sortino ratio (downside deviation)
        negative_returns = df['returns'][df['returns'] < 0]
        downside_std = negative_returns.std() if len(negative_returns) > 0 else returns_std
        sortino = (df['returns'].mean() / downside_std) * np.sqrt(525600) if downside_std > 0 else 0

        # Trade statistics
        trade_pnls = [t['pnl'] for t in self.trades if t['pnl'] != 0]
        winning = sum(1 for p in trade_pnls if p > 0)
        losing = sum(1 for p in trade_pnls if p < 0)
        total_trades = len(trade_pnls)

        win_rate = (winning / total_trades * 100) if total_trades > 0 else 0

        avg_win = np.mean([p for p in trade_pnls if p > 0]) if winning > 0 else 0
        avg_loss = np.mean([p for p in trade_pnls if p < 0]) if losing > 0 else 0

        profit_factor = abs(avg_win * winning / (avg_loss * losing)) if losing > 0 and avg_loss != 0 else 0

        # Calmar ratio
        calmar = (total_return / 100) / self.max_drawdown if self.max_drawdown > 0 else 0

        return {
            'initial_capital': self.initial_capital,
            'final_equity': final_equity,
            'total_return_pct': total_return,
            'total_pnl': final_equity - self.initial_capital,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'max_drawdown_pct': self.max_drawdown * 100,
            'total_trades': len(self.trades),
            'winning_trades': winning,
            'losing_trades': losing,
            'win_rate_pct': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'total_fees': sum(t['fee'] for t in self.trades)
        }


class MarketMakingStrategy:
    """Market making with inventory management"""

    def __init__(self, spread_bps: float = 5.0, size_pct: float = 1.0, max_pos_pct: float = 10.0):
        self.spread = spread_bps / 10000
        self.size_pct = size_pct / 100
        self.max_pos_pct = max_pos_pct / 100
        self.cooldown = 60
        self.last_idx = -self.cooldown

    def generate_signals(self, idx, row, df, capital, position, entry_price) -> List[Dict]:
        signals = []

        if idx - self.last_idx < self.cooldown:
            return signals
        if idx < 120:
            return signals

        price = row['close']
        pos_value = position * price
        max_pos_value = capital * self.max_pos_pct

        # Indicators
        ma20 = df['close'].iloc[idx-20:idx].mean()
        ma60 = df['close'].iloc[idx-60:idx].mean()
        volatility = df['close'].iloc[idx-60:idx].std() / price

        # Spread check
        bar_spread = (row['high'] - row['low']) / price
        if bar_spread < self.spread * 0.5:
            return signals

        order_size = (capital * self.size_pct) / price

        # Trend-aware market making
        trend = (ma20 - ma60) / ma60

        if trend > 0.002:  # Uptrend
            if pos_value < max_pos_value * 0.8:
                signals.append({'side': 'buy', 'price': price, 'size': order_size, 'reason': 'mm_uptrend'})
                self.last_idx = idx
        elif trend < -0.002:  # Downtrend
            if position > order_size:
                signals.append({'side': 'sell', 'price': price, 'size': min(order_size, position), 'reason': 'mm_downtrend'})
                self.last_idx = idx
        else:  # Range
            if volatility > 0.01 and pos_value < max_pos_value * 0.5:
                signals.append({'side': 'buy', 'price': price, 'size': order_size * 0.5, 'reason': 'mm_range'})
                self.last_idx = idx

        return signals


class MomentumStrategy:
    """Momentum with RSI filter"""

    def __init__(self, lookback: int = 30, rsi_period: int = 14):
        self.lookback = lookback
        self.rsi_period = rsi_period
        self.cooldown = 120
        self.last_idx = -self.cooldown

    def calc_rsi(self, prices):
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-self.rsi_period:])
        avg_loss = np.mean(losses[-self.rsi_period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def generate_signals(self, idx, row, df, capital, position, entry_price) -> List[Dict]:
        signals = []

        if idx - self.last_idx < self.cooldown:
            return signals
        if idx < self.lookback + 20:
            return signals

        price = row['close']
        prices = df['close'].iloc[:idx+1].values

        # Momentum
        momentum = (price - prices[idx - self.lookback]) / prices[idx - self.lookback]
        rsi = self.calc_rsi(prices)

        order_size = (capital * 0.02) / price
        max_pos = (capital * 0.15) / price

        # Entry
        if momentum > 0.02 and rsi < 70 and position < max_pos:
            signals.append({'side': 'buy', 'price': price, 'size': order_size, 'reason': f'momentum_buy_rsi{rsi:.0f}'})
            self.last_idx = idx

        # Exit on overbought
        elif rsi > 75 and position > 0:
            signals.append({'side': 'sell', 'price': price, 'size': position * 0.5, 'reason': f'overbought_rsi{rsi:.0f}'})
            self.last_idx = idx

        # Stop loss
        elif position > 0 and entry_price > 0:
            pnl_pct = (price - entry_price) / entry_price
            if pnl_pct < -0.02:
                signals.append({'side': 'sell', 'price': price, 'size': position, 'reason': 'stop_loss'})
                self.last_idx = idx

        return signals


class MeanReversionStrategy:
    """Mean reversion with Bollinger Bands"""

    def __init__(self, period: int = 20, std_mult: float = 2.0):
        self.period = period
        self.std_mult = std_mult
        self.cooldown = 90
        self.last_idx = -self.cooldown

    def generate_signals(self, idx, row, df, capital, position, entry_price) -> List[Dict]:
        signals = []

        if idx - self.last_idx < self.cooldown:
            return signals
        if idx < self.period + 10:
            return signals

        price = row['close']
        prices = df['close'].iloc[idx-self.period:idx]

        ma = prices.mean()
        std = prices.std()
        upper = ma + self.std_mult * std
        lower = ma - self.std_mult * std

        order_size = (capital * 0.015) / price
        max_pos = (capital * 0.1) / price

        # Buy at lower band
        if price < lower and position < max_pos:
            signals.append({'side': 'buy', 'price': price, 'size': order_size, 'reason': 'bb_lower'})
            self.last_idx = idx

        # Sell at upper band
        elif price > upper and position > 0:
            signals.append({'side': 'sell', 'price': price, 'size': min(order_size, position), 'reason': 'bb_upper'})
            self.last_idx = idx

        # Take profit at MA
        elif position > 0 and entry_price > 0:
            if entry_price < ma < price:  # Bought below, now above MA
                signals.append({'side': 'sell', 'price': price, 'size': position * 0.5, 'reason': 'bb_tp_ma'})
                self.last_idx = idx

        return signals


class VolatilityBreakoutStrategy:
    """Volatility breakout strategy"""

    def __init__(self, atr_period: int = 14, breakout_mult: float = 1.5):
        self.atr_period = atr_period
        self.breakout_mult = breakout_mult
        self.cooldown = 180
        self.last_idx = -self.cooldown

    def calc_atr(self, df, idx):
        if idx < self.atr_period:
            return 0
        trs = []
        for i in range(idx - self.atr_period, idx):
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]
            prev_close = df['close'].iloc[i-1]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        return np.mean(trs)

    def generate_signals(self, idx, row, df, capital, position, entry_price) -> List[Dict]:
        signals = []

        if idx - self.last_idx < self.cooldown:
            return signals
        if idx < self.atr_period + 20:
            return signals

        price = row['close']
        atr = self.calc_atr(df, idx)

        if atr == 0:
            return signals

        # Previous day high/low (simplified to 1440 bars)
        lookback = min(1440, idx)
        prev_high = df['high'].iloc[idx-lookback:idx].max()
        prev_low = df['low'].iloc[idx-lookback:idx].min()

        order_size = (capital * 0.02) / price
        max_pos = (capital * 0.1) / price

        # Breakout above
        if price > prev_high + atr * self.breakout_mult and position < max_pos:
            signals.append({'side': 'buy', 'price': price, 'size': order_size, 'reason': 'vol_breakout_up'})
            self.last_idx = idx

        # Stop loss / trailing stop
        elif position > 0 and entry_price > 0:
            stop_price = entry_price - atr * 2
            if price < stop_price:
                signals.append({'side': 'sell', 'price': price, 'size': position, 'reason': 'vol_stop'})
                self.last_idx = idx

        return signals


def run_backtest(df: pd.DataFrame, strategy, initial_capital: float) -> Dict:
    """Run backtest"""
    engine = BacktestEngine(initial_capital)

    for idx in range(len(df)):
        row = df.iloc[idx]
        signals = strategy.generate_signals(
            idx, row, df,
            engine.capital, engine.position, engine.entry_price
        )
        for sig in signals:
            engine.execute_trade(row['timestamp'], sig['side'], sig['price'], sig['size'])

    # Close any remaining position at end
    if engine.position > 0:
        engine.execute_trade(df.iloc[-1]['timestamp'], 'sell', df.iloc[-1]['close'], engine.position)

    return engine.get_metrics()


def main():
    """Main test function"""
    print("=" * 100)
    print("🚀 HFT SYSTEM COMPREHENSIVE TEST - SYNTHETIC DATA")
    print("=" * 100)
    print(f"Trading Pairs: {len(TRADING_PAIRS)}")
    print(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"Test Period: {DAYS_TO_TEST} days ({DAYS_TO_TEST * 1440} candles per pair)")
    print("=" * 100)
    print()

    # Generate data for all pairs
    print("📊 Generating synthetic market data...")
    data = {}
    for symbol, params in TRADING_PAIRS.items():
        df = generate_synthetic_ohlcv(
            base_price=params['base_price'],
            daily_volatility=params['daily_volatility'],
            spread_bps=params['spread_bps'],
            volume_daily=params['volume_daily'],
            trend_strength=params['trend_strength'],
            days=DAYS_TO_TEST,
            seed=hash(symbol) % 2**32
        )
        data[symbol] = df
        print(f"  ✅ {symbol}: {len(df)} candles, ${df['close'].iloc[0]:,.2f} → ${df['close'].iloc[-1]:,.2f}")

    print()
    print("=" * 100)
    print("📈 RUNNING BACKTESTS")
    print("=" * 100)

    strategies = {
        'Market Making': lambda: MarketMakingStrategy(spread_bps=5.0, size_pct=1.0, max_pos_pct=10.0),
        'Momentum': lambda: MomentumStrategy(lookback=30, rsi_period=14),
        'Mean Reversion': lambda: MeanReversionStrategy(period=20, std_mult=2.0),
        'Vol Breakout': lambda: VolatilityBreakoutStrategy(atr_period=14, breakout_mult=1.5),
    }

    all_results = {}

    for symbol, df in data.items():
        print(f"\n{'='*80}")
        print(f"📊 {symbol}")
        print(f"{'='*80}")

        params = TRADING_PAIRS[symbol]
        price_change = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100
        print(f"  Price: ${df['close'].iloc[0]:,.4f} → ${df['close'].iloc[-1]:,.4f} ({price_change:+.2f}%)")
        print(f"  Volatility: {params['daily_volatility']*100:.1f}% daily")

        all_results[symbol] = {}

        for strat_name, strat_factory in strategies.items():
            strategy = strat_factory()
            metrics = run_backtest(df, strategy, INITIAL_CAPITAL)
            all_results[symbol][strat_name] = metrics

            if metrics:
                emoji = "✅" if metrics['total_return_pct'] > 0 else "❌"
                print(f"\n  {emoji} {strat_name}:")
                print(f"     Return: {metrics['total_return_pct']:+.2f}% | Sharpe: {metrics['sharpe_ratio']:.2f} | "
                      f"Max DD: {metrics['max_drawdown_pct']:.2f}% | Win Rate: {metrics['win_rate_pct']:.1f}%")

    # Summary
    print()
    print("=" * 100)
    print("📊 COMPREHENSIVE RESULTS SUMMARY")
    print("=" * 100)
    print()

    # Table header
    print(f"{'Symbol':<12} | {'Strategy':<15} | {'Return %':>10} | {'Sharpe':>8} | {'Sortino':>8} | "
          f"{'Max DD %':>8} | {'Win %':>7} | {'Trades':>7} | {'PF':>6}")
    print("-" * 110)

    best_combinations = []

    for symbol, strats in all_results.items():
        for strat_name, metrics in strats.items():
            if metrics:
                print(f"{symbol:<12} | {strat_name:<15} | {metrics['total_return_pct']:>+10.2f} | "
                      f"{metrics['sharpe_ratio']:>8.2f} | {metrics['sortino_ratio']:>8.2f} | "
                      f"{metrics['max_drawdown_pct']:>8.2f} | {metrics['win_rate_pct']:>6.1f}% | "
                      f"{metrics['total_trades']:>7} | {metrics['profit_factor']:>6.2f}")

                best_combinations.append({
                    'symbol': symbol,
                    'strategy': strat_name,
                    'return': metrics['total_return_pct'],
                    'sharpe': metrics['sharpe_ratio'],
                    'sortino': metrics['sortino_ratio'],
                    'max_dd': metrics['max_drawdown_pct'],
                    'win_rate': metrics['win_rate_pct'],
                    'profit_factor': metrics['profit_factor'],
                    'trades': metrics['total_trades']
                })

    # Rankings
    print()
    print("=" * 100)
    print("🏆 TOP 10 BEST COMBINATIONS (by Risk-Adjusted Return)")
    print("=" * 100)

    # Score = Sharpe * (1 - MaxDD/100) * (1 + Return/100)
    for combo in best_combinations:
        combo['score'] = combo['sharpe'] * (1 - combo['max_dd']/100) * (1 + combo['return']/100)

    best_combinations.sort(key=lambda x: x['score'], reverse=True)

    medals = ['🥇', '🥈', '🥉'] + ['  '] * 7

    for i, combo in enumerate(best_combinations[:10]):
        print(f"\n{medals[i]} #{i+1}: {combo['symbol']} + {combo['strategy']}")
        print(f"      Return: {combo['return']:+.2f}% | Sharpe: {combo['sharpe']:.2f} | Sortino: {combo['sortino']:.2f}")
        print(f"      Max DD: {combo['max_dd']:.2f}% | Win Rate: {combo['win_rate']:.1f}% | Profit Factor: {combo['profit_factor']:.2f}")
        print(f"      Trades: {combo['trades']} | Score: {combo['score']:.3f}")

    # Strategy performance summary
    print()
    print("=" * 100)
    print("📈 STRATEGY PERFORMANCE ACROSS ALL PAIRS")
    print("=" * 100)

    for strat_name in strategies.keys():
        strat_results = [r for r in best_combinations if r['strategy'] == strat_name]
        if strat_results:
            avg_return = np.mean([r['return'] for r in strat_results])
            avg_sharpe = np.mean([r['sharpe'] for r in strat_results])
            avg_dd = np.mean([r['max_dd'] for r in strat_results])
            avg_wr = np.mean([r['win_rate'] for r in strat_results])
            profitable = sum(1 for r in strat_results if r['return'] > 0)

            print(f"\n  {strat_name}:")
            print(f"    Avg Return: {avg_return:+.2f}% | Avg Sharpe: {avg_sharpe:.2f} | Avg Max DD: {avg_dd:.2f}%")
            print(f"    Avg Win Rate: {avg_wr:.1f}% | Profitable Pairs: {profitable}/{len(strat_results)}")

    # Asset ranking
    print()
    print("=" * 100)
    print("💎 BEST ASSETS FOR ALGORITHMIC TRADING")
    print("=" * 100)

    asset_scores = {}
    for combo in best_combinations:
        if combo['symbol'] not in asset_scores:
            asset_scores[combo['symbol']] = []
        asset_scores[combo['symbol']].append(combo['score'])

    asset_avg = [(sym, np.mean(scores)) for sym, scores in asset_scores.items()]
    asset_avg.sort(key=lambda x: x[1], reverse=True)

    for i, (symbol, avg_score) in enumerate(asset_avg, 1):
        best_strat = max([c for c in best_combinations if c['symbol'] == symbol], key=lambda x: x['score'])
        print(f"\n  #{i} {symbol}")
        print(f"      Average Score: {avg_score:.3f}")
        print(f"      Best Strategy: {best_strat['strategy']} (Return: {best_strat['return']:+.2f}%, Sharpe: {best_strat['sharpe']:.2f})")

    # Save results
    results_file = 'test_results_synthetic.json'
    with open(results_file, 'w') as f:
        serializable = {}
        for symbol, strats in all_results.items():
            serializable[symbol] = {}
            for strat, metrics in strats.items():
                if metrics:
                    serializable[symbol][strat] = {
                        k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                        for k, v in metrics.items()
                    }
        json.dump(serializable, f, indent=2, default=str)

    print()
    print(f"📁 Results saved to: {results_file}")
    print()
    print("=" * 100)
    print("✅ TESTING COMPLETE")
    print("=" * 100)

    return all_results


if __name__ == "__main__":
    main()
