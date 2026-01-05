"""
HFT MVP Tier 1 - Order Execution
Order execution with support for paper, shadow, and live trading
"""

from typing import Dict, Optional, Literal
from datetime import datetime
import ccxt
import logging

logger = logging.getLogger(__name__)


class Order:
    """Trading order"""
    
    def __init__(
        self,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        order_type: str,  # 'market' or 'limit'
        size: float,
        price: Optional[float] = None,
        timestamp: Optional[datetime] = None
    ):
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.size = size
        self.price = price
        self.timestamp = timestamp or datetime.utcnow()
        self.status = 'pending'  # pending, filled, cancelled, failed
        self.filled_price = None
        self.exchange_order_id = None
    
    def to_dict(self) -> Dict:
        """Convert order to dictionary"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'order_type': self.order_type,
            'size': self.size,
            'price': self.price,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status,
            'filled_price': self.filled_price,
            'exchange_order_id': self.exchange_order_id
        }


class OrderExecutor:
    """Order execution engine"""
    
    def __init__(
        self,
        exchange_name: str,
        api_key: str,
        api_secret: str,
        mode: Literal['paper', 'shadow', 'live'] = 'paper'
    ):
        """
        Initialize order executor
        
        Args:
            exchange_name: Exchange name (e.g., 'binance')
            api_key: API key
            api_secret: API secret
            mode: Trading mode
                - paper: Simulated trading (no real orders)
                - shadow: Real market data, simulated orders
                - live: Real trading
        """
        self.exchange_name = exchange_name
        self.mode = mode
        
        # Initialize exchange
        exchange_class = getattr(ccxt, exchange_name)
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        
        # Order history
        self.order_history = []
        
        # Paper trading state
        self.paper_balance = {}
        
        logger.info(f"OrderExecutor initialized for {exchange_name} in {mode} mode")
    
    async def execute_order(
        self,
        symbol: str,
        side: str,
        size: float,
        order_type: str = 'market',
        price: Optional[float] = None
    ) -> Order:
        """
        Execute trading order
        
        Args:
            symbol: Trading symbol (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            size: Order size
            order_type: 'market' or 'limit'
            price: Limit price (required for limit orders)
            
        Returns:
            Order object
        """
        order = Order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            size=size,
            price=price
        )
        
        try:
            if self.mode == 'paper':
                # Paper trading: simulate order
                await self._execute_paper_order(order)
            
            elif self.mode == 'shadow':
                # Shadow trading: log order but don't execute
                await self._execute_shadow_order(order)
            
            elif self.mode == 'live':
                # Live trading: execute real order
                await self._execute_live_order(order)
            
            else:
                raise ValueError(f"Invalid trading mode: {self.mode}")
            
            # Record order
            self.order_history.append(order)
            
            return order
            
        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            order.status = 'failed'
            return order
    
    async def _execute_paper_order(self, order: Order):
        """Execute paper trading order"""
        # Get current market price
        ticker = await self.exchange.fetch_ticker(order.symbol)
        market_price = ticker['last']
        
        # Simulate fill
        if order.order_type == 'market':
            order.filled_price = market_price
            order.status = 'filled'
        elif order.order_type == 'limit':
            # For simplicity, assume limit orders fill immediately if price is good
            if order.side == 'buy' and order.price >= market_price:
                order.filled_price = order.price
                order.status = 'filled'
            elif order.side == 'sell' and order.price <= market_price:
                order.filled_price = order.price
                order.status = 'filled'
            else:
                order.status = 'pending'
        
        logger.info(f"[PAPER] {order.side.upper()} {order.size} {order.symbol} @ ${order.filled_price}")
    
    async def _execute_shadow_order(self, order: Order):
        """Execute shadow trading order"""
        # Get current market price
        ticker = await self.exchange.fetch_ticker(order.symbol)
        market_price = ticker['last']
        
        # Log order but don't execute
        order.filled_price = market_price
        order.status = 'filled'
        
        logger.info(f"[SHADOW] {order.side.upper()} {order.size} {order.symbol} @ ${order.filled_price}")
    
    async def _execute_live_order(self, order: Order):
        """Execute live trading order"""
        # Execute real order on exchange
        if order.order_type == 'market':
            result = await self.exchange.create_market_order(
                symbol=order.symbol,
                side=order.side,
                amount=order.size
            )
        elif order.order_type == 'limit':
            result = await self.exchange.create_limit_order(
                symbol=order.symbol,
                side=order.side,
                amount=order.size,
                price=order.price
            )
        else:
            raise ValueError(f"Invalid order type: {order.order_type}")
        
        # Update order with exchange response
        order.exchange_order_id = result['id']
        order.filled_price = result.get('price', result.get('average'))
        order.status = result['status']
        
        logger.info(f"[LIVE] {order.side.upper()} {order.size} {order.symbol} @ ${order.filled_price} (ID: {order.exchange_order_id})")
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an order
        
        Args:
            order_id: Exchange order ID
            symbol: Trading symbol
            
        Returns:
            True if cancelled successfully
        """
        if self.mode != 'live':
            logger.info(f"[{self.mode.upper()}] Cancel order {order_id} (simulated)")
            return True
        
        try:
            await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"[LIVE] Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def get_balance(self, currency: str = 'USDT') -> float:
        """
        Get account balance
        
        Args:
            currency: Currency to check
            
        Returns:
            Balance amount
        """
        if self.mode == 'paper':
            return self.paper_balance.get(currency, 10000.0)
        
        try:
            balance = await self.exchange.fetch_balance()
            return balance[currency]['free']
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return 0.0
    
    def get_order_history(self, limit: int = 100) -> list:
        """
        Get order history
        
        Args:
            limit: Maximum number of orders to return
            
        Returns:
            List of orders
        """
        return [o.to_dict() for o in self.order_history[-limit:]]
    
    def get_stats(self) -> Dict:
        """Get execution statistics"""
        total_orders = len(self.order_history)
        filled_orders = sum(1 for o in self.order_history if o.status == 'filled')
        failed_orders = sum(1 for o in self.order_history if o.status == 'failed')
        
        return {
            'mode': self.mode,
            'exchange': self.exchange_name,
            'total_orders': total_orders,
            'filled_orders': filled_orders,
            'failed_orders': failed_orders,
            'fill_rate': (filled_orders / total_orders * 100) if total_orders > 0 else 0
        }
