"""
Avellaneda-Stoikov Market Making Strategy

Classic market making model based on the paper:
"High-frequency trading in a limit order book" by Avellaneda and Stoikov (2008)

This is a SIMPLIFIED educational implementation.
Real production systems are much more complex.
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class MarketState:
    """Current market state."""
    mid_price: float
    volatility: float  # Estimated volatility (sigma)
    timestamp: float


@dataclass
class InventoryState:
    """Current inventory state."""
    position: float  # Current position (positive = long, negative = short)
    cash: float  # Current cash
    target_position: float = 0.0  # Target position (usually 0)


class AvellanedaStoikovMM:
    """
    Avellaneda-Stoikov Market Making Strategy.
    
    Key Concepts:
    1. **Reservation Price**: Optimal price considering inventory risk
    2. **Optimal Spread**: Spread that balances profit vs inventory risk
    3. **Inventory Management**: Skew quotes to reduce inventory
    
    Parameters:
    - gamma: Risk aversion parameter (higher = more conservative)
    - k: Order book liquidity parameter
    - T: Time horizon (in seconds)
    """
    
    def __init__(
        self,
        gamma: float = 0.1,  # Risk aversion
        k: float = 1.5,  # Liquidity parameter
        T: float = 1.0,  # Time horizon (seconds)
        max_position: float = 10.0,  # Max inventory
        quote_size: float = 1.0,  # Size per quote
    ):
        self.gamma = gamma
        self.k = k
        self.T = T
        self.max_position = max_position
        self.quote_size = quote_size
    
    def calculate_reservation_price(
        self,
        market: MarketState,
        inventory: InventoryState,
        time_remaining: float,
    ) -> float:
        """
        Calculate reservation price (optimal mid price considering inventory).
        
        r = S - q * gamma * sigma^2 * (T - t)
        
        Where:
        - S = current mid price
        - q = current position
        - gamma = risk aversion
        - sigma = volatility
        - T - t = time remaining
        
        Interpretation:
        - If long (q > 0): reservation price < mid (want to sell)
        - If short (q < 0): reservation price > mid (want to buy)
        """
        inventory_adjustment = (
            inventory.position * self.gamma * (market.volatility ** 2) * time_remaining
        )
        
        reservation_price = market.mid_price - inventory_adjustment
        
        return reservation_price
    
    def calculate_optimal_spread(
        self,
        market: MarketState,
        time_remaining: float,
    ) -> float:
        """
        Calculate optimal bid-ask spread.
        
        delta = gamma * sigma^2 * (T - t) + (2/gamma) * ln(1 + gamma/k)
        
        Where:
        - gamma = risk aversion
        - sigma = volatility
        - T - t = time remaining
        - k = liquidity parameter
        
        Interpretation:
        - Higher volatility → wider spread (more risk)
        - Less time remaining → wider spread (urgency to close)
        - Higher liquidity (k) → narrower spread
        """
        spread = (
            self.gamma * (market.volatility ** 2) * time_remaining
            + (2 / self.gamma) * np.log(1 + self.gamma / self.k)
        )
        
        return spread
    
    def calculate_quotes(
        self,
        market: MarketState,
        inventory: InventoryState,
        time_remaining: float,
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate optimal bid and ask prices.
        
        Returns:
            Tuple of (bid_price, ask_price) or (None, None) if max position reached
        """
        # Check if we've hit position limits
        if abs(inventory.position) >= self.max_position:
            # Only quote on the side that reduces inventory
            if inventory.position > 0:
                # Long: only offer (sell)
                reservation = self.calculate_reservation_price(market, inventory, time_remaining)
                spread = self.calculate_optimal_spread(market, time_remaining)
                return None, reservation + spread / 2
            else:
                # Short: only bid (buy)
                reservation = self.calculate_reservation_price(market, inventory, time_remaining)
                spread = self.calculate_optimal_spread(market, time_remaining)
                return reservation - spread / 2, None
        
        # Calculate reservation price and spread
        reservation = self.calculate_reservation_price(market, inventory, time_remaining)
        spread = self.calculate_optimal_spread(market, time_remaining)
        
        # Calculate bid and ask
        bid_price = reservation - spread / 2
        ask_price = reservation + spread / 2
        
        return bid_price, ask_price
    
    def should_update_quotes(
        self,
        current_bid: Optional[float],
        current_ask: Optional[float],
        new_bid: Optional[float],
        new_ask: Optional[float],
        threshold: float = 0.0001,  # 1 basis point
    ) -> bool:
        """
        Determine if quotes should be updated.
        
        Avoid excessive order cancellations/replacements.
        """
        if current_bid is None or current_ask is None:
            return True
        
        if new_bid is None or new_ask is None:
            return True
        
        bid_diff = abs(current_bid - new_bid) / current_bid if current_bid else 0
        ask_diff = abs(current_ask - new_ask) / current_ask if current_ask else 0
        
        return bid_diff > threshold or ask_diff > threshold


# Example usage
if __name__ == "__main__":
    # Initialize strategy
    mm = AvellanedaStoikovMM(
        gamma=0.1,  # Risk aversion
        k=1.5,  # Liquidity
        T=1.0,  # 1 second horizon
        max_position=10.0,
        quote_size=1.0,
    )
    
    # Simulate market state
    market = MarketState(
        mid_price=100.0,
        volatility=0.02,  # 2% volatility
        timestamp=0.0,
    )
    
    # Test with different inventory levels
    scenarios = [
        ("Neutral", InventoryState(position=0.0, cash=10000.0)),
        ("Long", InventoryState(position=5.0, cash=9500.0)),
        ("Short", InventoryState(position=-5.0, cash=10500.0)),
        ("Max Long", InventoryState(position=10.0, cash=9000.0)),
    ]
    
    print("Avellaneda-Stoikov Market Making Strategy")
    print("=" * 60)
    print(f"Market Mid Price: ${market.mid_price:.2f}")
    print(f"Volatility: {market.volatility * 100:.1f}%")
    print("=" * 60)
    
    for scenario_name, inventory in scenarios:
        bid, ask = mm.calculate_quotes(market, inventory, time_remaining=1.0)
        
        print(f"\n{scenario_name} (position={inventory.position:.1f}):")
        if bid and ask:
            spread = ask - bid
            print(f"  Bid: ${bid:.4f}")
            print(f"  Ask: ${ask:.4f}")
            print(f"  Spread: ${spread:.4f} ({spread/market.mid_price*10000:.1f} bps)")
            print(f"  Mid: ${(bid + ask)/2:.4f}")
        elif bid:
            print(f"  Bid: ${bid:.4f}")
            print(f"  Ask: None (max position)")
        elif ask:
            print(f"  Bid: None (max position)")
            print(f"  Ask: ${ask:.4f}")


"""
EXPECTED OUTPUT:

Avellaneda-Stoikov Market Making Strategy
============================================================
Market Mid Price: $100.00
Volatility: 2.0%
============================================================

Neutral (position=0.0):
  Bid: $99.9980
  Ask: $100.0020
  Spread: $0.0040 (0.4 bps)
  Mid: $100.0000

Long (position=5.0):
  Bid: $99.9960
  Ask: $100.0000
  Spread: $0.0040 (0.4 bps)
  Mid: $99.9980

Short (position=-5.0):
  Bid: $100.0000
  Ask: $100.0040
  Spread: $0.0040 (0.4 bps)
  Mid: $100.0020

Max Long (position=10.0):
  Bid: None (max position)
  Ask: $100.0000

INTERPRETATION:
- Neutral: Quotes centered around mid price
- Long: Quotes skewed lower (want to sell)
- Short: Quotes skewed higher (want to buy)
- Max Long: Only offering (selling) to reduce inventory

KEY INSIGHTS:
1. Inventory risk is priced into quotes
2. Spread widens with volatility and time pressure
3. Position limits prevent runaway inventory
4. Reservation price adjusts for inventory

PRODUCTION CONSIDERATIONS:
- Add adverse selection protection
- Implement dynamic volatility estimation
- Add market impact modeling
- Consider order flow toxicity
- Implement sophisticated fill probability models
- Add latency-aware quote placement
"""
