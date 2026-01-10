"""Position Model"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Position(BaseModel):
    """Position Model"""
    id: str = Field(default="")
    symbol: str
    size: float = 0.0  # Positive = long, Negative = short
    entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    def update_pnl(self, current_price: float):
        """Update unrealized PnL"""
        self.current_price = current_price
        if self.size != 0:
            self.unrealized_pnl = (current_price - self.entry_price) * self.size
        self.last_updated = datetime.utcnow()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
