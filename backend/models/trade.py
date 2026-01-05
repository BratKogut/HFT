"""Trade Model"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class TradeType(str, Enum):
    BUY = "buy"
    SELL = "sell"

class Trade(BaseModel):
    """Trade Model"""
    id: str = Field(default="")
    symbol: str
    type: TradeType
    price: float
    size: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    order_id: str
    pnl: Optional[float] = 0.0
    fees: Optional[float] = 0.0
    
    # Latency metrics (microseconds)
    signal_latency_us: Optional[float] = None
    execution_latency_us: Optional[float] = None
    total_latency_us: Optional[float] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
