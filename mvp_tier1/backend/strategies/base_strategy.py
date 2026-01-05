"""
HFT MVP Tier 1 - Base Strategy Class
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Signal:
    """Trading signal"""
    
    def __init__(
        self,
        symbol: str,
        direction: str,  # 'long', 'short', 'close'
        strength: float,  # 0.0 to 1.0
        price: float,
        timestamp: datetime,
        metadata: Optional[Dict] = None
    ):
        self.symbol = symbol
        self.direction = direction
        self.strength = strength
        self.price = price
        self.timestamp = timestamp
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict:
        """Convert signal to dictionary"""
        return {
            'symbol': self.symbol,
            'direction': self.direction,
            'strength': self.strength,
            'price': self.price,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }
    
    def __repr__(self) -> str:
        return f"Signal({self.symbol}, {self.direction}, strength={self.strength:.2f}, price={self.price})"


class BaseStrategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, name: str, params: Optional[Dict] = None):
        """
        Initialize strategy
        
        Args:
            name: Strategy name
            params: Strategy parameters
        """
        self.name = name
        self.params = params or {}
        self.is_active = False
        
        # State
        self.last_signal = None
        self.signal_history = []
        
        logger.info(f"Strategy '{name}' initialized with params: {params}")
    
    @abstractmethod
    async def on_ticker(self, ticker: Dict) -> Optional[Signal]:
        """
        Process ticker update
        
        Args:
            ticker: Ticker data
            
        Returns:
            Signal or None
        """
        pass
    
    @abstractmethod
    async def on_orderbook(self, orderbook: Dict) -> Optional[Signal]:
        """
        Process orderbook update
        
        Args:
            orderbook: Orderbook data
            
        Returns:
            Signal or None
        """
        pass
    
    @abstractmethod
    async def on_trade(self, trades: List[Dict]) -> Optional[Signal]:
        """
        Process trade update
        
        Args:
            trades: List of trades
            
        Returns:
            Signal or None
        """
        pass
    
    def activate(self):
        """Activate strategy"""
        self.is_active = True
        logger.info(f"Strategy '{self.name}' activated")
    
    def deactivate(self):
        """Deactivate strategy"""
        self.is_active = False
        logger.info(f"Strategy '{self.name}' deactivated")
    
    def _record_signal(self, signal: Optional[Signal]):
        """Record signal in history"""
        if signal:
            self.last_signal = signal
            self.signal_history.append(signal)
            
            # Keep only last 1000 signals
            if len(self.signal_history) > 1000:
                self.signal_history = self.signal_history[-1000:]
    
    def get_stats(self) -> Dict:
        """Get strategy statistics"""
        return {
            'name': self.name,
            'is_active': self.is_active,
            'total_signals': len(self.signal_history),
            'last_signal': self.last_signal.to_dict() if self.last_signal else None,
            'params': self.params
        }
