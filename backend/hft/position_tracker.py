"""Position Tracker - Track and manage positions"""

from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from models.position import Position
from models.trade import Trade, TradeType
from datetime import datetime
import uuid

class PositionTracker:
    """Track positions and PnL"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.positions: Dict[str, Position] = {}  # symbol -> Position
    
    async def initialize(self):
        """Load existing positions from database"""
        positions_data = await self.db.positions.find({}).to_list(None)
        for pos_data in positions_data:
            symbol = pos_data["symbol"]
            self.positions[symbol] = Position(**pos_data)
        print(f"✅ Loaded {len(self.positions)} positions from database")
    
    async def update_position(self, trade: Trade):
        """Update position based on trade"""
        symbol = trade.symbol
        
        if symbol not in self.positions:
            # Create new position
            self.positions[symbol] = Position(
                id=str(uuid.uuid4()),
                symbol=symbol,
                size=0.0,
                entry_price=0.0,
                current_price=trade.price
            )
        
        position = self.positions[symbol]
        
        # Update position
        if trade.type == TradeType.BUY:
            # Adding to long or reducing short
            new_size = position.size + trade.size
            if position.size == 0:
                position.entry_price = trade.price
            elif (position.size > 0 and new_size > 0) or (position.size < 0 and new_size < 0):
                # Increasing position - update average entry
                total_cost = position.entry_price * abs(position.size) + trade.price * trade.size
                position.entry_price = total_cost / abs(new_size)
            else:
                # Closing or flipping position - realize PnL
                pnl = (trade.price - position.entry_price) * min(abs(position.size), trade.size) * (-1 if position.size < 0 else 1)
                position.realized_pnl += pnl
                if abs(new_size) < abs(position.size):
                    # Partial close - keep entry price
                    pass
                else:
                    # Flip or new position
                    position.entry_price = trade.price
            position.size = new_size
        else:  # SELL
            # Reducing long or adding to short
            new_size = position.size - trade.size
            if position.size == 0:
                position.entry_price = trade.price
            elif (position.size < 0 and new_size < 0) or (position.size > 0 and new_size > 0):
                # Increasing short or long position
                total_cost = position.entry_price * abs(position.size) + trade.price * trade.size
                position.entry_price = total_cost / abs(new_size)
            else:
                # Closing or flipping
                pnl = (trade.price - position.entry_price) * min(abs(position.size), trade.size) * (1 if position.size > 0 else -1)
                position.realized_pnl += pnl
                if abs(new_size) < abs(position.size):
                    pass
                else:
                    position.entry_price = trade.price
            position.size = new_size
        
        position.update_pnl(trade.price)
        
        # Save to database
        await self.db.positions.update_one(
            {"symbol": symbol},
            {"$set": position.dict()},
            upsert=True
        )
    
    async def update_market_price(self, symbol: str, price: float):
        """Update current market price for position"""
        if symbol in self.positions:
            self.positions[symbol].update_pnl(price)
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol"""
        return self.positions.get(symbol)
    
    async def get_all_positions(self) -> List[Dict]:
        """Get all positions"""
        return [pos.dict() for pos in self.positions.values()]
    
    def get_total_pnl(self) -> Dict:
        """Get total PnL across all positions"""
        total_unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
        total_realized = sum(pos.realized_pnl for pos in self.positions.values())
        return {
            "unrealized_pnl": total_unrealized,
            "realized_pnl": total_realized,
            "total_pnl": total_unrealized + total_realized
        }
