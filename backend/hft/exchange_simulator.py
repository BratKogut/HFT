"""Exchange Simulator - Simulate market data for testing"""

import asyncio
import random
from typing import Dict, List
import numpy as np

class ExchangeSimulator:
    """Simulate exchange market data"""
    
    def __init__(self, symbol: str, base_price: float = 50000.0):
        self.symbol = symbol
        self.base_price = base_price
        self.current_price = base_price
        self.volatility = 0.0005  # 0.05% per tick
        self.is_running = False
        
        # Order book
        self.bids = []  # [(price, size), ...]
        self.asks = []  # [(price, size), ...]
        
        self._generate_order_book()
    
    def _generate_order_book(self, levels: int = 10):
        """Generate realistic order book"""
        spread = self.current_price * 0.0001  # 0.01% spread
        
        # Generate bids (below mid price)
        self.bids = []
        for i in range(levels):
            price = self.current_price - spread/2 - i * (spread / levels)
            size = random.uniform(0.1, 2.0)
            self.bids.append([price, size])
        
        # Generate asks (above mid price)
        self.asks = []
        for i in range(levels):
            price = self.current_price + spread/2 + i * (spread / levels)
            size = random.uniform(0.1, 2.0)
            self.asks.append([price, size])
    
    def _update_price(self):
        """Update price with random walk"""
        # Random walk with mean reversion
        mean_reversion = (self.base_price - self.current_price) * 0.001
        change = np.random.normal(0, self.volatility) + mean_reversion
        self.current_price *= (1 + change)
        self.current_price = max(self.current_price, self.base_price * 0.5)  # Floor
        self.current_price = min(self.current_price, self.base_price * 1.5)  # Ceiling
    
    def _update_order_book(self):
        """Update order book with new price"""
        self._generate_order_book()
        
        # Add some randomness to top levels
        if self.bids:
            self.bids[0][1] += random.uniform(-0.5, 0.5)
            self.bids[0][1] = max(0.1, self.bids[0][1])
        
        if self.asks:
            self.asks[0][1] += random.uniform(-0.5, 0.5)
            self.asks[0][1] = max(0.1, self.asks[0][1])
    
    async def start(self):
        """Start simulation"""
        self.is_running = True
        print(f"✅ Exchange simulator started for {self.symbol}")
    
    async def stop(self):
        """Stop simulation"""
        self.is_running = False
        print(f"❌ Exchange simulator stopped for {self.symbol}")
    
    async def get_tick(self) -> Dict:
        """Get next market data tick"""
        self._update_price()
        self._update_order_book()
        
        return {
            "symbol": self.symbol,
            "price": self.current_price,
            "bid": self.bids[0][0] if self.bids else self.current_price,
            "ask": self.asks[0][0] if self.asks else self.current_price,
            "bids": self.bids[:10],
            "asks": self.asks[:10],
            "timestamp": asyncio.get_event_loop().time()
        }
    
    def get_order_book(self) -> Dict:
        """Get current order book snapshot"""
        return {
            "symbol": self.symbol,
            "bids": self.bids[:10],
            "asks": self.asks[:10],
            "mid_price": self.current_price,
            "spread": self.asks[0][0] - self.bids[0][0] if self.bids and self.asks else 0
        }
