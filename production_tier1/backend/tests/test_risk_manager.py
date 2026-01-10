"""
Unit Tests for Production Risk Manager
"""

import asyncio
import pytest
from decimal import Decimal
from datetime import datetime

import sys
sys.path.insert(0, '..')

from risk.risk_manager import (
    ProductionRiskManager,
    RiskLimits,
    RiskLevel,
    PositionState,
)


@pytest.fixture
def risk_limits():
    """Default risk limits for testing."""
    return RiskLimits(
        max_position_size=Decimal("1.0"),
        max_position_value=Decimal("10000"),
        max_total_exposure=Decimal("50000"),
        max_positions=5,
        max_daily_loss_pct=Decimal("0.05"),
        max_drawdown_pct=Decimal("0.20"),
        max_risk_per_trade_pct=Decimal("0.02"),
        max_consecutive_losses=5,
        min_time_between_trades=0,  # Disable for testing
    )


@pytest.fixture
def risk_manager(risk_limits):
    """Create risk manager for testing."""
    return ProductionRiskManager(
        limits=risk_limits,
        initial_capital=Decimal("10000"),
    )


class TestPreTradeCheck:
    """Tests for pre-trade risk checks."""

    @pytest.mark.asyncio
    async def test_valid_trade_passes(self, risk_manager):
        """Test that valid trades pass checks."""
        # size * price = 0.01 * 10000 = 100, which is within max_risk (10000 * 0.02 = 200)
        allowed, reason = await risk_manager.pre_trade_check(
            symbol="BTC/USDT",
            side="long",
            size=Decimal("0.01"),
            price=Decimal("10000"),
        )
        assert allowed is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_exceeds_position_size_limit(self, risk_manager):
        """Test rejection when position size exceeds limit."""
        allowed, reason = await risk_manager.pre_trade_check(
            symbol="BTC/USDT",
            side="long",
            size=Decimal("2.0"),  # Exceeds max_position_size of 1.0
            price=Decimal("10000"),
        )
        assert allowed is False
        assert "Size" in reason

    @pytest.mark.asyncio
    async def test_exceeds_position_value_limit(self, risk_manager):
        """Test rejection when position value exceeds limit."""
        allowed, reason = await risk_manager.pre_trade_check(
            symbol="BTC/USDT",
            side="long",
            size=Decimal("0.5"),
            price=Decimal("30000"),  # 0.5 * 30000 = 15000 > 10000
        )
        assert allowed is False
        assert "Value" in reason

    @pytest.mark.asyncio
    async def test_halted_trading_blocked(self, risk_manager):
        """Test that trades are blocked when halted."""
        await risk_manager.halt_trading("Test halt")

        allowed, reason = await risk_manager.pre_trade_check(
            symbol="BTC/USDT",
            side="long",
            size=Decimal("0.1"),
            price=Decimal("10000"),
        )
        assert allowed is False
        assert "halted" in reason.lower()

    @pytest.mark.asyncio
    async def test_existing_position_blocked(self, risk_manager):
        """Test that duplicate positions are blocked."""
        await risk_manager.open_position(
            symbol="BTC/USDT",
            side="long",
            size=Decimal("0.1"),
            entry_price=Decimal("10000"),
        )

        allowed, reason = await risk_manager.pre_trade_check(
            symbol="BTC/USDT",
            side="long",
            size=Decimal("0.1"),
            price=Decimal("10000"),
        )
        assert allowed is False
        assert "Already have position" in reason


class TestPositionManagement:
    """Tests for position management."""

    @pytest.mark.asyncio
    async def test_open_position(self, risk_manager):
        """Test opening a position."""
        position = await risk_manager.open_position(
            symbol="BTC/USDT",
            side="long",
            size=Decimal("0.1"),
            entry_price=Decimal("50000"),
        )

        assert position is not None
        assert position.symbol == "BTC/USDT"
        assert position.side == "long"
        assert position.size == Decimal("0.1")
        assert position.entry_price == Decimal("50000")
        assert risk_manager.state.total_trades == 1

    @pytest.mark.asyncio
    async def test_close_position_profit(self, risk_manager):
        """Test closing a position with profit."""
        await risk_manager.open_position(
            symbol="BTC/USDT",
            side="long",
            size=Decimal("0.1"),
            entry_price=Decimal("50000"),
        )

        pnl = await risk_manager.close_position(
            symbol="BTC/USDT",
            exit_price=Decimal("51000"),  # 2% profit
        )

        assert pnl == Decimal("100.0")  # (51000 - 50000) * 0.1
        assert risk_manager.state.winning_trades == 1
        assert risk_manager.state.current_capital == Decimal("10100")

    @pytest.mark.asyncio
    async def test_close_position_loss(self, risk_manager):
        """Test closing a position with loss."""
        await risk_manager.open_position(
            symbol="BTC/USDT",
            side="long",
            size=Decimal("0.1"),
            entry_price=Decimal("50000"),
        )

        pnl = await risk_manager.close_position(
            symbol="BTC/USDT",
            exit_price=Decimal("49000"),  # 2% loss
        )

        assert pnl == Decimal("-100.0")
        assert risk_manager.state.losing_trades == 1
        assert risk_manager.state.consecutive_losses == 1

    @pytest.mark.asyncio
    async def test_update_prices(self, risk_manager):
        """Test updating position prices."""
        await risk_manager.open_position(
            symbol="BTC/USDT",
            side="long",
            size=Decimal("0.1"),
            entry_price=Decimal("50000"),
        )

        await risk_manager.update_prices({"BTC/USDT": Decimal("55000")})

        position = risk_manager.get_position("BTC/USDT")
        assert position is not None
        assert position.unrealized_pnl == Decimal("500")  # (55000 - 50000) * 0.1


class TestRiskLevels:
    """Tests for risk level management."""

    @pytest.mark.asyncio
    async def test_normal_risk_level(self, risk_manager):
        """Test normal risk level at start."""
        assert risk_manager.state.risk_level == RiskLevel.NORMAL

    @pytest.mark.asyncio
    async def test_halt_changes_risk_level(self, risk_manager):
        """Test that halting changes risk level."""
        await risk_manager.halt_trading("Test")
        assert risk_manager.state.risk_level == RiskLevel.HALTED

    @pytest.mark.asyncio
    async def test_resume_restores_risk_level(self, risk_manager):
        """Test that resuming restores risk level."""
        await risk_manager.halt_trading("Test")
        await risk_manager.resume_trading()
        assert risk_manager.state.risk_level == RiskLevel.NORMAL
        assert risk_manager.state.is_halted is False


class TestStatistics:
    """Tests for statistics tracking."""

    @pytest.mark.asyncio
    async def test_initial_stats(self, risk_manager):
        """Test initial statistics."""
        stats = risk_manager.get_stats()

        assert stats["base_capital"] == 10000.0
        assert stats["current_capital"] == 10000.0
        assert stats["total_trades"] == 0
        assert stats["win_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_after_trades(self, risk_manager):
        """Test statistics after trades."""
        # Win
        await risk_manager.open_position("BTC/USDT", "long", Decimal("0.1"), Decimal("50000"))
        await risk_manager.close_position("BTC/USDT", Decimal("51000"))

        # Loss
        await risk_manager.open_position("ETH/USDT", "long", Decimal("1.0"), Decimal("3000"))
        await risk_manager.close_position("ETH/USDT", Decimal("2900"))

        stats = risk_manager.get_stats()

        assert stats["total_trades"] == 2
        assert stats["winning_trades"] == 1
        assert stats["losing_trades"] == 1
        assert stats["win_rate"] == 50.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
