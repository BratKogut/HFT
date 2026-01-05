"""Order Model"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class Order(BaseModel):
    """Order Model"""
    id: str = Field(default="")
    symbol: str
    type: OrderType
    side: OrderSide
    price: float
    size: float
    filled_size: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    
    # Strategy info
    strategy: str = "market_making"
    signal_strength: Optional[float] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
