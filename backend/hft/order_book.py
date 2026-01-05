"""Order Book - Fast order book management"""

import numpy as np
from typing import Dict, List, Tuple
from collections import deque

class OrderBook:
    """Ultra-fast order book implementation using NumPy"""
    
    def __init__(self, symbol: str, depth: int = 20):
        self.symbol = symbol
        self.depth = depth
        
        # Bids and asks as lists of [price, size]
        self.bids: List[List[float]] = []
        self.asks: List[List[float]] = []
        
        # Derived metrics
        self.mid_price = 0.0
        self.spread = 0.0
        self.imbalance = 0.0
        
        # History for analysis
        self.price_history = deque(maxlen=1000)
        self.spread_history = deque(maxlen=1000)
    
    def update(self, bids: List[List[float]], asks: List[List[float]]):
        """Update order book"""
        self.bids = bids[:self.depth]
        self.asks = asks[:self.depth]
        
        # Calculate derived metrics
        if self.bids and self.asks:
            self.mid_price = (self.bids[0][0] + self.asks[0][0]) / 2
            self.spread = self.asks[0][0] - self.bids[0][0]
            self.imbalance = self._calculate_imbalance()
            
            # Update history
            self.price_history.append(self.mid_price)
            self.spread_history.append(self.spread)
    
    def _calculate_imbalance(self, levels: int = 5) -> float:
        """Calculate order book imbalance
        
        Imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
        Returns: -1 to +1 (negative = sell pressure, positive = buy pressure)
        """
        if not self.bids or not self.asks:
            return 0.0
        
        bid_volume = sum(level[1] for level in self.bids[:levels])
        ask_volume = sum(level[1] for level in self.asks[:levels])
        
        total_volume = bid_volume + ask_volume
        if total_volume == 0:
            return 0.0
        
        return (bid_volume - ask_volume) / total_volume
    
    def get_best_bid(self) -> Tuple[float, float]:
        """Get best bid [price, size]"""
        return tuple(self.bids[0]) if self.bids else (0.0, 0.0)
    
    def get_best_ask(self) -> Tuple[float, float]:
        """Get best ask [price, size]"""
        return tuple(self.asks[0]) if self.asks else (0.0, 0.0)
    
    def get_mid_price(self) -> float:
        """Get mid price"""
        return self.mid_price
    
    def get_spread(self) -> float:
        """Get bid-ask spread"""
        return self.spread
    
    def get_spread_bps(self) -> float:
        """Get spread in basis points"""
        if self.mid_price > 0:
            return (self.spread / self.mid_price) * 10000
        return 0.0
    
    def get_imbalance(self) -> float:
        """Get order book imbalance (-1 to +1)"""
        return self.imbalance
    
    def get_snapshot(self) -> Dict:
        """Get order book snapshot"""
        return {
            "symbol": self.symbol,
            "bids": self.bids,
            "asks": self.asks,
            "mid_price": self.mid_price,
            "spread": self.spread,
            "spread_bps": self.get_spread_bps(),
            "imbalance": self.imbalance,
            "best_bid": list(self.get_best_bid()),
            "best_ask": list(self.get_best_ask())
        }
    
    def get_depth_chart_data(self) -> Dict:
        """Get data for depth chart visualization"""
        bid_cumulative = []
        ask_cumulative = []
        
        # Calculate cumulative volumes
        bid_volume = 0
        for price, size in self.bids:
            bid_volume += size
            bid_cumulative.append({"price": price, "volume": bid_volume})
        
        ask_volume = 0
        for price, size in self.asks:
            ask_volume += size
            ask_cumulative.append({"price": price, "volume": ask_volume})
        
        return {
            "bids": bid_cumulative,
            "asks": ask_cumulative
        }
