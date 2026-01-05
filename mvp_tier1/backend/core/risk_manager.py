"""
HFT MVP Tier 1 - Risk Management
Pre-trade risk checks and position management
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class Position:
    """Trading position"""
    
    def __init__(
        self,
        symbol: str,
        side: str,  # 'long' or 'short'
        size: float,
        entry_price: float,
        timestamp: datetime
    ):
        self.symbol = symbol
        self.side = side
        self.size = size
        self.entry_price = entry_price
        self.timestamp = timestamp
        self.unrealized_pnl = 0.0
    
    def update_pnl(self, current_price: float):
        """Update unrealized PnL"""
        if self.side == 'long':
            self.unrealized_pnl = (current_price - self.entry_price) * self.size
        else:  # short
            self.unrealized_pnl = (self.entry_price - current_price) * self.size
    
    def to_dict(self) -> Dict:
        """Convert position to dictionary"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'size': self.size,
            'entry_price': self.entry_price,
            'timestamp': self.timestamp.isoformat(),
            'unrealized_pnl': self.unrealized_pnl
        }


class RiskManager:
    """Risk management and pre-trade checks"""
    
    def __init__(self, config: Dict):
        """
        Initialize risk manager
        
        Args:
            config: Risk configuration
                - base_capital: Starting capital
                - max_position_size: Maximum position size
                - max_risk_per_trade: Maximum risk per trade (as fraction)
                - max_daily_loss: Maximum daily loss (as fraction)
                - max_drawdown: Maximum drawdown (as fraction)
        """
        self.config = config
        
        # Capital tracking
        self.base_capital = config.get('base_capital', 10000.0)
        self.current_capital = self.base_capital
        self.peak_capital = self.base_capital
        
        # Positions
        self.positions: Dict[str, Position] = {}
        
        # Daily tracking
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_reset = datetime.utcnow().date()
        
        # Circuit breaker
        self.is_halted = False
        self.halt_reason = None
        
        logger.info(f"RiskManager initialized with capital: ${self.base_capital}")
    
    def pre_trade_check(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float
    ) -> tuple[bool, Optional[str]]:
        """
        Pre-trade risk checks
        
        Args:
            symbol: Trading symbol
            side: 'long' or 'short'
            size: Position size
            price: Entry price
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check if trading is halted
        if self.is_halted:
            return False, f"Trading halted: {self.halt_reason}"
        
        # Check position size limit
        max_position_size = self.config.get('max_position_size', 1000.0)
        if size > max_position_size:
            return False, f"Position size {size} exceeds limit {max_position_size}"
        
        # Check if position value exceeds capital
        position_value = size * price
        if position_value > self.current_capital:
            return False, f"Position value ${position_value:.2f} exceeds capital ${self.current_capital:.2f}"
        
        # Check risk per trade
        max_risk_per_trade = self.config.get('max_risk_per_trade', 0.02)
        max_risk_amount = self.current_capital * max_risk_per_trade
        if position_value > max_risk_amount:
            return False, f"Position risk ${position_value:.2f} exceeds max ${max_risk_amount:.2f}"
        
        # Check daily loss limit
        max_daily_loss = self.config.get('max_daily_loss', 0.05)
        max_daily_loss_amount = self.base_capital * max_daily_loss
        if self.daily_pnl < -max_daily_loss_amount:
            self.halt_trading("Daily loss limit exceeded")
            return False, f"Daily loss ${abs(self.daily_pnl):.2f} exceeds limit ${max_daily_loss_amount:.2f}"
        
        # Check drawdown
        max_drawdown = self.config.get('max_drawdown', 0.20)
        current_drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
        if current_drawdown > max_drawdown:
            self.halt_trading("Maximum drawdown exceeded")
            return False, f"Drawdown {current_drawdown:.2%} exceeds limit {max_drawdown:.2%}"
        
        # Check if already have position in this symbol
        if symbol in self.positions:
            return False, f"Already have position in {symbol}"
        
        # All checks passed
        return True, None
    
    def open_position(
        self,
        symbol: str,
        side: str,
        size: float,
        entry_price: float
    ) -> Position:
        """
        Open a new position
        
        Args:
            symbol: Trading symbol
            side: 'long' or 'short'
            size: Position size
            entry_price: Entry price
            
        Returns:
            Position object
        """
        position = Position(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            timestamp=datetime.utcnow()
        )
        
        self.positions[symbol] = position
        self.daily_trades += 1
        
        logger.info(f"Opened {side} position: {symbol} size={size} @ ${entry_price}")
        
        return position
    
    def close_position(
        self,
        symbol: str,
        exit_price: float
    ) -> Optional[float]:
        """
        Close an existing position
        
        Args:
            symbol: Trading symbol
            exit_price: Exit price
            
        Returns:
            Realized PnL or None if position doesn't exist
        """
        if symbol not in self.positions:
            logger.warning(f"No position to close for {symbol}")
            return None
        
        position = self.positions[symbol]
        
        # Calculate realized PnL
        if position.side == 'long':
            pnl = (exit_price - position.entry_price) * position.size
        else:  # short
            pnl = (position.entry_price - exit_price) * position.size
        
        # Update capital
        self.current_capital += pnl
        self.daily_pnl += pnl
        
        # Update peak capital
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
        
        # Remove position
        del self.positions[symbol]
        
        logger.info(f"Closed {position.side} position: {symbol} @ ${exit_price}, PnL: ${pnl:.2f}")
        
        return pnl
    
    def update_positions(self, prices: Dict[str, float]):
        """
        Update all positions with current prices
        
        Args:
            prices: Dictionary of symbol -> current price
        """
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_pnl(prices[symbol])
    
    def halt_trading(self, reason: str):
        """
        Halt all trading (circuit breaker)
        
        Args:
            reason: Reason for halt
        """
        self.is_halted = True
        self.halt_reason = reason
        logger.warning(f"Trading HALTED: {reason}")
    
    def resume_trading(self):
        """Resume trading after halt"""
        self.is_halted = False
        self.halt_reason = None
        logger.info("Trading RESUMED")
    
    def reset_daily_stats(self):
        """Reset daily statistics (called at start of new trading day)"""
        today = datetime.utcnow().date()
        
        if today > self.last_reset:
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.last_reset = today
            logger.info("Daily stats reset")
    
    def get_stats(self) -> Dict:
        """Get risk statistics"""
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        current_drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
        
        return {
            'base_capital': self.base_capital,
            'current_capital': self.current_capital,
            'peak_capital': self.peak_capital,
            'total_pnl': self.current_capital - self.base_capital,
            'total_pnl_pct': ((self.current_capital - self.base_capital) / self.base_capital) * 100,
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trades,
            'open_positions': len(self.positions),
            'total_unrealized_pnl': total_unrealized_pnl,
            'current_drawdown': current_drawdown,
            'is_halted': self.is_halted,
            'halt_reason': self.halt_reason
        }
    
    def get_positions(self) -> List[Dict]:
        """Get all open positions"""
        return [p.to_dict() for p in self.positions.values()]
