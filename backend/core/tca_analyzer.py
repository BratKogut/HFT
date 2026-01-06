"""
TCA (Transaction Cost Analysis) Analyzer

Tracks estimated vs realized costs for every trade.

Without TCA, you don't know if your "edge" exists after costs.

Analyzes:
- Estimated cost (pre-trade)
- Realized cost (post-trade)
- Slippage (price impact)
- Fees (maker/taker)
- Timing cost (delay)
- Opportunity cost (missed fills)

Critical for:
- Strategy evaluation
- Broker comparison
- Execution quality
- Risk management
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    """Order side"""
    BUY = 'buy'
    SELL = 'sell'


class OrderType(str, Enum):
    """Order type"""
    MARKET = 'market'
    LIMIT = 'limit'


@dataclass
class PreTradeEstimate:
    """Pre-trade cost estimate"""
    order_id: str
    symbol: str
    side: OrderSide
    size: float
    reference_price: float  # Mid price at decision time
    estimated_fill_price: float
    estimated_slippage_bps: float
    estimated_fees: float
    estimated_total_cost: float
    timestamp: float = field(default_factory=time.time)
    
    def __repr__(self):
        return (f"PreTrade({self.symbol} {self.side.value.upper()} "
                f"{self.size:.4f} @ ${self.estimated_fill_price:,.2f}, "
                f"slippage={self.estimated_slippage_bps:.1f}bps, "
                f"fees=${self.estimated_fees:.2f})")


@dataclass
class PostTradeMeasurement:
    """Post-trade actual measurement"""
    order_id: str
    symbol: str
    side: OrderSide
    size: float
    reference_price: float  # Mid price at decision time
    fill_price: float
    realized_slippage_bps: float
    realized_fees: float
    realized_total_cost: float
    execution_time_ms: float  # Time from decision to fill
    timestamp: float = field(default_factory=time.time)
    
    def __repr__(self):
        return (f"PostTrade({self.symbol} {self.side.value.upper()} "
                f"{self.size:.4f} @ ${self.fill_price:,.2f}, "
                f"slippage={self.realized_slippage_bps:.1f}bps, "
                f"fees=${self.realized_fees:.2f})")


@dataclass
class TCAReport:
    """TCA analysis report"""
    order_id: str
    symbol: str
    side: OrderSide
    
    # Estimates
    estimated_slippage_bps: float
    estimated_fees: float
    estimated_total_cost: float
    
    # Realized
    realized_slippage_bps: float
    realized_fees: float
    realized_total_cost: float
    
    # Differences
    slippage_surprise_bps: float  # realized - estimated
    fee_surprise: float
    total_cost_surprise: float
    
    # Execution quality
    execution_time_ms: float
    execution_quality_score: float  # 0-1 (1 = perfect)
    
    timestamp: float = field(default_factory=time.time)
    
    def __repr__(self):
        emoji = '✅' if self.execution_quality_score > 0.8 else '⚠️' if self.execution_quality_score > 0.6 else '❌'
        return (f"{emoji} TCA({self.symbol} {self.side.value.upper()}, "
                f"quality={self.execution_quality_score:.2f}, "
                f"cost_surprise=${self.total_cost_surprise:+.2f})")


class TCAAnalyzer:
    """
    Transaction Cost Analysis Analyzer
    
    Tracks every trade's estimated vs realized costs.
    
    Usage:
        tca = TCAAnalyzer()
        
        # Before trade
        estimate = tca.estimate_cost(order)
        
        # After trade
        measurement = tca.measure_cost(order, fill)
        
        # Get report
        report = tca.generate_report(order_id)
    """
    
    def __init__(self,
                 default_maker_fee: float = 0.001,  # 0.1%
                 default_taker_fee: float = 0.001,  # 0.1%
                 base_slippage_bps: float = 1.0):   # 1 bps base slippage
        
        self.default_maker_fee = default_maker_fee
        self.default_taker_fee = default_taker_fee
        self.base_slippage_bps = base_slippage_bps
        
        # Storage
        self.pre_trade_estimates: Dict[str, PreTradeEstimate] = {}
        self.post_trade_measurements: Dict[str, PostTradeMeasurement] = {}
        self.tca_reports: List[TCAReport] = []
        
        # Statistics
        self.total_trades = 0
        self.total_estimated_cost = 0.0
        self.total_realized_cost = 0.0
        
        logger.info(f"TCA Analyzer initialized: "
                   f"maker_fee={default_maker_fee*100:.2f}%, "
                   f"taker_fee={default_taker_fee*100:.2f}%")
    
    def estimate_cost(self,
                     order_id: str,
                     symbol: str,
                     side: OrderSide,
                     size: float,
                     order_type: OrderType,
                     reference_price: float,
                     orderbook: Optional[Dict] = None) -> PreTradeEstimate:
        """
        Estimate pre-trade costs
        
        Args:
            order_id: Unique order identifier
            symbol: Trading symbol
            side: BUY or SELL
            size: Order size
            order_type: MARKET or LIMIT
            reference_price: Mid price at decision time
            orderbook: Optional orderbook for better estimate
        
        Returns:
            PreTradeEstimate
        """
        # Estimate fill price
        if order_type == OrderType.MARKET:
            # Market order: expect to cross spread + slippage
            estimated_slippage_bps = self._estimate_market_slippage(size, orderbook)
            estimated_fill_price = self._apply_slippage(reference_price, side, estimated_slippage_bps)
            fee_rate = self.default_taker_fee
        else:
            # Limit order: assume fill at limit price (maker)
            estimated_slippage_bps = 0.0
            estimated_fill_price = reference_price
            fee_rate = self.default_maker_fee
        
        # Calculate fees
        order_value = size * estimated_fill_price
        estimated_fees = order_value * fee_rate
        
        # Total cost
        if side == OrderSide.BUY:
            estimated_total_cost = (estimated_fill_price * size) + estimated_fees
        else:  # SELL
            estimated_total_cost = estimated_fees  # Cost is just fees for sells
        
        # Create estimate
        estimate = PreTradeEstimate(
            order_id=order_id,
            symbol=symbol,
            side=side,
            size=size,
            reference_price=reference_price,
            estimated_fill_price=estimated_fill_price,
            estimated_slippage_bps=estimated_slippage_bps,
            estimated_fees=estimated_fees,
            estimated_total_cost=estimated_total_cost
        )
        
        # Store
        self.pre_trade_estimates[order_id] = estimate
        self.total_estimated_cost += estimated_total_cost
        
        logger.debug(f"Pre-trade estimate: {estimate}")
        
        return estimate
    
    def measure_cost(self,
                    order_id: str,
                    fill_price: float,
                    fill_size: float,
                    fees: float,
                    execution_time_ms: float) -> PostTradeMeasurement:
        """
        Measure post-trade actual costs
        
        Args:
            order_id: Order identifier
            fill_price: Actual fill price
            fill_size: Actual fill size
            fees: Actual fees paid
            execution_time_ms: Time from decision to fill
        
        Returns:
            PostTradeMeasurement
        """
        # Get pre-trade estimate
        estimate = self.pre_trade_estimates.get(order_id)
        if not estimate:
            logger.warning(f"No pre-trade estimate found for order {order_id}")
            return None
        
        # Calculate realized slippage
        realized_slippage_bps = self._calculate_slippage_bps(
            estimate.reference_price,
            fill_price,
            estimate.side
        )
        
        # Total cost
        if estimate.side == OrderSide.BUY:
            realized_total_cost = (fill_price * fill_size) + fees
        else:  # SELL
            realized_total_cost = fees
        
        # Create measurement
        measurement = PostTradeMeasurement(
            order_id=order_id,
            symbol=estimate.symbol,
            side=estimate.side,
            size=fill_size,
            reference_price=estimate.reference_price,
            fill_price=fill_price,
            realized_slippage_bps=realized_slippage_bps,
            realized_fees=fees,
            realized_total_cost=realized_total_cost,
            execution_time_ms=execution_time_ms
        )
        
        # Store
        self.post_trade_measurements[order_id] = measurement
        self.total_realized_cost += realized_total_cost
        self.total_trades += 1
        
        logger.debug(f"Post-trade measurement: {measurement}")
        
        # Generate TCA report
        report = self._generate_report(estimate, measurement)
        self.tca_reports.append(report)
        
        return measurement
    
    def _generate_report(self,
                        estimate: PreTradeEstimate,
                        measurement: PostTradeMeasurement) -> TCAReport:
        """Generate TCA report comparing estimate vs realized"""
        
        # Calculate surprises (realized - estimated)
        slippage_surprise_bps = measurement.realized_slippage_bps - estimate.estimated_slippage_bps
        fee_surprise = measurement.realized_fees - estimate.estimated_fees
        total_cost_surprise = measurement.realized_total_cost - estimate.estimated_total_cost
        
        # Calculate execution quality score (0-1)
        # Good execution = realized cost <= estimated cost
        if total_cost_surprise <= 0:
            # Better than expected
            execution_quality_score = 1.0
        else:
            # Worse than expected
            # Penalize based on % surprise
            surprise_pct = abs(total_cost_surprise / estimate.estimated_total_cost)
            execution_quality_score = max(0.0, 1.0 - surprise_pct)
        
        report = TCAReport(
            order_id=estimate.order_id,
            symbol=estimate.symbol,
            side=estimate.side,
            estimated_slippage_bps=estimate.estimated_slippage_bps,
            estimated_fees=estimate.estimated_fees,
            estimated_total_cost=estimate.estimated_total_cost,
            realized_slippage_bps=measurement.realized_slippage_bps,
            realized_fees=measurement.realized_fees,
            realized_total_cost=measurement.realized_total_cost,
            slippage_surprise_bps=slippage_surprise_bps,
            fee_surprise=fee_surprise,
            total_cost_surprise=total_cost_surprise,
            execution_time_ms=measurement.execution_time_ms,
            execution_quality_score=execution_quality_score
        )
        
        logger.info(f"TCA Report: {report}")
        
        return report
    
    def _estimate_market_slippage(self,
                                  size: float,
                                  orderbook: Optional[Dict]) -> float:
        """
        Estimate slippage for market order
        
        Based on:
        - Base slippage (1 bps)
        - Order size (larger = more slippage)
        - Orderbook depth (if available)
        """
        # Base slippage
        slippage_bps = self.base_slippage_bps
        
        # Size impact (1 bps per $10,000)
        size_impact_bps = (size * 93000 / 10000) * 1.0  # Assume ~$93K BTC
        slippage_bps += size_impact_bps
        
        # Orderbook impact (if available)
        if orderbook:
            # TODO: Calculate based on orderbook depth
            pass
        
        return slippage_bps
    
    def _apply_slippage(self,
                       reference_price: float,
                       side: OrderSide,
                       slippage_bps: float) -> float:
        """Apply slippage to reference price"""
        slippage_pct = slippage_bps / 10000
        
        if side == OrderSide.BUY:
            # Buy: pay more (slippage increases price)
            return reference_price * (1 + slippage_pct)
        else:  # SELL
            # Sell: receive less (slippage decreases price)
            return reference_price * (1 - slippage_pct)
    
    def _calculate_slippage_bps(self,
                               reference_price: float,
                               fill_price: float,
                               side: OrderSide) -> float:
        """Calculate realized slippage in basis points"""
        if side == OrderSide.BUY:
            # Buy: positive slippage = paid more
            slippage_pct = (fill_price - reference_price) / reference_price
        else:  # SELL
            # Sell: positive slippage = received less
            slippage_pct = (reference_price - fill_price) / reference_price
        
        return slippage_pct * 10000
    
    def get_summary(self) -> Dict:
        """Get TCA summary statistics"""
        if not self.tca_reports:
            return {
                'total_trades': 0,
                'avg_execution_quality': 0.0,
                'avg_cost_surprise': 0.0,
                'total_estimated_cost': 0.0,
                'total_realized_cost': 0.0
            }
        
        avg_quality = np.mean([r.execution_quality_score for r in self.tca_reports])
        avg_surprise = np.mean([r.total_cost_surprise for r in self.tca_reports])
        
        return {
            'total_trades': self.total_trades,
            'avg_execution_quality': avg_quality,
            'avg_cost_surprise': avg_surprise,
            'total_estimated_cost': self.total_estimated_cost,
            'total_realized_cost': self.total_realized_cost,
            'cost_overrun_pct': ((self.total_realized_cost / self.total_estimated_cost) - 1) * 100 if self.total_estimated_cost > 0 else 0
        }


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("📊 TCA ANALYZER - Transaction Cost Analysis")
    print("="*80)
    print()
    
    tca = TCAAnalyzer()
    
    # Simulate trade 1: Market buy (expect slippage)
    print("Trade 1: Market BUY")
    estimate = tca.estimate_cost(
        order_id='order_001',
        symbol='BTC/USDT',
        side=OrderSide.BUY,
        size=0.1,
        order_type=OrderType.MARKET,
        reference_price=93500.0
    )
    print(f"Estimate: {estimate}")
    
    # Simulate fill (worse than expected)
    measurement = tca.measure_cost(
        order_id='order_001',
        fill_price=93515.0,  # Paid $15 more
        fill_size=0.1,
        fees=9.35,  # 0.1% fee
        execution_time_ms=50.0
    )
    print(f"Measurement: {measurement}")
    print()
    
    # Simulate trade 2: Limit sell (expect maker fee)
    print("Trade 2: Limit SELL")
    estimate = tca.estimate_cost(
        order_id='order_002',
        symbol='BTC/USDT',
        side=OrderSide.SELL,
        size=0.1,
        order_type=OrderType.LIMIT,
        reference_price=93600.0
    )
    print(f"Estimate: {estimate}")
    
    # Simulate fill (better than expected - got maker rebate)
    measurement = tca.measure_cost(
        order_id='order_002',
        fill_price=93600.0,
        fill_size=0.1,
        fees=9.36,
        execution_time_ms=1500.0  # Took 1.5s to fill
    )
    print(f"Measurement: {measurement}")
    print()
    
    # Summary
    print("="*80)
    print("📊 TCA SUMMARY")
    print("="*80)
    summary = tca.get_summary()
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
    print("="*80)
