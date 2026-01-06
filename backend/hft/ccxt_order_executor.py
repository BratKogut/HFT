"""
CCXT Order Executor - Real Exchange Order Placement

Features:
- Place market/limit orders on real exchanges
- Order tracking and status updates
- Fill monitoring
- Position management
- Paper trading mode (simulate without real orders)
"""

import asyncio
import ccxt.async_support as ccxt
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum
import uuid


class OrderSide(str, Enum):
    BUY = 'buy'
    SELL = 'sell'


class OrderType(str, Enum):
    MARKET = 'market'
    LIMIT = 'limit'


class OrderStatus(str, Enum):
    PENDING = 'pending'
    OPEN = 'open'
    FILLED = 'filled'
    PARTIALLY_FILLED = 'partially_filled'
    CANCELLED = 'cancelled'
    REJECTED = 'rejected'


class CCXTOrderExecutor:
    """
    Order executor using CCXT for real exchange connectivity
    
    Supports:
    - Market and limit orders
    - Order tracking
    - Fill monitoring
    - Paper trading mode
    """
    
    def __init__(self,
                 exchange_name: str,
                 api_key: str,
                 api_secret: str,
                 testnet: bool = True,
                 paper_trading: bool = True):
        """
        Initialize order executor
        
        Args:
            exchange_name: 'binance', 'kraken', or 'okx'
            api_key: API key
            api_secret: API secret
            testnet: Use testnet if True
            paper_trading: If True, simulate orders without placing them
        """
        self.exchange_name = exchange_name.lower()
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.paper_trading = paper_trading
        
        # Exchange instance
        self.exchange: Optional[ccxt.Exchange] = None
        
        # Order tracking
        self.orders: Dict[str, Dict] = {}  # order_id -> order_data
        self.open_orders: Dict[str, Dict] = {}
        
        # Statistics
        self.total_orders = 0
        self.filled_orders = 0
        self.cancelled_orders = 0
        self.rejected_orders = 0
        self.total_volume = 0.0
        self.total_fees = 0.0
        
    async def initialize(self):
        """Initialize exchange connection"""
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
            
            config = {
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                }
            }
            
            # Testnet configuration
            if self.testnet:
                if self.exchange_name == 'binance':
                    config['urls'] = {
                        'api': {
                            'public': 'https://testnet.binance.vision/api',
                            'private': 'https://testnet.binance.vision/api',
                        }
                    }
            
            self.exchange = exchange_class(config)
            await self.exchange.load_markets()
            
            # Test authentication (if not paper trading)
            if not self.paper_trading:
                try:
                    balance = await self.exchange.fetch_balance()
                    print(f"✅ Authenticated with {self.exchange_name.upper()}")
                    print(f"   Account balance loaded")
                except Exception as e:
                    print(f"⚠️  Authentication test failed: {e}")
                    print(f"   Switching to paper trading mode")
                    self.paper_trading = True
            
            mode = "PAPER TRADING" if self.paper_trading else "LIVE TRADING"
            print(f"✅ Order executor initialized ({mode})")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize executor: {e}")
            return False
    
    async def place_order(self,
                         symbol: str,
                         side: OrderSide,
                         order_type: OrderType,
                         size: float,
                         price: Optional[float] = None,
                         params: Optional[Dict] = None) -> Dict:
        """
        Place an order
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            order_type: 'market' or 'limit'
            size: Order size in base currency
            price: Limit price (required for limit orders)
            params: Additional exchange-specific parameters
        
        Returns:
            {
                'success': bool,
                'order_id': str,
                'order': dict,  # Full order details
                'error': str  # If success=False
            }
        """
        if not self.exchange:
            await self.initialize()
        
        # Validate
        if order_type == OrderType.LIMIT and price is None:
            return {'success': False, 'error': 'Price required for limit orders'}
        
        # Generate order ID
        order_id = str(uuid.uuid4())
        
        try:
            if self.paper_trading:
                # Simulate order
                order = await self._simulate_order(
                    order_id, symbol, side, order_type, size, price
                )
            else:
                # Place real order
                if order_type == OrderType.MARKET:
                    order = await self.exchange.create_market_order(
                        symbol, side.value, size, params
                    )
                else:  # LIMIT
                    order = await self.exchange.create_limit_order(
                        symbol, side.value, size, price, params
                    )
                
                order_id = order['id']
            
            # Store order
            self.orders[order_id] = order
            if order['status'] in ['open', 'pending']:
                self.open_orders[order_id] = order
            
            self.total_orders += 1
            
            print(f"✅ Order placed: {side.value.upper()} {size} {symbol} "
                  f"@ {price if price else 'MARKET'} | ID: {order_id[:8]}")
            
            return {
                'success': True,
                'order_id': order_id,
                'order': order
            }
            
        except ccxt.InsufficientFunds as e:
            self.rejected_orders += 1
            error_msg = f"Insufficient funds: {e}"
            print(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}
            
        except ccxt.InvalidOrder as e:
            self.rejected_orders += 1
            error_msg = f"Invalid order: {e}"
            print(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}
            
        except Exception as e:
            self.rejected_orders += 1
            error_msg = f"Order placement failed: {e}"
            print(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}
    
    async def _simulate_order(self,
                             order_id: str,
                             symbol: str,
                             side: OrderSide,
                             order_type: OrderType,
                             size: float,
                             price: Optional[float]) -> Dict:
        """Simulate order for paper trading"""
        
        # Get current market price
        ticker = await self.exchange.fetch_ticker(symbol)
        market_price = ticker['last']
        
        # Determine fill price
        if order_type == OrderType.MARKET:
            # Market orders fill at current price (with slippage)
            slippage = 0.0001  # 0.01%
            fill_price = market_price * (1 + slippage if side == OrderSide.BUY else 1 - slippage)
        else:
            # Limit orders
            fill_price = price
        
        # Simulate order
        order = {
            'id': order_id,
            'symbol': symbol,
            'type': order_type.value,
            'side': side.value,
            'price': fill_price,
            'amount': size,
            'filled': size if order_type == OrderType.MARKET else 0,
            'remaining': 0 if order_type == OrderType.MARKET else size,
            'status': 'filled' if order_type == OrderType.MARKET else 'open',
            'timestamp': int(datetime.utcnow().timestamp() * 1000),
            'datetime': datetime.utcnow().isoformat(),
            'fee': {
                'cost': size * fill_price * 0.0002,  # 0.02% fee
                'currency': symbol.split('/')[1]
            },
            'info': {'simulated': True}
        }
        
        # Update statistics
        if order['status'] == 'filled':
            self.filled_orders += 1
            self.total_volume += size * fill_price
            self.total_fees += order['fee']['cost']
        
        return order
    
    async def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """
        Cancel an open order
        
        Returns:
            {'success': bool, 'error': str}
        """
        if order_id not in self.open_orders:
            return {'success': False, 'error': 'Order not found or already closed'}
        
        try:
            if self.paper_trading:
                # Simulate cancellation
                order = self.open_orders[order_id]
                order['status'] = 'cancelled'
            else:
                # Cancel real order
                await self.exchange.cancel_order(order_id, symbol)
            
            # Remove from open orders
            del self.open_orders[order_id]
            self.cancelled_orders += 1
            
            print(f"✅ Order cancelled: {order_id[:8]}")
            return {'success': True}
            
        except Exception as e:
            error_msg = f"Failed to cancel order: {e}"
            print(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}
    
    async def get_order_status(self, order_id: str, symbol: str) -> Optional[Dict]:
        """Get current order status"""
        if order_id in self.orders:
            order = self.orders[order_id]
            
            # If paper trading or order is closed, return cached
            if self.paper_trading or order['status'] in ['filled', 'cancelled', 'rejected']:
                return order
            
            # Fetch latest status from exchange
            try:
                updated_order = await self.exchange.fetch_order(order_id, symbol)
                self.orders[order_id] = updated_order
                
                # Update open orders
                if updated_order['status'] in ['filled', 'cancelled']:
                    if order_id in self.open_orders:
                        del self.open_orders[order_id]
                    
                    if updated_order['status'] == 'filled':
                        self.filled_orders += 1
                
                return updated_order
                
            except Exception as e:
                print(f"⚠️  Failed to fetch order status: {e}")
                return order
        
        return None
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open orders"""
        if not self.paper_trading and self.exchange:
            try:
                orders = await self.exchange.fetch_open_orders(symbol)
                return orders
            except Exception as e:
                print(f"⚠️  Failed to fetch open orders: {e}")
        
        # Return cached open orders
        if symbol:
            return [o for o in self.open_orders.values() if o['symbol'] == symbol]
        return list(self.open_orders.values())
    
    async def get_balance(self) -> Dict:
        """Get account balance"""
        if not self.exchange:
            await self.initialize()
        
        if self.paper_trading:
            # Return simulated balance
            return {
                'USDT': {'free': 10000.0, 'used': 0.0, 'total': 10000.0},
                'BTC': {'free': 0.0, 'used': 0.0, 'total': 0.0}
            }
        
        try:
            balance = await self.exchange.fetch_balance()
            return balance
        except Exception as e:
            print(f"❌ Failed to fetch balance: {e}")
            return {}
    
    async def close(self):
        """Close exchange connection"""
        if self.exchange:
            await self.exchange.close()
    
    def get_stats(self) -> Dict:
        """Get executor statistics"""
        return {
            'exchange': self.exchange_name,
            'paper_trading': self.paper_trading,
            'testnet': self.testnet,
            'total_orders': self.total_orders,
            'filled_orders': self.filled_orders,
            'cancelled_orders': self.cancelled_orders,
            'rejected_orders': self.rejected_orders,
            'open_orders': len(self.open_orders),
            'total_volume': self.total_volume,
            'total_fees': self.total_fees
        }


# Example usage
async def example_usage():
    """Example of how to use CCXTOrderExecutor"""
    
    # Create executor (paper trading mode)
    executor = CCXTOrderExecutor(
        exchange_name='binance',
        api_key='your_api_key',
        api_secret='your_api_secret',
        testnet=True,
        paper_trading=True  # Safe mode - no real orders
    )
    
    await executor.initialize()
    
    # Place a limit buy order
    result = await executor.place_order(
        symbol='BTC/USDT',
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        size=0.001,
        price=45000.0
    )
    
    if result['success']:
        print(f"Order placed: {result['order_id']}")
        
        # Check order status
        await asyncio.sleep(1)
        status = await executor.get_order_status(result['order_id'], 'BTC/USDT')
        print(f"Order status: {status['status']}")
    
    # Get statistics
    print("\nStatistics:", executor.get_stats())
    
    await executor.close()


if __name__ == "__main__":
    asyncio.run(example_usage())
