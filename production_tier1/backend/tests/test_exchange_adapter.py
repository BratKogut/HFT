"""
Unit Tests for Exchange Adapter
"""

import asyncio
import pytest
from decimal import Decimal
from datetime import datetime

import sys
sys.path.insert(0, '..')

from exchange.exchange_adapter import (
    SimulatedExchangeAdapter,
    CCXTExchangeAdapter,
    create_exchange_adapter,
    OrderRequest,
    OrderSide,
    OrderType,
    ConnectionState,
    SUPPORTED_EXCHANGES,
)


@pytest.fixture
def simulated_adapter():
    """Create simulated adapter for testing."""
    return SimulatedExchangeAdapter(
        initial_balance={'USDT': Decimal('10000'), 'BTC': Decimal('0.5')},
        slippage_pct=0.0005,
        latency_ms=1,
    )


class TestSimulatedExchangeAdapter:
    """Tests for simulated exchange adapter."""

    @pytest.mark.asyncio
    async def test_connect(self, simulated_adapter):
        """Test connection."""
        result = await simulated_adapter.connect()
        assert result is True
        assert simulated_adapter.state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_disconnect(self, simulated_adapter):
        """Test disconnection."""
        await simulated_adapter.connect()
        await simulated_adapter.disconnect()
        assert simulated_adapter.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_get_ticker(self, simulated_adapter):
        """Test getting ticker data."""
        await simulated_adapter.connect()
        ticker = await simulated_adapter.get_ticker("BTC/USDT")

        assert ticker is not None
        assert ticker.symbol == "BTC/USDT"
        assert ticker.bid > 0
        assert ticker.ask > 0
        assert ticker.last > 0
        assert ticker.bid < ticker.ask  # Bid always less than ask

    @pytest.mark.asyncio
    async def test_get_orderbook(self, simulated_adapter):
        """Test getting order book."""
        await simulated_adapter.connect()
        orderbook = await simulated_adapter.get_orderbook("BTC/USDT", limit=5)

        assert orderbook is not None
        assert orderbook.symbol == "BTC/USDT"
        assert len(orderbook.bids) == 5
        assert len(orderbook.asks) == 5

    @pytest.mark.asyncio
    async def test_get_balance(self, simulated_adapter):
        """Test getting balance."""
        await simulated_adapter.connect()

        usdt = await simulated_adapter.get_balance("USDT")
        btc = await simulated_adapter.get_balance("BTC")

        assert usdt == Decimal("10000")
        assert btc == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_market_buy_order(self, simulated_adapter):
        """Test market buy order."""
        await simulated_adapter.connect()

        order = OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.1"),
        )

        result = await simulated_adapter.place_order(order)

        assert result.success is True
        assert result.filled_quantity == Decimal("0.1")
        assert result.filled_price is not None
        assert result.status == "filled"

        # Check balances updated
        btc = await simulated_adapter.get_balance("BTC")
        assert btc == Decimal("0.6")  # 0.5 + 0.1

    @pytest.mark.asyncio
    async def test_market_sell_order(self, simulated_adapter):
        """Test market sell order."""
        await simulated_adapter.connect()

        order = OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.1"),
        )

        result = await simulated_adapter.place_order(order)

        assert result.success is True
        assert result.filled_quantity == Decimal("0.1")

        # Check balances updated
        btc = await simulated_adapter.get_balance("BTC")
        assert btc == Decimal("0.4")  # 0.5 - 0.1

    @pytest.mark.asyncio
    async def test_insufficient_balance_buy(self, simulated_adapter):
        """Test buy order with insufficient balance."""
        await simulated_adapter.connect()

        order = OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1000"),  # Way too much
        )

        result = await simulated_adapter.place_order(order)

        assert result.success is False
        assert "Insufficient" in result.error_message

    @pytest.mark.asyncio
    async def test_insufficient_balance_sell(self, simulated_adapter):
        """Test sell order with insufficient balance."""
        await simulated_adapter.connect()

        order = OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),  # More than 0.5 BTC
        )

        result = await simulated_adapter.place_order(order)

        assert result.success is False
        assert "Insufficient" in result.error_message

    @pytest.mark.asyncio
    async def test_unknown_symbol(self, simulated_adapter):
        """Test order with unknown symbol."""
        await simulated_adapter.connect()

        order = OrderRequest(
            symbol="UNKNOWN/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1.0"),
        )

        result = await simulated_adapter.place_order(order)

        assert result.success is False
        assert "Unknown symbol" in result.error_message

    @pytest.mark.asyncio
    async def test_set_price(self, simulated_adapter):
        """Test setting simulated price."""
        await simulated_adapter.connect()

        simulated_adapter.set_price("BTC/USDT", Decimal("100000"))

        ticker = await simulated_adapter.get_ticker("BTC/USDT")
        assert ticker.last == Decimal("100000")


class TestExchangeValidation:
    """Tests for exchange validation."""

    def test_supported_exchanges(self):
        """Test that common exchanges are supported."""
        assert "binance" in SUPPORTED_EXCHANGES
        assert "kraken" in SUPPORTED_EXCHANGES
        assert "coinbase" in SUPPORTED_EXCHANGES
        assert "bybit" in SUPPORTED_EXCHANGES

    def test_unsupported_exchange_not_in_list(self):
        """Test that fake exchanges are not supported."""
        assert "fakeexchange" not in SUPPORTED_EXCHANGES
        assert "hackexchange" not in SUPPORTED_EXCHANGES


class TestFactoryFunction:
    """Tests for create_exchange_adapter factory."""

    def test_create_simulated(self):
        """Test creating simulated adapter."""
        adapter = create_exchange_adapter(simulated=True)
        assert isinstance(adapter, SimulatedExchangeAdapter)

    def test_create_ccxt(self):
        """Test creating CCXT adapter."""
        adapter = create_exchange_adapter(
            exchange_id="binance",
            sandbox=True,
            simulated=False,
        )
        assert isinstance(adapter, CCXTExchangeAdapter)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
