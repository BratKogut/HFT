"""
Order Book Management
====================

High-performance order book using NumPy arrays.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from decimal import Decimal
import time


@dataclass
class OrderBookLevel:
    """Single order book level."""
    price: float
    quantity: float
    timestamp: float


class OrderBook:
    """
    High-performance order book implementation.
    
    Uses NumPy arrays for fast operations.
    Maintains sorted bid/ask levels.
    """
    
    def __init__(self, symbol: str, max_depth: int = 100):
        """
        Initialize order book.
        
        Args:
            symbol: Trading pair symbol
            max_depth: Maximum depth to maintain
        """
        self.symbol = symbol
        self.max_depth = max_depth
        
        # NumPy arrays for bids/asks [price, quantity, timestamp]
        self.bids = np.zeros((max_depth, 3), dtype=np.float64)
        self.asks = np.zeros((max_depth, 3), dtype=np.float64)
        
        self.bid_count = 0
        self.ask_count = 0
        
        self.last_update_time = 0.0
        self.sequence_number = 0
        
    def update_snapshot(self, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]]):
        """
        Update order book with full snapshot.
        
        Args:
            bids: List of (price, quantity) tuples for bids
            asks: List of (price, quantity) tuples for asks
        """
        timestamp = time.time()
        
        # Clear existing data
        self.bid_count = 0
        self.ask_count = 0
        
        # Update bids (sorted descending by price)
        for i, (price, qty) in enumerate(sorted(bids, key=lambda x: x[0], reverse=True)[:self.max_depth]):
            self.bids[i] = [price, qty, timestamp]
            self.bid_count += 1
        
        # Update asks (sorted ascending by price)
        for i, (price, qty) in enumerate(sorted(asks, key=lambda x: x[0])[:self.max_depth]):
            self.asks[i] = [price, qty, timestamp]
            self.ask_count += 1
        
        self.last_update_time = timestamp
        self.sequence_number += 1
    
    def update_level(self, side: str, price: float, quantity: float):
        """
        Update single order book level.
        
        Args:
            side: 'bid' or 'ask'
            price: Price level
            quantity: New quantity (0 to remove)
        """
        timestamp = time.time()
        
        if side == 'bid':
            self._update_bid_level(price, quantity, timestamp)
        else:
            self._update_ask_level(price, quantity, timestamp)
        
        self.last_update_time = timestamp
        self.sequence_number += 1
    
    def _update_bid_level(self, price: float, quantity: float, timestamp: float):
        """Update bid level."""
        # Find price level
        idx = np.where(self.bids[:self.bid_count, 0] == price)[0]
        
        if quantity == 0:
            # Remove level
            if len(idx) > 0:
                self.bids = np.delete(self.bids, idx[0], axis=0)
                self.bids = np.vstack([self.bids, np.zeros(3)])
                self.bid_count -= 1
        else:
            if len(idx) > 0:
                # Update existing level
                self.bids[idx[0]] = [price, quantity, timestamp]
            else:
                # Insert new level (maintain descending order)
                if self.bid_count < self.max_depth:
                    self.bids[self.bid_count] = [price, quantity, timestamp]
                    self.bid_count += 1
                    # Sort descending
                    self.bids[:self.bid_count] = self.bids[:self.bid_count][
                        np.argsort(self.bids[:self.bid_count, 0])[::-1]
                    ]
    
    def _update_ask_level(self, price: float, quantity: float, timestamp: float):
        """Update ask level."""
        # Find price level
        idx = np.where(self.asks[:self.ask_count, 0] == price)[0]
        
        if quantity == 0:
            # Remove level
            if len(idx) > 0:
                self.asks = np.delete(self.asks, idx[0], axis=0)
                self.asks = np.vstack([self.asks, np.zeros(3)])
                self.ask_count -= 1
        else:
            if len(idx) > 0:
                # Update existing level
                self.asks[idx[0]] = [price, quantity, timestamp]
            else:
                # Insert new level (maintain ascending order)
                if self.ask_count < self.max_depth:
                    self.asks[self.ask_count] = [price, quantity, timestamp]
                    self.ask_count += 1
                    # Sort ascending
                    self.asks[:self.ask_count] = self.asks[:self.ask_count][
                        np.argsort(self.asks[:self.ask_count, 0])
                    ]
    
    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        """Get best bid."""
        if self.bid_count == 0:
            return None
        return OrderBookLevel(*self.bids[0])
    
    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        """Get best ask."""
        if self.ask_count == 0:
            return None
        return OrderBookLevel(*self.asks[0])
    
    @property
    def mid_price(self) -> Optional[float]:
        """Calculate mid price."""
        if self.bid_count == 0 or self.ask_count == 0:
            return None
        return (self.bids[0, 0] + self.asks[0, 0]) / 2.0
    
    @property
    def spread(self) -> Optional[float]:
        """Calculate spread."""
        if self.bid_count == 0 or self.ask_count == 0:
            return None
        return self.asks[0, 0] - self.bids[0, 0]
    
    @property
    def spread_bps(self) -> Optional[float]:
        """Calculate spread in basis points."""
        if self.mid_price is None or self.spread is None:
            return None
        return (self.spread / self.mid_price) * 10000
    
    def get_bids(self, depth: int = 10) -> List[OrderBookLevel]:
        """Get top N bids."""
        return [OrderBookLevel(*self.bids[i]) for i in range(min(depth, self.bid_count))]
    
    def get_asks(self, depth: int = 10) -> List[OrderBookLevel]:
        """Get top N asks."""
        return [OrderBookLevel(*self.asks[i]) for i in range(min(depth, self.ask_count))]
    
    def calculate_imbalance(self, depth: int = 5) -> float:
        """
        Calculate order book imbalance.
        
        Returns value between -1 (ask heavy) and +1 (bid heavy).
        """
        if self.bid_count == 0 or self.ask_count == 0:
            return 0.0
        
        bid_volume = np.sum(self.bids[:min(depth, self.bid_count), 1])
        ask_volume = np.sum(self.asks[:min(depth, self.ask_count), 1])
        
        total_volume = bid_volume + ask_volume
        if total_volume == 0:
            return 0.0
        
        return (bid_volume - ask_volume) / total_volume
    
    def calculate_vwap(self, side: str, quantity: float) -> Optional[float]:
        """
        Calculate VWAP for given quantity.
        
        Args:
            side: 'buy' or 'sell'
            quantity: Quantity to calculate VWAP for
        
        Returns:
            VWAP price or None if insufficient liquidity
        """
        if side == 'buy':
            levels = self.asks[:self.ask_count]
        else:
            levels = self.bids[:self.bid_count]
        
        remaining = quantity
        total_cost = 0.0
        
        for price, qty, _ in levels:
            if remaining <= 0:
                break
            
            take_qty = min(remaining, qty)
            total_cost += take_qty * price
            remaining -= take_qty
        
        if remaining > 0:
            return None  # Insufficient liquidity
        
        return total_cost / quantity
    
    def to_dict(self, depth: int = 10) -> dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "bids": [[float(p), float(q)] for p, q, _ in self.bids[:min(depth, self.bid_count)]],
            "asks": [[float(p), float(q)] for p, q, _ in self.asks[:min(depth, self.ask_count)]],
            "mid_price": self.mid_price,
            "spread": self.spread,
            "spread_bps": self.spread_bps,
            "imbalance": self.calculate_imbalance(),
            "timestamp": self.last_update_time,
            "sequence": self.sequence_number,
        }


class OrderBookManager:
    """
    Manages multiple order books.
    """
    
    def __init__(self, max_depth: int = 100):
        """Initialize order book manager."""
        self.max_depth = max_depth
        self.order_books: Dict[str, OrderBook] = {}
    
    def get_or_create(self, symbol: str) -> OrderBook:
        """Get or create order book for symbol."""
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol, self.max_depth)
        return self.order_books[symbol]
    
    def get(self, symbol: str) -> Optional[OrderBook]:
        """Get order book for symbol."""
        return self.order_books.get(symbol)
    
    def update_snapshot(self, symbol: str, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]]):
        """Update order book snapshot."""
        order_book = self.get_or_create(symbol)
        order_book.update_snapshot(bids, asks)
    
    def update_level(self, symbol: str, side: str, price: float, quantity: float):
        """Update order book level."""
        order_book = self.get_or_create(symbol)
        order_book.update_level(side, price, quantity)
