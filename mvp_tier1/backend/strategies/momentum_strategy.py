"""
HFT MVP Tier 1 - Momentum Strategy
Simple momentum-based trading strategy
"""

from typing import Dict, Optional, List
from datetime import datetime
from collections import deque
import numpy as np

from .base_strategy import BaseStrategy, Signal
import logging

logger = logging.getLogger(__name__)


class MomentumStrategy(BaseStrategy):
    """
    Momentum Strategy
    
    Generates signals based on price momentum:
    - Long when price momentum is positive and strong
    - Short when price momentum is negative and strong
    - Close when momentum weakens
    """
    
    def __init__(self, params: Optional[Dict] = None):
        """
        Initialize momentum strategy
        
        Args:
            params: Strategy parameters
                - lookback: Number of periods for momentum calculation (default: 20)
                - threshold: Momentum threshold for signal generation (default: 0.001)
                - min_strength: Minimum signal strength (default: 0.3)
        """
        default_params = {
            'lookback': 20,
            'threshold': 0.001,  # 0.1%
            'min_strength': 0.3
        }
        
        if params:
            default_params.update(params)
        
        super().__init__('Momentum', default_params)
        
        # Price history
        self.price_history = deque(maxlen=self.params['lookback'])
        
        # Current position
        self.current_position = None  # 'long', 'short', or None
    
    async def on_ticker(self, ticker: Dict) -> Optional[Signal]:
        """
        Process ticker update and generate signal
        
        Args:
            ticker: Ticker data with 'last' price
            
        Returns:
            Signal or None
        """
        if not self.is_active:
            return None
        
        try:
            price = float(ticker['last'])
            symbol = ticker['symbol']
            
            # Add price to history
            self.price_history.append(price)
            
            # Need enough data
            if len(self.price_history) < self.params['lookback']:
                return None
            
            # Calculate momentum
            momentum = self._calculate_momentum()
            
            # Generate signal
            signal = self._generate_signal(symbol, price, momentum)
            
            self._record_signal(signal)
            return signal
            
        except Exception as e:
            logger.error(f"Error in momentum strategy: {e}")
            return None
    
    async def on_orderbook(self, orderbook: Dict) -> Optional[Signal]:
        """Process orderbook update (not used in momentum strategy)"""
        return None
    
    async def on_trade(self, trades: List[Dict]) -> Optional[Signal]:
        """Process trade update (not used in momentum strategy)"""
        return None
    
    def _calculate_momentum(self) -> float:
        """
        Calculate price momentum
        
        Returns:
            Momentum value (percentage change)
        """
        prices = np.array(self.price_history)
        
        # Simple momentum: (current - start) / start
        momentum = (prices[-1] - prices[0]) / prices[0]
        
        return momentum
    
    def _generate_signal(self, symbol: str, price: float, momentum: float) -> Optional[Signal]:
        """
        Generate trading signal based on momentum
        
        Args:
            symbol: Trading symbol
            price: Current price
            momentum: Calculated momentum
            
        Returns:
            Signal or None
        """
        threshold = self.params['threshold']
        min_strength = self.params['min_strength']
        
        # Calculate signal strength (normalized momentum)
        strength = min(abs(momentum) / threshold, 1.0)
        
        # Only generate signal if strength is above minimum
        if strength < min_strength:
            return None
        
        # Determine direction
        if momentum > threshold:
            # Positive momentum -> Long signal
            if self.current_position != 'long':
                self.current_position = 'long'
                return Signal(
                    symbol=symbol,
                    direction='long',
                    strength=strength,
                    price=price,
                    timestamp=datetime.utcnow(),
                    metadata={
                        'momentum': momentum,
                        'threshold': threshold
                    }
                )
        
        elif momentum < -threshold:
            # Negative momentum -> Short signal
            if self.current_position != 'short':
                self.current_position = 'short'
                return Signal(
                    symbol=symbol,
                    direction='short',
                    strength=strength,
                    price=price,
                    timestamp=datetime.utcnow(),
                    metadata={
                        'momentum': momentum,
                        'threshold': threshold
                    }
                )
        
        else:
            # Weak momentum -> Close signal
            if self.current_position is not None:
                self.current_position = None
                return Signal(
                    symbol=symbol,
                    direction='close',
                    strength=strength,
                    price=price,
                    timestamp=datetime.utcnow(),
                    metadata={
                        'momentum': momentum,
                        'threshold': threshold
                    }
                )
        
        return None
