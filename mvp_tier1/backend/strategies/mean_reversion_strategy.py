"""
HFT MVP Tier 1 - Mean Reversion Strategy
Simple mean reversion trading strategy
"""

from typing import Dict, Optional, List
from datetime import datetime
from collections import deque
import numpy as np

from .base_strategy import BaseStrategy, Signal
import logging

logger = logging.getLogger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy
    
    Generates signals based on deviation from moving average:
    - Long when price is significantly below MA (oversold)
    - Short when price is significantly above MA (overbought)
    - Close when price returns to MA
    """
    
    def __init__(self, params: Optional[Dict] = None):
        """
        Initialize mean reversion strategy
        
        Args:
            params: Strategy parameters
                - ma_period: Moving average period (default: 20)
                - std_multiplier: Standard deviation multiplier for bands (default: 2.0)
                - min_strength: Minimum signal strength (default: 0.3)
        """
        default_params = {
            'ma_period': 20,
            'std_multiplier': 2.0,
            'min_strength': 0.3
        }
        
        if params:
            default_params.update(params)
        
        super().__init__('MeanReversion', default_params)
        
        # Price history
        self.price_history = deque(maxlen=self.params['ma_period'])
        
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
            if len(self.price_history) < self.params['ma_period']:
                return None
            
            # Calculate MA and bands
            ma, upper_band, lower_band = self._calculate_bands()
            
            # Generate signal
            signal = self._generate_signal(symbol, price, ma, upper_band, lower_band)
            
            self._record_signal(signal)
            return signal
            
        except Exception as e:
            logger.error(f"Error in mean reversion strategy: {e}")
            return None
    
    async def on_orderbook(self, orderbook: Dict) -> Optional[Signal]:
        """Process orderbook update (not used in mean reversion strategy)"""
        return None
    
    async def on_trade(self, trades: List[Dict]) -> Optional[Signal]:
        """Process trade update (not used in mean reversion strategy)"""
        return None
    
    def _calculate_bands(self):
        """
        Calculate moving average and Bollinger Bands
        
        Returns:
            Tuple of (ma, upper_band, lower_band)
        """
        prices = np.array(self.price_history)
        
        # Moving average
        ma = np.mean(prices)
        
        # Standard deviation
        std = np.std(prices)
        
        # Bollinger Bands
        multiplier = self.params['std_multiplier']
        upper_band = ma + (multiplier * std)
        lower_band = ma - (multiplier * std)
        
        return ma, upper_band, lower_band
    
    def _generate_signal(
        self,
        symbol: str,
        price: float,
        ma: float,
        upper_band: float,
        lower_band: float
    ) -> Optional[Signal]:
        """
        Generate trading signal based on mean reversion
        
        Args:
            symbol: Trading symbol
            price: Current price
            ma: Moving average
            upper_band: Upper Bollinger Band
            lower_band: Lower Bollinger Band
            
        Returns:
            Signal or None
        """
        min_strength = self.params['min_strength']
        
        # Calculate distance from MA (normalized by band width)
        band_width = upper_band - lower_band
        if band_width == 0:
            return None
        
        distance_from_ma = (price - ma) / band_width
        
        # Calculate signal strength
        strength = min(abs(distance_from_ma) * 2, 1.0)  # *2 because bands are ±2 std
        
        # Only generate signal if strength is above minimum
        if strength < min_strength:
            return None
        
        # Determine direction
        if price < lower_band:
            # Price below lower band -> Oversold -> Long signal
            if self.current_position != 'long':
                self.current_position = 'long'
                return Signal(
                    symbol=symbol,
                    direction='long',
                    strength=strength,
                    price=price,
                    timestamp=datetime.utcnow(),
                    metadata={
                        'ma': ma,
                        'upper_band': upper_band,
                        'lower_band': lower_band,
                        'distance_from_ma': distance_from_ma
                    }
                )
        
        elif price > upper_band:
            # Price above upper band -> Overbought -> Short signal
            if self.current_position != 'short':
                self.current_position = 'short'
                return Signal(
                    symbol=symbol,
                    direction='short',
                    strength=strength,
                    price=price,
                    timestamp=datetime.utcnow(),
                    metadata={
                        'ma': ma,
                        'upper_band': upper_band,
                        'lower_band': lower_band,
                        'distance_from_ma': distance_from_ma
                    }
                )
        
        elif lower_band <= price <= upper_band:
            # Price within bands -> Close signal
            if self.current_position is not None:
                self.current_position = None
                return Signal(
                    symbol=symbol,
                    direction='close',
                    strength=strength,
                    price=price,
                    timestamp=datetime.utcnow(),
                    metadata={
                        'ma': ma,
                        'upper_band': upper_band,
                        'lower_band': lower_band,
                        'distance_from_ma': distance_from_ma
                    }
                )
        
        return None
