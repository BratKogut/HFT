"""
Simple Integrated Trading Engine

Simplified version that focuses on integration of hardening modules
without complex strategy dependencies.

Demonstrates:
- L0 Sanitizer (data validation)
- DRB-Guard (risk management)
- WAL Logger (logging)
- Reason Codes (decision tracking)
- TCA Analyzer (cost analysis)
- Event Bus (metrics)
- Deterministic Fee Model (realistic costs)

Simple strategy: Buy when price dips, sell when it rises
(Just for demonstration - real strategies come later)
"""

import time
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.l0_sanitizer import L0Sanitizer, ValidationAction
from core.drb_guard import DRBGuard, Position, RiskAction
from core.wal_logger import WALLogger
from core.reason_codes import ReasonCode, ReasonCodeTracker
from core.tca_analyzer import TCAAnalyzer, OrderSide, OrderType
from core.deterministic_fee_model import DeterministicFeeModel, Exchange
from core.event_bus import EventBus, Event, EventType

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EngineState(str, Enum):
    """Engine state"""
    IDLE = 'idle'
    RUNNING = 'running'
    FROZEN = 'frozen'
    STOPPED = 'stopped'


@dataclass
class EngineConfig:
    """Engine configuration"""
    initial_capital: float = 10000.0
    exchange: Exchange = Exchange.BINANCE
    max_position_loss_pct: float = 5.0
    max_total_loss_pct: float = 10.0
    max_drawdown_pct: float = 15.0
    max_latency_ms: float = 100.0
    max_data_age_sec: float = 2.0
    max_spread_bps: float = 50.0
    wal_log_path: str = 'logs/wal.jsonl'
    paper_trading: bool = True


class SimpleIntegratedEngine:
    """
    Simple Integrated Trading Engine
    
    Demonstrates integration of all hardening modules
    with a simple trading strategy.
    """
    
    def __init__(self, config: EngineConfig):
        self.config = config
        self.state = EngineState.IDLE
        
        logger.info("="*80)
        logger.info("🚀 Initializing Simple Integrated Trading Engine...")
        logger.info("="*80)
        
        # Initialize hardening components
        self.l0_sanitizer = L0Sanitizer(
            max_latency_ms=config.max_latency_ms,
            max_data_age_sec=config.max_data_age_sec,
            max_spread_bps=config.max_spread_bps
        )
        logger.info("✅ L0 Sanitizer initialized")
        
        self.drb_guard = DRBGuard(
            initial_capital=config.initial_capital,
            max_position_loss_pct=config.max_position_loss_pct,
            max_total_loss_pct=config.max_total_loss_pct,
            max_drawdown_pct=config.max_drawdown_pct
        )
        logger.info("✅ DRB-Guard initialized")
        
        self.wal_logger = WALLogger(config.wal_log_path)
        logger.info("✅ WAL Logger initialized")
        
        self.reason_tracker = ReasonCodeTracker()
        logger.info("✅ Reason Code Tracker initialized")
        
        self.tca_analyzer = TCAAnalyzer()
        logger.info("✅ TCA Analyzer initialized")
        
        self.fee_model = DeterministicFeeModel(exchange=config.exchange)
        logger.info("✅ Deterministic Fee Model initialized")
        
        self.event_bus = EventBus()
        logger.info("✅ Event Bus initialized")
        
        # State
        self.current_position: Optional[Position] = None
        self.order_id_counter = 0
        self.last_price = 0.0
        
        # Statistics
        self.total_ticks = 0
        self.valid_ticks = 0
        self.rejected_ticks = 0
        self.frozen_count = 0
        self.signals_generated = 0
        self.orders_placed = 0
        self.fills = 0
        
        logger.info("="*80)
        logger.info("✅ Simple Integrated Engine Ready!")
        logger.info("="*80)
    
    def start(self):
        """Start engine"""
        if self.state != EngineState.IDLE:
            logger.warning(f"Engine already in state: {self.state}")
            return
        
        self.state = EngineState.RUNNING
        
        self.wal_logger.log_state_change(
            event_id='engine_start',
            old_state='IDLE',
            new_state='RUNNING',
            reason='Engine started'
        )
        
        self.event_bus.publish(Event(
            event_type=EventType.STATE_CHANGE,
            event_id='engine_start',
            data={'state': 'RUNNING'}
        ))
        
        logger.info("✅ Engine STARTED")
    
    def stop(self):
        """Stop engine"""
        self.state = EngineState.STOPPED
        
        self.wal_logger.log_state_change(
            event_id='engine_stop',
            old_state='RUNNING',
            new_state='STOPPED',
            reason='Engine stopped'
        )
        
        self.wal_logger.close()
        
        logger.info("✅ Engine STOPPED")
    
    def on_market_data(self, market_data: Dict) -> Optional[Dict]:
        """Process market data tick"""
        self.total_ticks += 1
        
        # Publish market data event
        self.event_bus.publish(Event(
            event_type=EventType.MARKET_DATA,
            event_id=f'md_{self.total_ticks}',
            data=market_data
        ))
        
        # Step 1: L0 Sanitizer - Validate data
        validation = self.l0_sanitizer.validate(market_data)
        
        # Debug: Log validation result
        if self.total_ticks <= 3:
            logger.info(f"Validation: {validation}")
        
        if validation.action == ValidationAction.FREEZE:
            self.frozen_count += 1
            self._freeze(validation.reason)
            return None
        
        if validation.action == ValidationAction.REJECT:
            self.rejected_ticks += 1
            return None
        
        if validation.action == ValidationAction.SKIP:
            return None
        
        # Data is valid
        self.valid_ticks += 1
        
        # Step 2: Simple strategy - Generate signal
        signal = self._generate_simple_signal(market_data)
        
        if not signal:
            return None
        
        self.signals_generated += 1
        
        # Publish signal event
        self.event_bus.publish(Event(
            event_type=EventType.SIGNAL,
            event_id=f'signal_{self.signals_generated}',
            data=signal
        ))
        
        # Step 3: DRB-Guard - Check risk
        risk_check = self.drb_guard.check_risk()
        
        self.wal_logger.log_risk_check(
            event_id=f'risk_{self.total_ticks}',
            action=risk_check.action.value,
            reason=risk_check.reason,
            data={
                'utilization_pct': risk_check.utilization_pct,
                'current_risk': risk_check.current_risk,
                'limit': risk_check.limit
            }
        )
        
        if risk_check.action == RiskAction.FREEZE:
            self._freeze(risk_check.reason)
            return None
        
        if risk_check.action in [RiskAction.CLOSE, RiskAction.REDUCE]:
            logger.warning(f"Risk action: {risk_check.action.value} - {risk_check.reason}")
            return None
        
        # Step 4: Execute signal
        return self._execute_signal(signal, market_data)
    
    def _generate_simple_signal(self, market_data: Dict) -> Optional[Dict]:
        """
        Simple strategy: Buy dips, sell rallies
        
        This is just for demonstration!
        Real strategies (liquidation hunting, etc.) come later.
        """
        price = market_data.get('price', (market_data['bid'] + market_data['ask']) / 2)
        
        # Skip first tick (need previous price)
        if self.last_price == 0:
            self.last_price = price
            return None
        
        # Calculate price change
        price_change_pct = ((price - self.last_price) / self.last_price) * 100
        
        # Update last price
        self.last_price = price
        
        # Simple rules:
        # - Buy if price dropped > 0.01%
        # - Sell if price rose > 0.01%
        
        if price_change_pct < -0.01 and self.current_position is None:
            return {
                'side': 'buy',
                'reason': f'Price dip: {price_change_pct:.2f}%',
                'confidence': 0.6
            }
        
        if price_change_pct > 0.01 and self.current_position is None:
            return {
                'side': 'sell',
                'reason': f'Price rally: {price_change_pct:.2f}%',
                'confidence': 0.6
            }
        
        return None
    
    def _execute_signal(self, signal: Dict, market_data: Dict) -> Dict:
        """Execute trading signal"""
        self.order_id_counter += 1
        order_id = f'order_{self.order_id_counter}'
        
        symbol = market_data['symbol']
        side = OrderSide.BUY if signal['side'] == 'buy' else OrderSide.SELL
        order_type = OrderType.MARKET
        price = market_data.get('price', (market_data['bid'] + market_data['ask']) / 2)
        size = 0.01
        
        # Determine reason code
        reason_code = ReasonCode.SIGNAL_MEDIUM
        
        # Log decision to WAL
        self.wal_logger.log_decision(
            event_id=order_id,
            decision=signal['side'],
            reason_code=reason_code.value,
            data={
                'symbol': symbol,
                'side': side.value,
                'size': size,
                'price': price,
                'confidence': signal['confidence']
            },
            reason_detail=signal['reason']
        )
        
        # Pre-trade TCA estimate
        self.tca_analyzer.estimate_cost(
            order_id=order_id,
            symbol=symbol,
            side=side,
            size=size,
            order_type=order_type,
            reference_price=price
        )
        
        # Simulate fill (paper trading)
        if self.config.paper_trading:
            fill = self.fee_model.simulate_fill(
                order_id=order_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                order_price=price,
                order_size=size
            )
            
            # Post-trade TCA measurement
            self.tca_analyzer.measure_cost(
                order_id=order_id,
                fill_price=fill.fill_price,
                fill_size=fill.fill_size,
                fees=fill.fees_usd,
                execution_time_ms=fill.execution_time_ms
            )
            
            # Log execution to WAL
            self.wal_logger.log_execution(
                event_id=order_id,
                result='filled',
                data={
                    'fill_price': fill.fill_price,
                    'fill_size': fill.fill_size,
                    'fees': fill.fees_usd,
                    'slippage_bps': fill.slippage_bps
                }
            )
            
            # Update position
            self._update_position(symbol, side, fill.fill_size, fill.fill_price)
            
            # Publish fill event
            self.event_bus.publish(Event(
                event_type=EventType.FILL,
                event_id=order_id,
                data={
                    'symbol': symbol,
                    'side': side.value,
                    'fill_price': fill.fill_price,
                    'fill_size': fill.fill_size,
                    'fees': fill.fees_usd
                }
            ))
            
            # Track reason code
            self.reason_tracker.record_decision(
                reason_code=reason_code,
                action=signal['side'],
                outcome='pending'  # Will update later
            )
            
            self.fills += 1
            
            logger.info(f"✅ Order filled: {fill}")
            
            return {'order_id': order_id, 'fill': fill}
        
        self.orders_placed += 1
        return {'order_id': order_id}
    
    def _update_position(self, symbol: str, side: OrderSide, size: float, price: float):
        """Update position after fill"""
        if self.current_position is None:
            self.current_position = Position(
                symbol=symbol,
                side='long' if side == OrderSide.BUY else 'short',
                size=size,
                entry_price=price,
                current_price=price
            )
            
            # Update DRB-Guard
            self.drb_guard.update_position(self.current_position)
    
    def _freeze(self, reason: str):
        """Freeze engine"""
        if self.state == EngineState.FROZEN:
            return
        
        old_state = self.state
        self.state = EngineState.FROZEN
        
        self.wal_logger.log_state_change(
            event_id=f'freeze_{self.frozen_count}',
            old_state=old_state.value,
            new_state='FROZEN',
            reason=reason
        )
        
        logger.error(f"🛑 ENGINE FROZEN: {reason}")
    
    def get_stats(self) -> Dict:
        """Get engine statistics"""
        return {
            'state': self.state.value,
            'total_ticks': self.total_ticks,
            'valid_ticks': self.valid_ticks,
            'rejected_ticks': self.rejected_ticks,
            'frozen_count': self.frozen_count,
            'validation_rate': (self.valid_ticks / self.total_ticks * 100) if self.total_ticks > 0 else 0,
            'signals_generated': self.signals_generated,
            'orders_placed': self.orders_placed,
            'fills': self.fills,
            'drb_summary': self.drb_guard.get_portfolio_summary(),
            'tca_summary': self.tca_analyzer.get_summary(),
            'event_bus_summary': self.event_bus.get_summary()
        }


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("🚀 SIMPLE INTEGRATED ENGINE - Full System Test")
    print("="*80)
    print()
    
    # Create config
    config = EngineConfig(
        initial_capital=10000.0,
        paper_trading=True
    )
    
    # Create engine
    engine = SimpleIntegratedEngine(config)
    
    # Start
    engine.start()
    
    print()
    print("="*80)
    print("📊 Simulating 100 market ticks...")
    print("="*80)
    
    # Simulate market data
    base_price = 93500.0
    for i in range(100):
        # Simulate price movement
        price_change = (i % 10 - 5) * 10  # Oscillating price
        price = base_price + price_change
        
        # Round to tick size (0.01)
        price = round(price, 2)
        bid = round(price - 2.5, 2)
        ask = round(price + 2.5, 2)
        
        market_data = {
            'symbol': 'BTC/USDT',
            'bid': bid,
            'ask': ask,
            'price': price,
            'volume': 100.0,
            'timestamp': time.time(),
            'exchange_timestamp': time.time() - 0.05
        }
        
        result = engine.on_market_data(market_data)
        
        if result and 'fill' in result:
            print(f"  Tick {i+1}: ✅ {result['fill']}")
    
    # Stop
    engine.stop()
    
    # Get stats
    print()
    print("="*80)
    print("📊 ENGINE STATISTICS")
    print("="*80)
    stats = engine.get_stats()
    
    print(f"State: {stats['state']}")
    print(f"Total ticks: {stats['total_ticks']}")
    print(f"Valid ticks: {stats['valid_ticks']}")
    print(f"Validation rate: {stats['validation_rate']:.1f}%")
    print(f"Signals generated: {stats['signals_generated']}")
    print(f"Fills: {stats['fills']}")
    print()
    
    print("DRB-Guard Summary:")
    drb = stats['drb_summary']
    print(f"  Current equity: ${drb['current_equity']:,.2f}")
    print(f"  Unrealized P&L: ${drb['unrealized_pnl']:+,.2f}")
    print(f"  Drawdown: ${drb['drawdown']:,.2f} ({drb['drawdown_pct']:.2f}%)")
    print()
    
    print("TCA Summary:")
    tca = stats['tca_summary']
    print(f"  Total trades: {tca['total_trades']}")
    print(f"  Avg execution quality: {tca['avg_execution_quality']:.2f}")
    print(f"  Total realized cost: ${tca['total_realized_cost']:,.2f}")
    print()
    
    print("Event Bus Summary:")
    ebs = stats['event_bus_summary']
    print(f"  Total events: {ebs['total_events']}")
    print(f"  Events/sec: {ebs['events_per_sec']:.1f}")
    print(f"  Error rate: {ebs['error_rate_pct']:.2f}%")
    
    print("="*80)
    print("✅ Integration Test Complete!")
    print("="*80)
