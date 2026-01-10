"""
Unit Tests for Trading Models
"""

import pytest
from decimal import Decimal
from datetime import datetime

import sys
sys.path.insert(0, '..')

from models.trade import Trade, TradeStatus, TradeSide
from models.position import Position, PositionSide
from models.order import Order, OrderStatus, OrderType, OrderSide, TimeInForce


class TestTradeModel:
    """Tests for Trade model."""

    def test_trade_creation(self):
        """Test basic trade creation."""
        trade = Trade(
            trade_id='T001',
            symbol='BTC/USDT',
            side=TradeSide.BUY,
            quantity=Decimal('0.1'),
            price=Decimal('50000'),
            value=Decimal('5000'),
        )

        assert trade.trade_id == 'T001'
        assert trade.symbol == 'BTC/USDT'
        assert trade.side == TradeSide.BUY
        assert trade.quantity == Decimal('0.1')
        assert trade.status == TradeStatus.EXECUTED

    def test_trade_from_order_fill(self):
        """Test creating trade from order fill."""
        trade = Trade.from_order_fill(
            trade_id='T002',
            order_id='O001',
            symbol='ETH/USDT',
            side=TradeSide.SELL,
            quantity=Decimal('1.0'),
            price=Decimal('3000'),
            commission=Decimal('3'),
            is_maker=True,
        )

        assert trade.order_id == 'O001'
        assert trade.value == Decimal('3000')  # 1.0 * 3000
        assert trade.is_maker is True
        assert trade.commission == Decimal('3')

    def test_trade_net_value_buy(self):
        """Test net value calculation for buy trade."""
        trade = Trade(
            trade_id='T003',
            symbol='BTC/USDT',
            side=TradeSide.BUY,
            quantity=Decimal('0.1'),
            price=Decimal('50000'),
            value=Decimal('5000'),
            commission=Decimal('5'),
        )

        net_value = trade.calculate_net_value()
        assert net_value == Decimal('5005')  # value + commission

    def test_trade_net_value_sell(self):
        """Test net value calculation for sell trade."""
        trade = Trade(
            trade_id='T004',
            symbol='BTC/USDT',
            side=TradeSide.SELL,
            quantity=Decimal('0.1'),
            price=Decimal('50000'),
            value=Decimal('5000'),
            commission=Decimal('5'),
        )

        net_value = trade.calculate_net_value()
        assert net_value == Decimal('4995')  # value - commission

    def test_trade_is_profitable(self):
        """Test profitability check."""
        trade = Trade(
            trade_id='T005',
            symbol='BTC/USDT',
            side=TradeSide.BUY,
            quantity=Decimal('0.1'),
            price=Decimal('50000'),
            value=Decimal('5000'),
            pnl=Decimal('100'),
        )

        assert trade.is_profitable is True

        trade.pnl = Decimal('-50')
        assert trade.is_profitable is False


class TestPositionModel:
    """Tests for Position model."""

    @pytest.fixture
    def long_position(self):
        """Create a long position for testing."""
        return Position(
            position_id='P001',
            symbol='BTC/USDT',
            side=PositionSide.LONG,
            size=Decimal('0.1'),
            entry_price=Decimal('50000'),
        )

    @pytest.fixture
    def short_position(self):
        """Create a short position for testing."""
        return Position(
            position_id='P002',
            symbol='ETH/USDT',
            side=PositionSide.SHORT,
            size=Decimal('1.0'),
            entry_price=Decimal('3000'),
        )

    def test_position_creation(self, long_position):
        """Test basic position creation."""
        assert long_position.position_id == 'P001'
        assert long_position.side == PositionSide.LONG
        assert long_position.is_open is True

    def test_update_price_long(self, long_position):
        """Test price update for long position."""
        long_position.update_price(Decimal('52000'))

        assert long_position.current_price == Decimal('52000')
        assert long_position.unrealized_pnl == Decimal('200')  # (52000-50000) * 0.1

    def test_update_price_short(self, short_position):
        """Test price update for short position."""
        short_position.update_price(Decimal('2800'))

        assert short_position.current_price == Decimal('2800')
        assert short_position.unrealized_pnl == Decimal('200')  # (3000-2800) * 1.0

    def test_add_to_position(self, long_position):
        """Test adding to existing position."""
        long_position.add_to_position(
            quantity=Decimal('0.1'),
            price=Decimal('52000'),
            trade_id='T001',
        )

        assert long_position.size == Decimal('0.2')
        # New avg price: (50000*0.1 + 52000*0.1) / 0.2 = 51000
        assert long_position.entry_price == Decimal('51000')
        assert 'T001' in long_position.trade_ids

    def test_reduce_position(self, long_position):
        """Test reducing position size."""
        pnl = long_position.reduce_position(
            quantity=Decimal('0.05'),
            price=Decimal('52000'),
            trade_id='T002',
        )

        assert long_position.size == Decimal('0.05')
        assert pnl == Decimal('100')  # (52000-50000) * 0.05
        assert long_position.realized_pnl == Decimal('100')

    def test_close_position(self, long_position):
        """Test closing entire position."""
        pnl = long_position.close(
            price=Decimal('51000'),
            trade_id='T003',
        )

        assert long_position.size == Decimal('0')
        assert long_position.is_open is False
        assert pnl == Decimal('100')  # (51000-50000) * 0.1

    def test_position_value(self, long_position):
        """Test position value calculation."""
        long_position.update_price(Decimal('52000'))
        assert long_position.position_value == Decimal('5200')  # 0.1 * 52000

    def test_take_profit_trigger_long(self, long_position):
        """Test take profit trigger for long position."""
        long_position.take_profit = Decimal('55000')
        long_position.update_price(Decimal('56000'))

        assert long_position.should_take_profit() is True

    def test_stop_loss_trigger_long(self, long_position):
        """Test stop loss trigger for long position."""
        long_position.stop_loss = Decimal('48000')
        long_position.update_price(Decimal('47000'))

        assert long_position.should_stop_loss() is True

    def test_risk_reward_ratio(self, long_position):
        """Test risk/reward ratio calculation."""
        long_position.take_profit = Decimal('55000')
        long_position.stop_loss = Decimal('48000')

        rr_ratio = long_position.risk_reward_ratio

        # Potential profit: 55000 - 50000 = 5000
        # Potential loss: 50000 - 48000 = 2000
        # R:R = 5000 / 2000 = 2.5
        assert rr_ratio == 2.5


class TestOrderModel:
    """Tests for Order model."""

    @pytest.fixture
    def market_order(self):
        """Create a market order for testing."""
        return Order(
            order_id='O001',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal('0.1'),
            remaining_quantity=Decimal('0.1'),
        )

    @pytest.fixture
    def limit_order(self):
        """Create a limit order for testing."""
        return Order(
            order_id='O002',
            symbol='ETH/USDT',
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal('1.0'),
            remaining_quantity=Decimal('1.0'),
            price=Decimal('3100'),
        )

    def test_order_creation(self, market_order):
        """Test basic order creation."""
        assert market_order.order_id == 'O001'
        assert market_order.order_type == OrderType.MARKET
        assert market_order.status == OrderStatus.PENDING
        assert market_order.is_active is True

    def test_update_fill(self, limit_order):
        """Test updating order with fill."""
        limit_order.update_fill(
            fill_quantity=Decimal('0.5'),
            fill_price=Decimal('3100'),
        )

        assert limit_order.filled_quantity == Decimal('0.5')
        assert limit_order.remaining_quantity == Decimal('0.5')
        assert limit_order.status == OrderStatus.PARTIALLY_FILLED
        assert limit_order.average_fill_price == Decimal('3100')

    def test_order_fully_filled(self, limit_order):
        """Test fully filled order."""
        limit_order.update_fill(
            fill_quantity=Decimal('1.0'),
            fill_price=Decimal('3100'),
        )

        assert limit_order.remaining_quantity == Decimal('0')
        assert limit_order.status == OrderStatus.FILLED
        assert limit_order.is_filled is True
        assert limit_order.is_active is False

    def test_fill_percentage(self, limit_order):
        """Test fill percentage calculation."""
        limit_order.update_fill(
            fill_quantity=Decimal('0.25'),
            fill_price=Decimal('3100'),
        )

        assert limit_order.fill_percentage == 25.0

    def test_average_fill_price_multiple_fills(self, limit_order):
        """Test average fill price with multiple fills."""
        # First fill at 3100
        limit_order.update_fill(
            fill_quantity=Decimal('0.5'),
            fill_price=Decimal('3100'),
        )

        # Second fill at 3150
        limit_order.update_fill(
            fill_quantity=Decimal('0.5'),
            fill_price=Decimal('3150'),
        )

        # Average should be weighted: (3100*0.5 + 3150*0.5) / 1.0 = 3125
        assert limit_order.average_fill_price == Decimal('3125')

    def test_order_time_in_force(self, limit_order):
        """Test time in force setting."""
        assert limit_order.time_in_force == TimeInForce.GTC

        limit_order.time_in_force = TimeInForce.IOC
        assert limit_order.time_in_force == TimeInForce.IOC


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
