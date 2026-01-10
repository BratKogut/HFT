"""
Production Exchange Adapter
===========================

Provides unified interface for connecting to cryptocurrency exchanges.
Supports both real exchanges (via CCXT) and simulation mode.

Features:
- Thread-safe connection management
- Rate limiting and retry logic
- Order execution with timeout
- Real-time WebSocket data feeds
- Health monitoring
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
import ccxt.async_support as ccxt

logger = logging.getLogger(__name__)


# Whitelist of supported exchanges for security
SUPPORTED_EXCHANGES = frozenset({
    'binance', 'binanceus', 'binancecoinm', 'binanceusdm',
    'kraken', 'krakenfutures',
    'coinbase', 'coinbasepro',
    'kucoin', 'kucoinfutures',
    'bybit', 'bybitspot',
    'okx', 'gate',
})


class ConnectionState(Enum):
    """Exchange connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class OrderRequest:
    """Order request data."""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    client_order_id: Optional[str] = None
    time_in_force: str = "GTC"


@dataclass
class OrderResult:
    """Order execution result."""
    success: bool
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    filled_quantity: Decimal = Decimal("0")
    filled_price: Optional[Decimal] = None
    status: str = "unknown"
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Ticker:
    """Market ticker data."""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume_24h: Decimal
    high_24h: Decimal
    low_24h: Decimal
    timestamp: datetime


@dataclass
class OrderBookLevel:
    """Order book level."""
    price: Decimal
    quantity: Decimal


@dataclass
class OrderBook:
    """Order book snapshot."""
    symbol: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: datetime


class ExchangeAdapter(ABC):
    """Abstract base class for exchange adapters."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to exchange."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from exchange."""
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """Get ticker for symbol."""
        pass

    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 10) -> Optional[OrderBook]:
        """Get order book for symbol."""
        pass

    @abstractmethod
    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Place order."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel order."""
        pass

    @abstractmethod
    async def get_balance(self, asset: str) -> Decimal:
        """Get balance for asset."""
        pass


class CCXTExchangeAdapter(ExchangeAdapter):
    """
    Production exchange adapter using CCXT library.

    Features:
    - Support for multiple exchanges
    - Automatic rate limiting
    - Connection retry with exponential backoff
    - Order execution with timeout
    """

    def __init__(
        self,
        exchange_id: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sandbox: bool = True,
        timeout: int = 30000,
        max_retries: int = 3,
    ):
        """
        Initialize CCXT exchange adapter.

        Args:
            exchange_id: Exchange identifier (e.g., 'binance')
            api_key: API key (None for public-only access)
            api_secret: API secret
            sandbox: Use sandbox/testnet mode
            timeout: Request timeout in milliseconds
            max_retries: Maximum retry attempts
        """
        self.exchange_id = exchange_id.lower()
        self.api_key = api_key
        self.api_secret = api_secret
        self.sandbox = sandbox
        self.timeout = timeout
        self.max_retries = max_retries

        self.exchange: Optional[ccxt.Exchange] = None
        self.state = ConnectionState.DISCONNECTED
        self._lock = asyncio.Lock()

        # Callbacks
        self._ticker_callbacks: List[Callable[[Ticker], Any]] = []
        self._orderbook_callbacks: List[Callable[[OrderBook], Any]] = []

        # Statistics
        self.total_requests = 0
        self.failed_requests = 0
        self.total_orders = 0
        self.filled_orders = 0

    async def connect(self) -> bool:
        """Connect to exchange with validation and retry logic."""
        async with self._lock:
            if self.state == ConnectionState.CONNECTED:
                return True

            self.state = ConnectionState.CONNECTING

            # Validate exchange ID
            if self.exchange_id not in SUPPORTED_EXCHANGES:
                logger.error(f"Unsupported exchange: {self.exchange_id}")
                self.state = ConnectionState.ERROR
                return False

            if not hasattr(ccxt, self.exchange_id):
                logger.error(f"Exchange not found in CCXT: {self.exchange_id}")
                self.state = ConnectionState.ERROR
                return False

            try:
                # Create exchange instance
                exchange_class = getattr(ccxt, self.exchange_id)

                config = {
                    'enableRateLimit': True,
                    'timeout': self.timeout,
                    'options': {
                        'defaultType': 'spot',
                        'adjustForTimeDifference': True,
                    }
                }

                if self.api_key and self.api_secret:
                    config['apiKey'] = self.api_key
                    config['secret'] = self.api_secret

                self.exchange = exchange_class(config)

                # Enable sandbox mode if requested
                if self.sandbox:
                    self.exchange.set_sandbox_mode(True)

                # Load markets with retry
                for attempt in range(self.max_retries):
                    try:
                        await asyncio.wait_for(
                            self.exchange.load_markets(),
                            timeout=self.timeout / 1000
                        )
                        break
                    except asyncio.TimeoutError:
                        if attempt == self.max_retries - 1:
                            raise
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff

                self.state = ConnectionState.CONNECTED
                logger.info(f"Connected to {self.exchange_id.upper()} (sandbox={self.sandbox})")
                return True

            except Exception as e:
                logger.error(f"Failed to connect to {self.exchange_id}: {e}")
                self.state = ConnectionState.ERROR
                return False

    async def disconnect(self) -> None:
        """Disconnect from exchange."""
        async with self._lock:
            if self.exchange:
                try:
                    await self.exchange.close()
                except Exception as e:
                    logger.warning(f"Error during disconnect: {e}")
                finally:
                    self.exchange = None
                    self.state = ConnectionState.DISCONNECTED
                    logger.info(f"Disconnected from {self.exchange_id}")

    async def _ensure_connected(self) -> bool:
        """Ensure connection is active."""
        if self.state != ConnectionState.CONNECTED:
            return await self.connect()
        return True

    async def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """Get ticker with retry logic."""
        if not await self._ensure_connected():
            return None

        self.total_requests += 1

        for attempt in range(self.max_retries):
            try:
                data = await asyncio.wait_for(
                    self.exchange.fetch_ticker(symbol),
                    timeout=self.timeout / 1000
                )

                return Ticker(
                    symbol=symbol,
                    bid=Decimal(str(data.get('bid', 0) or 0)),
                    ask=Decimal(str(data.get('ask', 0) or 0)),
                    last=Decimal(str(data.get('last', 0) or 0)),
                    volume_24h=Decimal(str(data.get('quoteVolume', 0) or 0)),
                    high_24h=Decimal(str(data.get('high', 0) or 0)),
                    low_24h=Decimal(str(data.get('low', 0) or 0)),
                    timestamp=datetime.utcnow()
                )

            except asyncio.TimeoutError:
                logger.warning(f"Ticker request timeout (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Error fetching ticker: {e}")
                self.failed_requests += 1
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        return None

    async def get_orderbook(self, symbol: str, limit: int = 10) -> Optional[OrderBook]:
        """Get order book with retry logic."""
        if not await self._ensure_connected():
            return None

        self.total_requests += 1

        for attempt in range(self.max_retries):
            try:
                data = await asyncio.wait_for(
                    self.exchange.fetch_order_book(symbol, limit),
                    timeout=self.timeout / 1000
                )

                bids = [
                    OrderBookLevel(Decimal(str(p)), Decimal(str(q)))
                    for p, q in data.get('bids', [])[:limit]
                ]
                asks = [
                    OrderBookLevel(Decimal(str(p)), Decimal(str(q)))
                    for p, q in data.get('asks', [])[:limit]
                ]

                return OrderBook(
                    symbol=symbol,
                    bids=bids,
                    asks=asks,
                    timestamp=datetime.utcnow()
                )

            except asyncio.TimeoutError:
                logger.warning(f"Order book request timeout (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Error fetching order book: {e}")
                self.failed_requests += 1
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        return None

    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Place order with timeout and error handling."""
        if not await self._ensure_connected():
            return OrderResult(
                success=False,
                error_message="Not connected to exchange"
            )

        self.total_requests += 1
        self.total_orders += 1

        try:
            # Prepare order parameters
            order_type = request.order_type.value
            side = request.side.value
            amount = float(request.quantity)
            price = float(request.price) if request.price else None

            params = {}
            if request.client_order_id:
                params['clientOrderId'] = request.client_order_id

            # Execute order with timeout
            if request.order_type == OrderType.MARKET:
                result = await asyncio.wait_for(
                    self.exchange.create_order(
                        request.symbol, 'market', side, amount, None, params
                    ),
                    timeout=self.timeout / 1000
                )
            elif request.order_type == OrderType.LIMIT:
                result = await asyncio.wait_for(
                    self.exchange.create_order(
                        request.symbol, 'limit', side, amount, price, params
                    ),
                    timeout=self.timeout / 1000
                )
            else:
                # Stop orders require additional parameters
                if request.stop_price:
                    params['stopPrice'] = float(request.stop_price)
                result = await asyncio.wait_for(
                    self.exchange.create_order(
                        request.symbol, order_type, side, amount, price, params
                    ),
                    timeout=self.timeout / 1000
                )

            # Parse result
            filled_qty = Decimal(str(result.get('filled', 0) or 0))
            avg_price = result.get('average') or result.get('price')

            if result.get('status') in ['closed', 'filled']:
                self.filled_orders += 1

            return OrderResult(
                success=True,
                order_id=result.get('id'),
                client_order_id=result.get('clientOrderId'),
                filled_quantity=filled_qty,
                filled_price=Decimal(str(avg_price)) if avg_price else None,
                status=result.get('status', 'unknown'),
            )

        except asyncio.TimeoutError:
            logger.error(f"Order execution timeout for {request.symbol}")
            self.failed_requests += 1
            return OrderResult(
                success=False,
                error_message="Order execution timeout"
            )
        except Exception as e:
            logger.error(f"Order execution error: {e}")
            self.failed_requests += 1
            return OrderResult(
                success=False,
                error_message=str(e)
            )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel order."""
        if not await self._ensure_connected():
            return False

        self.total_requests += 1

        try:
            await asyncio.wait_for(
                self.exchange.cancel_order(order_id, symbol),
                timeout=self.timeout / 1000
            )
            return True
        except asyncio.TimeoutError:
            logger.error(f"Cancel order timeout: {order_id}")
            return False
        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            self.failed_requests += 1
            return False

    async def get_balance(self, asset: str) -> Decimal:
        """Get balance for asset."""
        if not await self._ensure_connected():
            return Decimal("0")

        self.total_requests += 1

        try:
            balance = await asyncio.wait_for(
                self.exchange.fetch_balance(),
                timeout=self.timeout / 1000
            )

            if asset in balance:
                return Decimal(str(balance[asset].get('free', 0) or 0))
            return Decimal("0")

        except Exception as e:
            logger.error(f"Get balance error: {e}")
            self.failed_requests += 1
            return Decimal("0")

    def get_stats(self) -> Dict:
        """Get adapter statistics."""
        return {
            'exchange': self.exchange_id,
            'state': self.state.value,
            'sandbox': self.sandbox,
            'total_requests': self.total_requests,
            'failed_requests': self.failed_requests,
            'total_orders': self.total_orders,
            'filled_orders': self.filled_orders,
            'success_rate': (
                (self.total_requests - self.failed_requests) / self.total_requests * 100
                if self.total_requests > 0 else 0
            )
        }

    def register_ticker_callback(self, callback: Callable[[Ticker], Any]) -> None:
        """Register callback for ticker updates."""
        self._ticker_callbacks.append(callback)

    def register_orderbook_callback(self, callback: Callable[[OrderBook], Any]) -> None:
        """Register callback for order book updates."""
        self._orderbook_callbacks.append(callback)


class SimulatedExchangeAdapter(ExchangeAdapter):
    """
    Simulated exchange adapter for testing and paper trading.

    Provides realistic simulation of exchange behavior including:
    - Order book simulation
    - Slippage modeling
    - Latency simulation
    """

    def __init__(
        self,
        initial_balance: Dict[str, Decimal] = None,
        slippage_pct: float = 0.0005,
        latency_ms: int = 10,
    ):
        """
        Initialize simulated exchange adapter.

        Args:
            initial_balance: Initial balances (e.g., {'USDT': 10000, 'BTC': 0})
            slippage_pct: Simulated slippage percentage
            latency_ms: Simulated latency in milliseconds
        """
        self.balances = initial_balance or {'USDT': Decimal('10000')}
        self.slippage_pct = slippage_pct
        self.latency_ms = latency_ms

        self.state = ConnectionState.DISCONNECTED
        self.orders: Dict[str, Dict] = {}
        self._order_counter = 0

        # Simulated prices
        self._prices: Dict[str, Decimal] = {
            'BTC/USDT': Decimal('93000'),
            'ETH/USDT': Decimal('3400'),
            'SOL/USDT': Decimal('190'),
        }

    async def connect(self) -> bool:
        """Connect (simulated)."""
        await asyncio.sleep(self.latency_ms / 1000)
        self.state = ConnectionState.CONNECTED
        logger.info("Connected to simulated exchange")
        return True

    async def disconnect(self) -> None:
        """Disconnect (simulated)."""
        self.state = ConnectionState.DISCONNECTED
        logger.info("Disconnected from simulated exchange")

    async def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """Get simulated ticker."""
        await asyncio.sleep(self.latency_ms / 1000)

        if symbol not in self._prices:
            return None

        price = self._prices[symbol]
        spread = price * Decimal('0.0001')  # 0.01% spread

        return Ticker(
            symbol=symbol,
            bid=price - spread / 2,
            ask=price + spread / 2,
            last=price,
            volume_24h=Decimal('1000000'),
            high_24h=price * Decimal('1.02'),
            low_24h=price * Decimal('0.98'),
            timestamp=datetime.utcnow()
        )

    async def get_orderbook(self, symbol: str, limit: int = 10) -> Optional[OrderBook]:
        """Get simulated order book."""
        await asyncio.sleep(self.latency_ms / 1000)

        if symbol not in self._prices:
            return None

        price = self._prices[symbol]
        spread = price * Decimal('0.0001')

        bids = []
        asks = []

        for i in range(limit):
            bid_price = price - spread / 2 - Decimal(str(i)) * spread / 10
            ask_price = price + spread / 2 + Decimal(str(i)) * spread / 10

            bids.append(OrderBookLevel(bid_price, Decimal('1.0')))
            asks.append(OrderBookLevel(ask_price, Decimal('1.0')))

        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=datetime.utcnow()
        )

    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Execute simulated order."""
        await asyncio.sleep(self.latency_ms / 1000)

        self._order_counter += 1
        order_id = f"SIM-{self._order_counter}"

        # Get current price
        if request.symbol not in self._prices:
            return OrderResult(
                success=False,
                error_message=f"Unknown symbol: {request.symbol}"
            )

        price = self._prices[request.symbol]

        # Apply slippage
        if request.side == OrderSide.BUY:
            fill_price = price * (1 + Decimal(str(self.slippage_pct)))
        else:
            fill_price = price * (1 - Decimal(str(self.slippage_pct)))

        # Use limit price if specified
        if request.price:
            if request.side == OrderSide.BUY and request.price < price:
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    filled_quantity=Decimal('0'),
                    status='open',
                )
            elif request.side == OrderSide.SELL and request.price > price:
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    filled_quantity=Decimal('0'),
                    status='open',
                )
            fill_price = request.price

        # Update balances
        base, quote = request.symbol.split('/')
        trade_value = request.quantity * fill_price

        if request.side == OrderSide.BUY:
            if self.balances.get(quote, Decimal('0')) < trade_value:
                return OrderResult(
                    success=False,
                    error_message="Insufficient balance"
                )
            self.balances[quote] = self.balances.get(quote, Decimal('0')) - trade_value
            self.balances[base] = self.balances.get(base, Decimal('0')) + request.quantity
        else:
            if self.balances.get(base, Decimal('0')) < request.quantity:
                return OrderResult(
                    success=False,
                    error_message="Insufficient balance"
                )
            self.balances[base] = self.balances.get(base, Decimal('0')) - request.quantity
            self.balances[quote] = self.balances.get(quote, Decimal('0')) + trade_value

        return OrderResult(
            success=True,
            order_id=order_id,
            filled_quantity=request.quantity,
            filled_price=fill_price,
            status='filled',
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel simulated order."""
        await asyncio.sleep(self.latency_ms / 1000)
        if order_id in self.orders:
            del self.orders[order_id]
            return True
        return False

    async def get_balance(self, asset: str) -> Decimal:
        """Get simulated balance."""
        await asyncio.sleep(self.latency_ms / 1000)
        return self.balances.get(asset, Decimal('0'))

    def set_price(self, symbol: str, price: Decimal) -> None:
        """Set simulated price (for testing)."""
        self._prices[symbol] = price


def create_exchange_adapter(
    exchange_id: str = 'binance',
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    sandbox: bool = True,
    simulated: bool = False,
    **kwargs
) -> ExchangeAdapter:
    """
    Factory function to create exchange adapter.

    Args:
        exchange_id: Exchange identifier
        api_key: API key
        api_secret: API secret
        sandbox: Use sandbox/testnet mode
        simulated: Use simulated adapter
        **kwargs: Additional arguments

    Returns:
        Exchange adapter instance
    """
    if simulated:
        return SimulatedExchangeAdapter(**kwargs)

    return CCXTExchangeAdapter(
        exchange_id=exchange_id,
        api_key=api_key,
        api_secret=api_secret,
        sandbox=sandbox,
        **kwargs
    )
