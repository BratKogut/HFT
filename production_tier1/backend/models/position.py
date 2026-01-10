"""
Position Model
==============

Pydantic model for trading positions.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from decimal import Decimal


class PositionSide(str, Enum):
    """Position side enum."""
    LONG = "long"
    SHORT = "short"


class Position(BaseModel):
    """
    Position model representing an open trading position.

    Attributes:
        position_id: Unique position identifier
        symbol: Trading pair (e.g., "BTCUSDT")
        side: Position side (long/short)
        size: Position size
        entry_price: Average entry price
        current_price: Current market price
        unrealized_pnl: Unrealized profit/loss
        realized_pnl: Realized profit/loss
        leverage: Position leverage (1 for spot)
        margin_used: Margin used for position
        liquidation_price: Liquidation price (for leveraged positions)
        take_profit: Take profit price
        stop_loss: Stop loss price
        opened_at: Position open timestamp
        updated_at: Last update timestamp
        trade_ids: List of associated trade IDs
        metadata: Additional metadata
    """

    position_id: str = Field(..., description="Unique position identifier")
    symbol: str = Field(..., description="Trading pair")
    side: PositionSide = Field(..., description="Position side")

    size: Decimal = Field(..., ge=0, description="Position size")
    entry_price: Decimal = Field(..., gt=0, description="Average entry price")
    current_price: Optional[Decimal] = Field(None, gt=0, description="Current market price")

    unrealized_pnl: Decimal = Field(Decimal("0"), description="Unrealized PnL")
    unrealized_pnl_percentage: float = Field(0.0, description="Unrealized PnL percentage")
    realized_pnl: Decimal = Field(Decimal("0"), description="Realized PnL")

    leverage: int = Field(1, ge=1, description="Position leverage")
    margin_used: Decimal = Field(Decimal("0"), ge=0, description="Margin used")
    liquidation_price: Optional[Decimal] = Field(None, description="Liquidation price")

    take_profit: Optional[Decimal] = Field(None, gt=0, description="Take profit price")
    stop_loss: Optional[Decimal] = Field(None, gt=0, description="Stop loss price")

    opened_at: datetime = Field(default_factory=datetime.utcnow, description="Open timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Update timestamp")

    trade_ids: List[str] = Field(default_factory=list, description="Associated trade IDs")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }

    def update_price(self, new_price: Decimal):
        """Update current price and recalculate unrealized PnL."""
        self.current_price = new_price

        if self.side == PositionSide.LONG:
            price_diff = new_price - self.entry_price
        else:  # SHORT
            price_diff = self.entry_price - new_price

        self.unrealized_pnl = price_diff * self.size

        # Calculate percentage
        position_value = self.entry_price * self.size
        if position_value > 0:
            self.unrealized_pnl_percentage = float(
                (self.unrealized_pnl / position_value) * 100
            )
        else:
            self.unrealized_pnl_percentage = 0.0

        self.updated_at = datetime.utcnow()

    def add_to_position(self, quantity: Decimal, price: Decimal, trade_id: str):
        """Add to existing position (scale in)."""
        # Calculate new average entry price
        total_value = (self.entry_price * self.size) + (price * quantity)
        new_size = self.size + quantity

        if new_size > 0:
            self.entry_price = total_value / new_size

        self.size = new_size
        self.trade_ids.append(trade_id)
        self.updated_at = datetime.utcnow()

        # Recalculate unrealized PnL if we have current price
        if self.current_price:
            self.update_price(self.current_price)

    def reduce_position(self, quantity: Decimal, price: Decimal, trade_id: str) -> Decimal:
        """
        Reduce position size (scale out).

        Returns:
            Realized PnL from the reduction.
        """
        if quantity > self.size:
            quantity = self.size

        # Calculate realized PnL for this portion
        if self.side == PositionSide.LONG:
            pnl = (price - self.entry_price) * quantity
        else:  # SHORT
            pnl = (self.entry_price - price) * quantity

        self.realized_pnl += pnl
        self.size -= quantity
        self.trade_ids.append(trade_id)
        self.updated_at = datetime.utcnow()

        # Recalculate unrealized PnL
        if self.current_price:
            self.update_price(self.current_price)

        return pnl

    def close(self, price: Decimal, trade_id: str) -> Decimal:
        """
        Close the entire position.

        Returns:
            Total realized PnL from closing.
        """
        return self.reduce_position(self.size, price, trade_id)

    @property
    def is_open(self) -> bool:
        """Check if position is still open."""
        return self.size > 0

    @property
    def is_profitable(self) -> bool:
        """Check if position is currently profitable."""
        return self.unrealized_pnl > 0

    @property
    def position_value(self) -> Decimal:
        """Calculate current position value."""
        price = self.current_price or self.entry_price
        return self.size * price

    @property
    def risk_reward_ratio(self) -> Optional[float]:
        """Calculate risk/reward ratio based on TP/SL."""
        if not self.take_profit or not self.stop_loss:
            return None

        if self.side == PositionSide.LONG:
            potential_profit = float(self.take_profit - self.entry_price)
            potential_loss = float(self.entry_price - self.stop_loss)
        else:  # SHORT
            potential_profit = float(self.entry_price - self.take_profit)
            potential_loss = float(self.stop_loss - self.entry_price)

        if potential_loss <= 0:
            return None

        return potential_profit / potential_loss

    def should_take_profit(self) -> bool:
        """Check if take profit should trigger."""
        if not self.take_profit or not self.current_price:
            return False

        if self.side == PositionSide.LONG:
            return self.current_price >= self.take_profit
        else:  # SHORT
            return self.current_price <= self.take_profit

    def should_stop_loss(self) -> bool:
        """Check if stop loss should trigger."""
        if not self.stop_loss or not self.current_price:
            return False

        if self.side == PositionSide.LONG:
            return self.current_price <= self.stop_loss
        else:  # SHORT
            return self.current_price >= self.stop_loss
