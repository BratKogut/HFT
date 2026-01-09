"""
Trade Model
===========

Pydantic model for executed trades.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from decimal import Decimal


class TradeSide(str, Enum):
    """Trade side enum."""
    BUY = "buy"
    SELL = "sell"


class TradeStatus(str, Enum):
    """Trade status enum."""
    PENDING = "pending"
    EXECUTED = "executed"
    SETTLED = "settled"
    FAILED = "failed"
    CANCELED = "canceled"


class Trade(BaseModel):
    """
    Trade model representing an executed trade.

    Attributes:
        trade_id: Unique trade identifier
        order_id: Associated order ID
        exchange_trade_id: Exchange-assigned trade ID
        symbol: Trading pair (e.g., "BTCUSDT")
        side: Trade side (buy/sell)
        quantity: Trade quantity
        price: Execution price
        value: Trade value (quantity * price)
        commission: Trading commission
        commission_asset: Asset in which commission is paid
        status: Trade status
        is_maker: Whether this was a maker order
        executed_at: Trade execution timestamp
        settled_at: Settlement timestamp
        pnl: Realized PnL (if closing trade)
        pnl_percentage: Realized PnL percentage
        metadata: Additional metadata
    """

    trade_id: str = Field(..., description="Unique trade identifier")
    order_id: Optional[str] = Field(None, description="Associated order ID")
    exchange_trade_id: Optional[str] = Field(None, description="Exchange-assigned trade ID")

    symbol: str = Field(..., description="Trading pair")
    side: TradeSide = Field(..., description="Trade side")

    quantity: Decimal = Field(..., gt=0, description="Trade quantity")
    price: Decimal = Field(..., gt=0, description="Execution price")
    value: Decimal = Field(..., gt=0, description="Trade value")

    commission: Decimal = Field(Decimal("0"), ge=0, description="Commission paid")
    commission_asset: Optional[str] = Field(None, description="Commission asset")

    status: TradeStatus = Field(TradeStatus.EXECUTED, description="Trade status")
    is_maker: bool = Field(False, description="Maker or taker order")

    executed_at: datetime = Field(default_factory=datetime.utcnow, description="Execution timestamp")
    settled_at: Optional[datetime] = Field(None, description="Settlement timestamp")

    pnl: Optional[Decimal] = Field(None, description="Realized PnL")
    pnl_percentage: Optional[float] = Field(None, description="Realized PnL percentage")

    metadata: dict = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }

    @classmethod
    def from_order_fill(
        cls,
        trade_id: str,
        order_id: str,
        symbol: str,
        side: TradeSide,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = Decimal("0"),
        commission_asset: Optional[str] = None,
        is_maker: bool = False,
        exchange_trade_id: Optional[str] = None,
    ) -> "Trade":
        """Create a Trade from an order fill."""
        return cls(
            trade_id=trade_id,
            order_id=order_id,
            exchange_trade_id=exchange_trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            value=quantity * price,
            commission=commission,
            commission_asset=commission_asset,
            is_maker=is_maker,
        )

    def calculate_net_value(self) -> Decimal:
        """Calculate net value after commission."""
        if self.side == TradeSide.BUY:
            return self.value + self.commission
        else:
            return self.value - self.commission

    @property
    def is_profitable(self) -> bool:
        """Check if trade was profitable."""
        if self.pnl is None:
            return False
        return self.pnl > 0

    @property
    def is_settled(self) -> bool:
        """Check if trade is settled."""
        return self.status == TradeStatus.SETTLED
