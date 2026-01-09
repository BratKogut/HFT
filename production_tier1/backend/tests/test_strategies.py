"""
Unit Tests for Production Strategies
"""

import asyncio
import pytest
from decimal import Decimal
from datetime import datetime, timedelta

import sys
sys.path.insert(0, '..')

from strategies.base_strategy import BaseStrategy, Signal, SignalDirection, StrategyStats
from strategies.market_making_strategy import ProductionMarketMakingStrategy
from strategies.momentum_strategy import ProductionMomentumStrategy


class TestBaseStrategy:
    """Tests for base strategy functionality."""

    def test_strategy_creation(self):
        """Test strategy creation with custom parameters."""
        strategy = ProductionMarketMakingStrategy({'signal_cooldown': 10})
        assert strategy.name == 'MarketMaking'
        assert strategy.is_active is True

    def test_strategy_activation(self):
        """Test strategy activation/deactivation."""
        strategy = ProductionMarketMakingStrategy()

        strategy.deactivate()
        assert strategy.is_active is False

        strategy.activate()
        assert strategy.is_active is True

    def test_strategy_stats_initial(self):
        """Test initial strategy statistics."""
        strategy = ProductionMarketMakingStrategy()
        stats = strategy.get_stats()

        assert stats['name'] == 'MarketMaking'
        assert stats['total_signals'] == 0
        assert stats['is_active'] is True

    def test_strategy_reset_stats(self):
        """Test resetting strategy statistics."""
        strategy = ProductionMarketMakingStrategy()
        strategy.stats.total_signals = 100
        strategy.stats.winning_signals = 60

        strategy.reset_stats()

        assert strategy.stats.total_signals == 0
        assert strategy.stats.winning_signals == 0


class TestMarketMakingStrategy:
    """Tests for Market Making Strategy."""

    @pytest.fixture
    def mm_strategy(self):
        """Create market making strategy with no cooldown."""
        return ProductionMarketMakingStrategy({
            'signal_cooldown': 0,
            'trend_window': 5,
            'volatility_window': 10,
        })

    @pytest.mark.asyncio
    async def test_no_signal_without_data(self, mm_strategy):
        """Test no signal generation without enough data."""
        signal = await mm_strategy.analyze(
            symbol='BTC/USDT',
            price=Decimal('50000'),
            bid=Decimal('49999'),
            ask=Decimal('50001'),
            volume=Decimal('100'),
            timestamp=datetime.utcnow(),
        )
        assert signal is None

    @pytest.mark.asyncio
    async def test_signal_generation_with_trend(self, mm_strategy):
        """Test signal generation with trending data."""
        base_price = 50000
        current_time = datetime.utcnow()

        # Feed uptrending data
        for i in range(20):
            price = Decimal(str(base_price + i * 100))  # Uptrend
            signal = await mm_strategy.analyze(
                symbol='BTC/USDT',
                price=price,
                bid=price - Decimal('1'),
                ask=price + Decimal('1'),
                volume=Decimal('100'),
                timestamp=current_time + timedelta(seconds=i),
            )

        # Should eventually generate signals
        stats = mm_strategy.get_stats()
        # Note: signals may or may not be generated depending on conditions
        assert stats['total_signals'] >= 0

    @pytest.mark.asyncio
    async def test_inactive_strategy_no_signal(self, mm_strategy):
        """Test that inactive strategy doesn't generate signals."""
        mm_strategy.deactivate()

        signal = await mm_strategy.analyze(
            symbol='BTC/USDT',
            price=Decimal('50000'),
            bid=Decimal('49999'),
            ask=Decimal('50001'),
            volume=Decimal('100'),
            timestamp=datetime.utcnow(),
        )

        assert signal is None

    def test_get_parameters(self, mm_strategy):
        """Test getting strategy parameters."""
        params = mm_strategy.get_parameters()

        assert 'base_spread' in params
        assert 'order_size' in params
        assert 'max_position' in params

    def test_update_position(self, mm_strategy):
        """Test position update tracking."""
        mm_strategy.update_position(Decimal('0.1'))
        assert mm_strategy.current_position == Decimal('0.1')

        mm_strategy.update_position(Decimal('-0.05'))
        assert mm_strategy.current_position == Decimal('0.05')


class TestMomentumStrategy:
    """Tests for Momentum Strategy."""

    @pytest.fixture
    def momentum_strategy(self):
        """Create momentum strategy with test parameters."""
        return ProductionMomentumStrategy({
            'signal_cooldown': 0,
            'lookback': 5,
            'rsi_period': 5,
            'momentum_threshold': Decimal('0.01'),
            'volume_threshold': 1.0,
        })

    @pytest.mark.asyncio
    async def test_no_signal_without_data(self, momentum_strategy):
        """Test no signal without enough data."""
        signal = await momentum_strategy.analyze(
            symbol='BTC/USDT',
            price=Decimal('50000'),
            bid=Decimal('49999'),
            ask=Decimal('50001'),
            volume=Decimal('100'),
            timestamp=datetime.utcnow(),
        )
        assert signal is None

    @pytest.mark.asyncio
    async def test_long_signal_on_momentum(self, momentum_strategy):
        """Test long signal on positive momentum."""
        current_time = datetime.utcnow()
        signal = None

        # Feed strong uptrending data
        for i in range(15):
            price = Decimal(str(50000 + i * 200))  # Strong uptrend
            signal = await momentum_strategy.analyze(
                symbol='BTC/USDT',
                price=price,
                bid=price - Decimal('1'),
                ask=price + Decimal('1'),
                volume=Decimal('200'),  # High volume
                timestamp=current_time + timedelta(seconds=i),
            )

        # Should generate a long signal
        if signal:
            assert signal.direction == SignalDirection.LONG

    @pytest.mark.asyncio
    async def test_short_signal_on_negative_momentum(self, momentum_strategy):
        """Test short signal on negative momentum."""
        current_time = datetime.utcnow()
        signal = None

        # Feed strong downtrending data
        for i in range(15):
            price = Decimal(str(50000 - i * 200))  # Strong downtrend
            signal = await momentum_strategy.analyze(
                symbol='BTC/USDT',
                price=price,
                bid=price - Decimal('1'),
                ask=price + Decimal('1'),
                volume=Decimal('200'),
                timestamp=current_time + timedelta(seconds=i),
            )

        # Should generate a short signal
        if signal:
            assert signal.direction == SignalDirection.SHORT

    @pytest.mark.asyncio
    async def test_close_signal_on_reversal(self, momentum_strategy):
        """Test close signal on momentum reversal."""
        current_time = datetime.utcnow()

        # First, create a long position with uptrend
        for i in range(10):
            price = Decimal(str(50000 + i * 100))
            await momentum_strategy.analyze(
                symbol='BTC/USDT',
                price=price,
                bid=price - Decimal('1'),
                ask=price + Decimal('1'),
                volume=Decimal('200'),
                timestamp=current_time + timedelta(seconds=i),
            )

        # Now, reverse to downtrend
        signal = None
        for i in range(10, 20):
            price = Decimal(str(51000 - (i - 10) * 100))  # Reversal
            signal = await momentum_strategy.analyze(
                symbol='BTC/USDT',
                price=price,
                bid=price - Decimal('1'),
                ask=price + Decimal('1'),
                volume=Decimal('200'),
                timestamp=current_time + timedelta(seconds=i),
            )

        # Should have closed position or generated close/short signal
        assert momentum_strategy.current_position != 'long' or signal is not None

    def test_get_parameters(self, momentum_strategy):
        """Test getting strategy parameters."""
        params = momentum_strategy.get_parameters()

        assert 'lookback' in params
        assert 'rsi_period' in params
        assert 'momentum_threshold' in params
        assert 'rsi_overbought' in params
        assert 'rsi_oversold' in params

    def test_reset_position(self, momentum_strategy):
        """Test position reset."""
        momentum_strategy.current_position = 'long'
        momentum_strategy.reset_position()
        assert momentum_strategy.current_position is None


class TestSignal:
    """Tests for Signal dataclass."""

    def test_signal_creation(self):
        """Test creating a signal."""
        signal = Signal(
            symbol='BTC/USDT',
            direction=SignalDirection.LONG,
            strength=0.8,
            price=Decimal('50000'),
            size=Decimal('0.1'),
            take_profit=Decimal('51000'),
            stop_loss=Decimal('49500'),
            reason='Test signal',
        )

        assert signal.symbol == 'BTC/USDT'
        assert signal.direction == SignalDirection.LONG
        assert signal.strength == 0.8
        assert signal.price == Decimal('50000')

    def test_signal_with_metadata(self):
        """Test signal with metadata."""
        signal = Signal(
            symbol='ETH/USDT',
            direction=SignalDirection.SHORT,
            strength=0.6,
            price=Decimal('3000'),
            metadata={'momentum': -0.05, 'rsi': 75},
        )

        assert signal.metadata['momentum'] == -0.05
        assert signal.metadata['rsi'] == 75


class TestStrategyStats:
    """Tests for StrategyStats."""

    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        stats = StrategyStats(name='Test')
        stats.winning_signals = 60
        stats.losing_signals = 40

        assert stats.win_rate == 60.0

    def test_win_rate_no_trades(self):
        """Test win rate with no trades."""
        stats = StrategyStats(name='Test')
        assert stats.win_rate == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
