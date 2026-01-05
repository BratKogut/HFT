"""
Order Model
===========

Pydantic model for trading orders.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from decimal import Decimal


class OrderSide(str, Enum):
    """Order side enum."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type enum."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LOSS_LIMIT = "stop_loss_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"


class OrderStatus(str, Enum):
    """Order status enum."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(str, Enum):
    """Time in force enum."""
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill
    GTD = "GTD"  # Good Till Date


class Order(BaseModel):
    """
    Order model representing a trading order.
    
    Attributes:
        order_id: Unique order identifier
        client_order_id: Client-side order ID
        exchange_order_id: Exchange-assigned order ID
        symbol: Trading pair (e.g., "BTCUSDT")
        side: Order side (buy/sell)
        order_type: Order type (market/limit/etc.)
        quantity: Order quantity
        price: Order price (None for market orders)
        stop_price: Stop price for stop orders
        time_in_force: Time in force
        status: Current order status
        filled_quantity: Quantity filled so far
        remaining_quantity: Quantity remaining to be filled
        average_fill_price: Average price of fills
        commission: Trading commission paid
        commission_asset: Asset in which commission is paid
        created_at: Order creation timestamp
        updated_at: Last update timestamp
        filled_at: Order fill timestamp
        metadata: Additional metadata
    """
    
    order_id: str = Field(..., description="Unique order identifier")
    client_order_id: Optional[str] = Field(None, description="Client-side order ID")
    exchange_order_id: Optional[str] = Field(None, description="Exchange-assigned order ID")
    
    symbol: str = Field(..., description="Trading pair")
    side: OrderSide = Field(..., description="Order side")
    order_type: OrderType = Field(..., description="Order type")
    
    quantity: Decimal = Field(..., gt=0, description="Order quantity")
    price: Optional[Decimal] = Field(None, gt=0, description="Order price")
    stop_price: Optional[Decimal] = Field(None, gt=0, description="Stop price")
    
    time_in_force: TimeInForce = Field(TimeInForce.GTC, description="Time in force")
    status: OrderStatus = Field(OrderStatus.PENDING, description="Order status")
    
    filled_quantity: Decimal = Field(Decimal("0"), ge=0, description="Filled quantity")
    remaining_quantity: Decimal = Field(..., ge=0, description="Remaining quantity")
    average_fill_price: Optional[Decimal] = Field(None, description="Average fill price")
    
    commission: Decimal = Field(Decimal("0"), ge=0, description="Commission paid")
    commission_asset: Optional[str] = Field(None, description="Commission asset")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Update timestamp")
    filled_at: Optional[datetime] = Field(None, description="Fill timestamp")
    
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }
    
    def update_fill(self, fill_quantity: Decimal, fill_price: Decimal):
        """Update order with new fill information."""
        self.filled_quantity += fill_quantity
        self.remaining_quantity = self.quantity - self.filled_quantity
        
        # Update average fill price
        if self.average_fill_price is None:
            self.average_fill_price = fill_price
        else:
            total_value = (self.average_fill_price * (self.filled_quantity - fill_quantity) + 
                          fill_price * fill_quantity)
            self.average_fill_price = total_value / self.filled_quantity
        
        # Update status
        if self.remaining_quantity == 0:
            self.status = OrderStatus.FILLED
            self.filled_at = datetime.utcnow()
        elif self.filled_quantity > 0:
            self.status = OrderStatus.PARTIALLY_FILLED
        
        self.updated_at = datetime.utcnow()
    
    @property
    def is_active(self) -> bool:
        """Check if order is still active."""
        return self.status in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]
    
    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.status == OrderStatus.FILLED
    
    @property
    def fill_percentage(self) -> float:
        """Calculate fill percentage."""
        if self.quantity == 0:
            return 0.0
        return float(self.filled_quantity / self.quantity * 100)
