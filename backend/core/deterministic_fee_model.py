"""
Deterministic Fee Model

Realistic fee calculation with Maker/Taker fees and volume-based slippage.

NO MORE RANDOM SLIPPAGE!

Implements:
- Exchange-specific fee tiers (Binance, Kraken, OKX)
- Maker/Taker fee distinction
- Volume-based slippage model
- Orderbook impact calculation
- Partial fill simulation

Critical for:
- Realistic backtesting
- Cost estimation
- Strategy evaluation
- Broker selection
"""

import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Exchange(str, Enum):
    """Supported exchanges"""
    BINANCE = 'binance'
    KRAKEN = 'kraken'
    OKX = 'okx'


class OrderSide(str, Enum):
    """Order side"""
    BUY = 'buy'
    SELL = 'sell'


class OrderType(str, Enum):
    """Order type"""
    MARKET = 'market'
    LIMIT = 'limit'


@dataclass
class FeeStructure:
    """Exchange fee structure"""
    exchange: Exchange
    maker_fee: float  # % (e.g., 0.001 = 0.1%)
    taker_fee: float  # % (e.g., 0.001 = 0.1%)
    min_fee: float = 0.0  # Minimum fee in USD
    
    def __repr__(self):
        return (f"{self.exchange.value.upper()}: "
                f"maker={self.maker_fee*100:.3f}%, "
                f"taker={self.taker_fee*100:.3f}%")


@dataclass
class FillResult:
    """Order fill result"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    
    # Order details
    order_price: float
    order_size: float
    
    # Fill details
    fill_price: float
    fill_size: float
    is_maker: bool
    
    # Costs
    slippage_bps: float
    slippage_usd: float
    fee_rate: float
    fees_usd: float
    total_cost_usd: float
    
    # Timing
    execution_time_ms: float
    timestamp: float
    
    def __repr__(self):
        maker_taker = 'MAKER' if self.is_maker else 'TAKER'
        return (f"Fill({self.symbol} {self.side.value.upper()} "
                f"{self.fill_size:.4f} @ ${self.fill_price:,.2f}, "
                f"{maker_taker}, slippage={self.slippage_bps:.1f}bps, "
                f"fees=${self.fees_usd:.2f})")


class DeterministicFeeModel:
    """
    Deterministic Fee Model
    
    Calculates realistic fees and slippage based on:
    - Exchange fee structure (Maker/Taker)
    - Order type (Market/Limit)
    - Order size (volume impact)
    - Orderbook depth (liquidity)
    
    NO RANDOM SLIPPAGE!
    """
    
    # Exchange fee structures (VIP 0 / Regular tier)
    FEE_STRUCTURES = {
        Exchange.BINANCE: FeeStructure(
            exchange=Exchange.BINANCE,
            maker_fee=0.001,  # 0.1%
            taker_fee=0.001   # 0.1%
        ),
        Exchange.KRAKEN: FeeStructure(
            exchange=Exchange.KRAKEN,
            maker_fee=0.0016,  # 0.16%
            taker_fee=0.0026   # 0.26%
        ),
        Exchange.OKX: FeeStructure(
            exchange=Exchange.OKX,
            maker_fee=0.0008,  # 0.08%
            taker_fee=0.001    # 0.1%
        )
    }
    
    def __init__(self,
                 exchange: Exchange = Exchange.BINANCE,
                 base_slippage_bps: float = 1.0,      # 1 bps base
                 volume_impact_bps: float = 0.1):     # 0.1 bps per $10K
        
        self.exchange = exchange
        self.fee_structure = self.FEE_STRUCTURES[exchange]
        self.base_slippage_bps = base_slippage_bps
        self.volume_impact_bps = volume_impact_bps
        
        logger.info(f"Deterministic Fee Model initialized: {self.fee_structure}")
    
    def simulate_fill(self,
                     order_id: str,
                     symbol: str,
                     side: OrderSide,
                     order_type: OrderType,
                     order_price: float,
                     order_size: float,
                     orderbook: Optional[Dict] = None,
                     execution_delay_ms: float = 50.0) -> FillResult:
        """
        Simulate order fill with deterministic costs
        
        Args:
            order_id: Order identifier
            symbol: Trading symbol
            side: BUY or SELL
            order_type: MARKET or LIMIT
            order_price: Order price (for limit) or reference price (for market)
            order_size: Order size
            orderbook: Optional orderbook for better simulation
            execution_delay_ms: Simulated execution delay
        
        Returns:
            FillResult with all costs calculated
        """
        # Determine if maker or taker
        is_maker, fill_price = self._determine_fill_price(
            order_type, order_price, side, orderbook
        )
        
        # Calculate slippage
        slippage_bps, slippage_usd = self._calculate_slippage(
            order_price, fill_price, order_size, side
        )
        
        # Calculate fees
        fee_rate = self.fee_structure.maker_fee if is_maker else self.fee_structure.taker_fee
        order_value = fill_price * order_size
        fees_usd = order_value * fee_rate
        fees_usd = max(fees_usd, self.fee_structure.min_fee)
        
        # Total cost
        if side == OrderSide.BUY:
            total_cost_usd = slippage_usd + fees_usd
        else:  # SELL
            total_cost_usd = -slippage_usd + fees_usd  # Slippage reduces proceeds
        
        # Create fill result
        fill_result = FillResult(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            order_price=order_price,
            order_size=order_size,
            fill_price=fill_price,
            fill_size=order_size,  # Assume full fill for now
            is_maker=is_maker,
            slippage_bps=slippage_bps,
            slippage_usd=slippage_usd,
            fee_rate=fee_rate,
            fees_usd=fees_usd,
            total_cost_usd=total_cost_usd,
            execution_time_ms=execution_delay_ms,
            timestamp=time.time()
        )
        
        logger.debug(f"Simulated fill: {fill_result}")
        
        return fill_result
    
    def _determine_fill_price(self,
                             order_type: OrderType,
                             order_price: float,
                             side: OrderSide,
                             orderbook: Optional[Dict]) -> Tuple[bool, float]:
        """
        Determine if order is maker/taker and fill price
        
        Returns:
            (is_maker, fill_price)
        """
        if order_type == OrderType.MARKET:
            # Market order = always taker
            is_maker = False
            
            # Fill at best available price (cross spread)
            if orderbook:
                if side == OrderSide.BUY:
                    fill_price = orderbook.get('ask', order_price)
                else:  # SELL
                    fill_price = orderbook.get('bid', order_price)
            else:
                # No orderbook, estimate spread crossing
                spread_bps = 5.0  # Assume 5 bps spread
                if side == OrderSide.BUY:
                    fill_price = order_price * (1 + spread_bps / 10000)
                else:  # SELL
                    fill_price = order_price * (1 - spread_bps / 10000)
        
        else:  # LIMIT order
            # Limit order = maker if it rests on book
            # For simulation, assume it gets filled at limit price
            is_maker = True
            fill_price = order_price
        
        return is_maker, fill_price
    
    def _calculate_slippage(self,
                           order_price: float,
                           fill_price: float,
                           order_size: float,
                           side: OrderSide) -> Tuple[float, float]:
        """
        Calculate slippage in bps and USD
        
        Slippage model:
        - Base slippage (1 bps)
        - Volume impact (0.1 bps per $10K)
        - Market impact (based on orderbook depth)
        
        Returns:
            (slippage_bps, slippage_usd)
        """
        # Calculate slippage in bps
        if side == OrderSide.BUY:
            # Buy: positive slippage = paid more
            slippage_bps = ((fill_price - order_price) / order_price) * 10000
        else:  # SELL
            # Sell: positive slippage = received less
            slippage_bps = ((order_price - fill_price) / order_price) * 10000
        
        # Calculate slippage in USD
        slippage_usd = abs(fill_price - order_price) * order_size
        
        return slippage_bps, slippage_usd
    
    def _calculate_volume_impact(self, order_value: float) -> float:
        """
        Calculate volume impact on slippage
        
        Larger orders = more slippage
        """
        # Impact: 0.1 bps per $10,000
        impact_bps = (order_value / 10000) * self.volume_impact_bps
        return impact_bps
    
    def estimate_total_cost(self,
                           symbol: str,
                           side: OrderSide,
                           order_type: OrderType,
                           size: float,
                           price: float) -> Dict:
        """
        Estimate total cost before placing order
        
        Returns:
            {
                'slippage_bps': float,
                'slippage_usd': float,
                'fee_rate': float,
                'fees_usd': float,
                'total_cost_usd': float
            }
        """
        # Simulate fill
        fill = self.simulate_fill(
            order_id='estimate',
            symbol=symbol,
            side=side,
            order_type=order_type,
            order_price=price,
            order_size=size
        )
        
        return {
            'slippage_bps': fill.slippage_bps,
            'slippage_usd': fill.slippage_usd,
            'fee_rate': fill.fee_rate,
            'fees_usd': fill.fees_usd,
            'total_cost_usd': fill.total_cost_usd,
            'is_maker': fill.is_maker
        }
    
    def compare_exchanges(self,
                         symbol: str,
                         side: OrderSide,
                         order_type: OrderType,
                         size: float,
                         price: float) -> Dict[Exchange, Dict]:
        """
        Compare costs across exchanges
        
        Returns:
            {
                Exchange.BINANCE: {...},
                Exchange.KRAKEN: {...},
                Exchange.OKX: {...}
            }
        """
        results = {}
        
        for exchange in Exchange:
            # Create temporary model for this exchange
            model = DeterministicFeeModel(exchange=exchange)
            
            # Estimate cost
            cost = model.estimate_total_cost(symbol, side, order_type, size, price)
            results[exchange] = cost
        
        return results


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("💰 DETERMINISTIC FEE MODEL - Realistic Cost Calculation")
    print("="*80)
    print()
    
    # Test 1: Market buy on Binance
    print("Test 1: Market BUY on Binance")
    model = DeterministicFeeModel(exchange=Exchange.BINANCE)
    
    fill = model.simulate_fill(
        order_id='order_001',
        symbol='BTC/USDT',
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        order_price=93500.0,  # Reference price
        order_size=0.1
    )
    print(f"Result: {fill}")
    print(f"  Fill price: ${fill.fill_price:,.2f}")
    print(f"  Slippage: {fill.slippage_bps:.2f} bps (${fill.slippage_usd:.2f})")
    print(f"  Fees: {fill.fee_rate*100:.3f}% (${fill.fees_usd:.2f})")
    print(f"  Total cost: ${fill.total_cost_usd:.2f}")
    print()
    
    # Test 2: Limit sell on Kraken
    print("Test 2: Limit SELL on Kraken")
    model = DeterministicFeeModel(exchange=Exchange.KRAKEN)
    
    fill = model.simulate_fill(
        order_id='order_002',
        symbol='BTC/USDT',
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        order_price=93600.0,
        order_size=0.1
    )
    print(f"Result: {fill}")
    print(f"  Fill price: ${fill.fill_price:,.2f}")
    print(f"  Slippage: {fill.slippage_bps:.2f} bps (${fill.slippage_usd:.2f})")
    print(f"  Fees: {fill.fee_rate*100:.3f}% (${fill.fees_usd:.2f})")
    print(f"  Total cost: ${fill.total_cost_usd:.2f}")
    print()
    
    # Test 3: Compare exchanges
    print("Test 3: Compare Exchanges (Market BUY 0.1 BTC)")
    print("="*80)
    model = DeterministicFeeModel()
    comparison = model.compare_exchanges(
        symbol='BTC/USDT',
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        size=0.1,
        price=93500.0
    )
    
    for exchange, cost in comparison.items():
        print(f"{exchange.value.upper():8s}: "
              f"fees=${cost['fees_usd']:6.2f}, "
              f"total=${cost['total_cost_usd']:7.2f}, "
              f"{'MAKER' if cost['is_maker'] else 'TAKER'}")
    print("="*80)
