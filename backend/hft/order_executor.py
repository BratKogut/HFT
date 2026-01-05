"""Order Executor - Execute trading orders"""

import uuid
from typing import Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.order import Order, OrderStatus
from models.trade import Trade, TradeType
from hft.latency_monitor import LatencyMonitor

class OrderExecutor:
    """Execute trading orders"""
    
    def __init__(self, db: AsyncIOMotorDatabase, latency_monitor: LatencyMonitor):
        self.db = db
        self.latency_monitor = latency_monitor
        self.pending_orders = {}
    
    async def place_order(self, order: Order) -> tuple[bool, Optional[str]]:
        """Place an order
        
        Returns: (success, error_message)
        """
        start_time = self.latency_monitor.start_timer()
        
        try:
            # Generate order ID if not present
            if not order.id:
                order.id = str(uuid.uuid4())
            
            # Set timestamp
            order.timestamp = datetime.utcnow()
            order.status = OrderStatus.PENDING
            
            # Save to database
            await self.db.orders.insert_one(order.dict())
            
            # Add to pending orders
            self.pending_orders[order.id] = order
            
            # Simulate order execution (in real system, this would connect to exchange)
            # For now, immediately fill the order
            await self._simulate_fill(order)
            
            # Record latency
            self.latency_monitor.record("execution", start_time)
            
            return True, None
            
        except Exception as e:
            print(f"❌ Error placing order: {e}")
            return False, str(e)
    
    async def _simulate_fill(self, order: Order):
        """Simulate order fill (for testing)"""
        # Mark order as filled
        order.status = OrderStatus.FILLED
        order.filled_size = order.size
        order.filled_at = datetime.utcnow()
        
        # Update in database
        await self.db.orders.update_one(
            {"id": order.id},
            {"$set": {"status": order.status.value, "filled_size": order.filled_size, "filled_at": order.filled_at}}
        )
        
        # Create trade
        trade = Trade(
            id=str(uuid.uuid4()),
            symbol=order.symbol,
            type=TradeType.BUY if order.side.value == "buy" else TradeType.SELL,
            price=order.price,
            size=order.size,
            order_id=order.id,
            timestamp=datetime.utcnow()
        )
        
        # Save trade
        await self.db.trades.insert_one(trade.dict())
        
        # Remove from pending
        if order.id in self.pending_orders:
            del self.pending_orders[order.id]
        
        print(f"✅ Order filled: {order.side.value} {order.size} {order.symbol} @ {order.price}")
    
    async def cancel_order(self, order_id: str) -> tuple[bool, Optional[str]]:
        """Cancel an order"""
        if order_id not in self.pending_orders:
            return False, "Order not found or already filled"
        
        order = self.pending_orders[order_id]
        order.status = OrderStatus.CANCELLED
        
        # Update in database
        await self.db.orders.update_one(
            {"id": order_id},
            {"$set": {"status": order.status.value}}
        )
        
        del self.pending_orders[order_id]
        
        print(f"❌ Order cancelled: {order_id}")
        return True, None
    
    def get_pending_orders(self):
        """Get all pending orders"""
        return list(self.pending_orders.values())
