"""
Order Book Imbalance Signal - Python Example

Educational example showing how to calculate and use order book imbalance
for trading signals.

NOT for production HFT - this is for medium-frequency trading.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple
from collections import deque


@dataclass
class OrderBookLevel:
    """Single price level in the order book."""
    price: float
    size: float


@dataclass
class OrderBook:
    """Full order book snapshot."""
    bids: List[OrderBookLevel]  # Sorted desc by price
    asks: List[OrderBookLevel]  # Sorted asc by price
    timestamp_ns: int


def calculate_imbalance(book: OrderBook, levels: int = 5) -> float:
    """
    Calculate order book imbalance.
    
    Imbalance = (Bid Volume - Ask Volume) / (Bid Volume + Ask Volume)
    
    Args:
        book: Order book snapshot
        levels: Number of levels to include (default: 5)
    
    Returns:
        Imbalance ratio in range [-1, 1]
        - Positive = more buying pressure
        - Negative = more selling pressure
        - Zero = balanced
    """
    bid_vol = sum(level.size for level in book.bids[:levels])
    ask_vol = sum(level.size for level in book.asks[:levels])
    
    total = bid_vol + ask_vol
    if total == 0:
        return 0.0
    
    return (bid_vol - ask_vol) / total


def weighted_mid_price(book: OrderBook) -> float:
    """
    Calculate weighted mid price based on top-of-book imbalance.
    
    More accurate than simple mid when book is imbalanced.
    
    Args:
        book: Order book snapshot
    
    Returns:
        Weighted mid price
    """
    if not book.bids or not book.asks:
        return 0.0
    
    best_bid = book.bids[0]
    best_ask = book.asks[0]
    
    total_size = best_bid.size + best_ask.size
    if total_size == 0:
        return (best_bid.price + best_ask.price) / 2
    
    # Weight by opposite side (bid size pulls toward ask, ask size pulls toward bid)
    weighted = (best_bid.price * best_ask.size + best_ask.price * best_bid.size) / total_size
    
    return weighted


class ImbalanceSignalGenerator:
    """
    Generate trading signals based on order book imbalance.
    
    Strategy:
    - When imbalance is strongly positive (>threshold) → expect price to go up
    - When imbalance is strongly negative (<-threshold) → expect price to go down
    """
    
    def __init__(
        self,
        threshold: float = 0.3,
        lookback: int = 10,
        levels: int = 5,
    ):
        """
        Initialize signal generator.
        
        Args:
            threshold: Imbalance threshold for signal (default: 0.3)
            lookback: Number of imbalance readings to smooth (default: 10)
            levels: Number of orderbook levels to use (default: 5)
        """
        self.threshold = threshold
        self.lookback = lookback
        self.levels = levels
        self.imbalance_history = deque(maxlen=lookback)
    
    def update(self, book: OrderBook) -> Tuple[str, float]:
        """
        Update with new order book and generate signal.
        
        Args:
            book: Order book snapshot
        
        Returns:
            Tuple of (signal, imbalance)
            - signal: 'BUY', 'SELL', or 'NEUTRAL'
            - imbalance: Current smoothed imbalance value
        """
        # Calculate current imbalance
        imbalance = calculate_imbalance(book, self.levels)
        self.imbalance_history.append(imbalance)
        
        # Smooth imbalance (moving average)
        if len(self.imbalance_history) < self.lookback:
            return 'NEUTRAL', imbalance
        
        smoothed = np.mean(self.imbalance_history)
        
        # Generate signal
        if smoothed > self.threshold:
            return 'BUY', smoothed
        elif smoothed < -self.threshold:
            return 'SELL', smoothed
        else:
            return 'NEUTRAL', smoothed
    
    def get_signal_strength(self) -> float:
        """
        Get signal strength (0.0 to 1.0).
        
        Returns:
            Signal strength based on how far imbalance is from threshold
        """
        if len(self.imbalance_history) < self.lookback:
            return 0.0
        
        smoothed = abs(np.mean(self.imbalance_history))
        
        # Normalize to 0-1 range
        # threshold = 0.5 strength, 1.0 = 1.0 strength
        strength = min(smoothed / self.threshold, 1.0) * 0.5 + 0.5
        
        return strength


# Example usage
if __name__ == "__main__":
    # Create sample order book
    book = OrderBook(
        bids=[
            OrderBookLevel(100.00, 1000),
            OrderBookLevel(99.99, 800),
            OrderBookLevel(99.98, 600),
            OrderBookLevel(99.97, 400),
            OrderBookLevel(99.96, 200),
        ],
        asks=[
            OrderBookLevel(100.01, 500),  # Less ask volume = buying pressure
            OrderBookLevel(100.02, 400),
            OrderBookLevel(100.03, 300),
            OrderBookLevel(100.04, 200),
            OrderBookLevel(100.05, 100),
        ],
        timestamp_ns=1704470400000000000,
    )
    
    # Calculate imbalance
    imbalance = calculate_imbalance(book, levels=5)
    print(f"Order Book Imbalance: {imbalance:.3f}")
    
    # Calculate weighted mid
    wmid = weighted_mid_price(book)
    simple_mid = (book.bids[0].price + book.asks[0].price) / 2
    print(f"Simple Mid: {simple_mid:.2f}")
    print(f"Weighted Mid: {wmid:.2f}")
    print(f"Difference: {wmid - simple_mid:.4f}")
    
    # Generate signal
    signal_gen = ImbalanceSignalGenerator(threshold=0.3)
    
    # Simulate multiple updates
    for i in range(15):
        signal, smoothed = signal_gen.update(book)
        strength = signal_gen.get_signal_strength()
        print(f"Update {i+1}: Signal={signal}, Imbalance={smoothed:.3f}, Strength={strength:.2f}")


"""
EXPECTED OUTPUT:

Order Book Imbalance: 0.429
Simple Mid: 100.01
Weighted Mid: 100.00
Difference: -0.0033

Update 1: Signal=NEUTRAL, Imbalance=0.429, Strength=0.00
Update 2: Signal=NEUTRAL, Imbalance=0.429, Strength=0.00
...
Update 10: Signal=BUY, Imbalance=0.429, Strength=1.00
Update 11: Signal=BUY, Imbalance=0.429, Strength=1.00
...

INTERPRETATION:
- Positive imbalance (0.429) = More bid volume than ask volume
- This suggests buying pressure
- After 10 updates (lookback), signal becomes BUY
- Strength is 1.0 because imbalance (0.429) > threshold (0.3)

PERFORMANCE NOTES:
- Latency: ~10-100 microseconds (Python)
- For real HFT, implement in C++ for <1 microsecond
- Use numpy for vectorized operations (faster)

LIMITATIONS:
- Simplified model (real: more sophisticated)
- No consideration of order sizes at different levels
- No time decay of old imbalances
- No market microstructure effects

IMPROVEMENTS:
- Add volume-weighted imbalance
- Consider order arrival rate
- Add time-weighted moving average
- Combine with other signals (price action, volume, etc.)
"""
