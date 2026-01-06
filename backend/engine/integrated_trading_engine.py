"""
Integrated Trading Engine

Combines all hardening modules with trading strategies.

Components:
- L0 Sanitizer (data validation)
- Signal Manager (strategy selection)
- DRB-Guard (risk management)
- WAL Logger (logging)
- Reason Codes (decision tracking)
- TCA Analyzer (cost analysis)
- Event Bus (metrics)

Flow:
1. Market data → L0 Sanitizer → validate
2. Valid data → Strategies → generate signals
3. Signals → Signal Manager → select best
4. Best signal → DRB-Guard → check risk
5. Risk OK → Execute order → Log decision
6. Fill → TCA → measure cost
7. Update position → Track P&L
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

from strategies.signal_manager import SignalManager, TradingSignal
from strategies.liquidation_hunter_v2 import LiquidationHunterV2
from strategies.volatility_spike_fader import VolatilitySpikeFader
from strategies.trend_filter import TrendFilter

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
    # Capital
    initial_capital: float = 10000.0
    
    # Exchange
    exchange: Exchange = Exchange.BINANCE
    
    # Risk limits
    max_position_loss_pct: float = 5.0
    max_total_loss_pct: float = 10.0
    max_drawdown_pct: float = 15.0
    
    # L0 Sanitizer
    max_latency_ms: float = 100.0
    max_data_age_sec: float = 2.0
    max_spread_bps: float = 50.0
    
    # Logging
    wal_log_path: str = 'logs/wal.jsonl'
    
    # Paper trading
    paper_trading: bool = True


class IntegratedTradingEngine:
    """
    Integrated Trading Engine
    
    Production-ready trading engine with all hardening modules.
    
    Usage:
        config = EngineConfig(
            initial_capital=10000.0,
            paper_trading=True
        )
        
        engine = IntegratedTradingEngine(config)
        engine.start()
        
        # Process market data
        engine.on_market_data(market_data)
        
        # Stop
        engine.stop()
    """
    
    def __init__(self, config: EngineConfig):
        self.config = config
        self.state = EngineState.IDLE
        
        # Initialize components
        logger.info("Initializing Integrated Trading Engine...")
        
        # L0 Sanitizer
        self.l0_sanitizer = L0Sanitizer(
            max_latency_ms=config.max_latency_ms,
            max_data_age_sec=config.max_data_age_sec,
            max_spread_bps=config.max_spread_bps
        )
        logger.info("✅ L0 Sanitizer initialized")
        
        # DRB-Guard
        self.drb_guard = DRBGuard(
            initial_capital=config.initial_capital,
            max_position_loss_pct=config.max_position_loss_pct,
            max_total_loss_pct=config.max_total_loss_pct,
            max_drawdown_pct=config.max_drawdown_pct
        )
        logger.info("✅ DRB-Guard initialized")
        
        # WAL Logger
        self.wal_logger = WALLogger(config.wal_log_path)
        logger.info("✅ WAL Logger initialized")
        
        # Reason Code Tracker
        self.reason_tracker = ReasonCodeTracker()
        logger.info("✅ Reason Code Tracker initialized")
        
        # TCA Analyzer
        self.tca_analyzer = TCAAnalyzer()
        logger.info("✅ TCA Analyzer initialized")
        
        # Fee Model
        self.fee_model = DeterministicFeeModel(exchange=config.exchange)
        logger.info("✅ Deterministic Fee Model initialized")
        
        # Event Bus
        self.event_bus = EventBus()
        logger.info("✅ Event Bus initialized")
        
        # Strategies
        self.trend_filter = TrendFilter()
        self.liquidation_hunter = LiquidationHunterV2()
        self.volatility_fader = VolatilitySpikeFader()
        
        self.signal_manager = SignalManager()
        self.signal_manager.add_strategy('liquidation_hunter', self.liquidation_hunter)
        self.signal_manager.add_strategy('volatility_fader', self.volatility_fader)
        logger.info("✅ Signal Manager initialized with 2 strategies")
        
        # State
        self.current_position: Optional[Position] = None
        self.order_id_counter = 0
        
        # Statistics
        self.total_ticks = 0
        self.valid_ticks = 0
        self.rejected_ticks = 0
        self.frozen_count = 0
        self.signals_generated = 0
        self.orders_placed = 0
        self.fills = 0
        
        logger.info("🚀 Integrated Trading Engine initialized!")
    
    def start(self):
        """Start engine"""
        if self.state != EngineState.IDLE:
            logger.warning(f"Engine already in state: {self.state}")
            return
        
        self.state = EngineState.RUNNING
        
        # Log state change
        self.wal_logger.log_state_change(
            event_id='engine_start',
            old_state='IDLE',
            new_state='RUNNING',
            reason='Engine started'
        )
        
        # Publish event
        self.event_bus.publish(Event(
            event_type=EventType.STATE_CHANGE,
            event_id='engine_start',
            data={'state': 'RUNNING'}
        ))
        
        logger.info("✅ Engine STARTED")
    
    def stop(self):
        """Stop engine"""
        self.state = EngineState.STOPPED
        
        # Log state change
        self.wal_logger.log_state_change(
            event_id='engine_stop',
            old_state='RUNNING',
            new_state='STOPPED',
            reason='Engine stopped'
        )
        
        # Close WAL
        self.wal_logger.close()
        
        logger.info("✅ Engine STOPPED")
    
    def on_market_data(self, market_data: Dict) -> Optional[Dict]:
        """
        Process market data tick
        
        Returns:
            Order dict if order placed, None otherwise
        """
        self.total_ticks += 1
        
        # Publish market data event
        self.event_bus.publish(Event(
            event_type=EventType.MARKET_DATA,
            event_id=f'md_{self.total_ticks}',
            data=market_data
        ))
        
        # Step 1: L0 Sanitizer
        validation = self.l0_sanitizer.validate(market_data)
        
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
        
        # Step 2: Generate signals
        signals = self.signal_manager.generate_signals(market_data)
        
        if not signals:
            return None
        
        self.signals_generated += len(signals)
        
        # Get best signal
        best_signal = self.signal_manager.select_best_signal(signals)
        
        if not best_signal:
            return None
        
        # Publish signal event
        self.event_bus.publish(Event(
            event_type=EventType.SIGNAL,
            event_id=f'signal_{self.signals_generated}',
            data={
                'side': best_signal.side,
                'confidence': best_signal.confidence,
                'reason': best_signal.reason
            }
        ))
        
        # Step 3: Check risk
        risk_check = self.drb_guard.check_risk()
        
        # Log risk check
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
            # TODO: Handle position reduction/closure
            return None
        
        # Step 4: Make decision
        if best_signal.side in ['buy', 'sell']:
            return self._execute_signal(best_signal, market_data)
        
        return None
    
    def _execute_signal(self, signal: TradingSignal, market_data: Dict) -> Dict:
        """Execute trading signal"""
        self.order_id_counter += 1
        order_id = f'order_{self.order_id_counter}'
        
        # Determine order parameters
        symbol = market_data['symbol']
        side = OrderSide.BUY if signal.side == 'buy' else OrderSide.SELL
        order_type = OrderType.MARKET  # For now, always market
        price = market_data.get('price', (market_data['bid'] + market_data['ask']) / 2)
        size = 0.01  # Fixed size for now (TODO: dynamic sizing)
        
        # Map signal reason to reason code
        reason_code = self._map_reason_to_code(signal.reason)
        
        # Log decision
        self.wal_logger.log_decision(
            event_id=order_id,
            decision=signal.side,
            reason_code=reason_code.value,
            data={
                'symbol': symbol,
                'side': side.value,
                'size': size,
                'price': price,
                'confidence': signal.confidence
            },
            reason_detail=signal.reason
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
        
        # Simulate fill (in paper trading mode)
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
            
            # Log execution
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
            
            self.fills += 1
            
            logger.info(f"✅ Order filled: {fill}")
            
            return {
                'order_id': order_id,
                'fill': fill
            }
        
        self.orders_placed += 1
        return {'order_id': order_id}
    
    def _update_position(self, symbol: str, side: OrderSide, size: float, price: float):
        """Update position after fill"""
        if self.current_position is None:
            # Open new position
            self.current_position = Position(
                symbol=symbol,
                side='long' if side == OrderSide.BUY else 'short',
                size=size,
                entry_price=price,
                current_price=price
            )
        else:
            # TODO: Handle position updates (add/reduce/close)
            pass
        
        # Update DRB-Guard
        if self.current_position:
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
    
    def _map_reason_to_code(self, reason: str) -> ReasonCode:
        """Map signal reason to reason code"""
        reason_lower = reason.lower()
        
        if 'liquidation' in reason_lower:
            return ReasonCode.SIGNAL_LIQUIDATION
        elif 'cvd' in reason_lower:
            return ReasonCode.SIGNAL_CVD
        elif 'volatility' in reason_lower or 'spike' in reason_lower:
            return ReasonCode.SIGNAL_VOLATILITY
        elif 'trend' in reason_lower:
            return ReasonCode.SIGNAL_TREND
        elif 'strong' in reason_lower:
            return ReasonCode.SIGNAL_STRONG
        else:
            return ReasonCode.SIGNAL_MEDIUM
    
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
    print("🚀 INTEGRATED TRADING ENGINE - Full System Test")
    print("="*80)
    print()
    
    # Create config
    config = EngineConfig(
        initial_capital=10000.0,
        paper_trading=True
    )
    
    # Create engine
    engine = IntegratedTradingEngine(config)
    
    # Start
    engine.start()
    
    # Simulate market data
    print("Simulating market data...")
    for i in range(10):
        market_data = {
            'symbol': 'BTC/USDT',
            'bid': 93500.0 + i,
            'ask': 93505.0 + i,
            'price': 93502.5 + i,
            'volume': 100.0,
            'timestamp': time.time(),
            'exchange_timestamp': time.time() - 0.05
        }
        
        result = engine.on_market_data(market_data)
        
        if result:
            print(f"  ✅ Order placed: {result['order_id']}")
    
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
    print(f"Orders placed: {stats['orders_placed']}")
    print(f"Fills: {stats['fills']}")
    print("="*80)
