"""
Production Trading Engine V2 with Position Management
Includes Take Profit and Stop Loss logic
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import time
import numpy as np

from core.l0_sanitizer import L0Sanitizer
from core.drb_guard import DRBGuard, Position
from core.wal_logger import WALLogger
from core.tca_analyzer import TCAAnalyzer
from core.deterministic_fee_model import DeterministicFeeModel, OrderSide, OrderType
from core.event_bus import EventBus, Event, EventType
from strategies.simple_liquidation_hunter import SimpleLiquidationHunter


@dataclass
class OpenPosition:
    """Represents an open position with entry and management parameters"""
    symbol: str
    side: str  # 'BUY' or 'SELL'
    entry_price: float
    quantity: float
    entry_time: datetime
    take_profit: float
    stop_loss: float
    position_id: str
    
    def check_exit(self, current_price: float) -> Optional[str]:
        """Check if position should be closed based on TP/SL"""
        if self.side == 'BUY':
            if current_price >= self.take_profit:
                return 'TAKE_PROFIT'
            elif current_price <= self.stop_loss:
                return 'STOP_LOSS'
        else:  # SELL
            if current_price <= self.take_profit:
                return 'TAKE_PROFIT'
            elif current_price >= self.stop_loss:
                return 'STOP_LOSS'
        return None
    
    def get_pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL"""
        if self.side == 'BUY':
            return (current_price - self.entry_price) * self.quantity
        else:  # SELL
            return (self.entry_price - current_price) * self.quantity


class ProductionEngineV2:
    """
    Production Trading Engine with full position management
    """
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        exchange: str = 'binance',
        symbol: str = 'BTC/USDT'
    ):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.exchange = exchange
        self.symbol = symbol
        
        # Initialize components
        self.l0_sanitizer = L0Sanitizer()
        self.drb_guard = DRBGuard(initial_capital=initial_capital)
        self.wal_logger = WALLogger(log_path='logs/wal/wal.jsonl')
        self.tca_analyzer = TCAAnalyzer()
        self.fee_model = DeterministicFeeModel()
        self.event_bus = EventBus()
        self.strategy = SimpleLiquidationHunter()
        
        # Position management
        self.open_positions: List[OpenPosition] = []
        self.closed_positions: List[Dict] = []
        
        # Statistics
        self.stats = {
            'ticks_processed': 0,
            'ticks_validated': 0,
            'signals_generated': 0,
            'positions_opened': 0,
            'positions_closed': 0,
            'tp_exits': 0,
            'sl_exits': 0,
            'total_pnl': 0.0,
            'winning_trades': 0,
            'losing_trades': 0
        }
        
        print(f"ProductionEngineV2 initialized:")
        print(f"  Capital: ${initial_capital:,.2f}")
        print(f"  Exchange: {exchange}")
        print(f"  Symbol: {symbol}")
    
    def process_tick(self, tick_data: Dict) -> None:
        """Process a single market data tick"""
        self.stats['ticks_processed'] += 1
        
        # Step 1: L0 Sanitizer - Validate data quality
        validation_result = self.l0_sanitizer.validate({
            'symbol': tick_data['symbol'],
            'timestamp': tick_data['timestamp'],
            'bid': tick_data['bid'],
            'ask': tick_data['ask'],
            'exchange_timestamp': tick_data['timestamp']
        })
        
        if not validation_result.valid:
            # Data failed validation, skip this tick
            self.event_bus.publish(Event(
                event_type=EventType.ERROR,
                event_id=f"validation_failed_{tick_data['timestamp']}",
                data={
                    'reason': validation_result.reason,
                    'timestamp': tick_data['timestamp']
                }
            ))
            return
        
        self.stats['ticks_validated'] += 1
        
        # Step 2: Check existing positions for TP/SL
        self._check_position_exits(tick_data)
        
        # Step 3: Generate trading signals (only if we have room for new positions)
        if len(self.open_positions) < 3:  # Max 3 concurrent positions
            signal = self.strategy.analyze(tick_data)
            
            if signal:
                self.stats['signals_generated'] += 1
                
                # Step 4: Risk check with DRB-Guard
                position_size = min(self.capital * 0.02, 1000.0)  # 2% of capital, max $1000
                
                # Create position for risk check
                entry_price = tick_data['bid'] if signal['side'].upper() == 'BUY' else tick_data['ask']
                test_position = Position(
                    symbol=self.symbol,
                    side='long' if signal['side'].upper() == 'BUY' else 'short',
                    size=position_size / entry_price,
                    entry_price=entry_price,
                    current_price=entry_price,
                    entry_time=tick_data['timestamp']
                )
                
                # Check current risk before adding position
                risk_check = self.drb_guard.check_risk()
                
                if risk_check.action == 'allow':
                    # Step 5: Execute trade
                    self._execute_trade(signal, tick_data)
                else:
                    self.event_bus.publish(Event(
                        event_type=EventType.RISK_CHECK,
                        event_id=f"trade_blocked_{tick_data['timestamp']}",
                        data={
                            'reason': risk_check.reason,
                            'timestamp': tick_data['timestamp']
                        }
                    ))
    
    def _check_position_exits(self, tick_data: Dict) -> None:
        """Check if any open positions should be closed"""
        current_price = (tick_data['bid'] + tick_data['ask']) / 2
        
        positions_to_close = []
        
        for position in self.open_positions:
            exit_reason = position.check_exit(current_price)
            
            if exit_reason:
                positions_to_close.append((position, exit_reason))
        
        # Close positions
        for position, reason in positions_to_close:
            self._close_position(position, tick_data, reason)
    
    def _execute_trade(self, signal, tick_data: Dict) -> None:
        """Execute a new trade"""
        # Calculate position size
        position_size = min(self.capital * 0.02, 1000.0)  # 2% of capital, max $1000
        
        # Get entry price
        if signal['side'].upper() == 'BUY':
            entry_price = tick_data['ask']  # Buy at ask
        else:
            entry_price = tick_data['bid']  # Sell at bid
        
        quantity = position_size / entry_price
        
        # Calculate TP/SL
        if signal['side'].upper() == 'BUY':
            take_profit = entry_price * 1.015  # 1.5% profit
            stop_loss = entry_price * 0.99    # 1% loss
        else:
            take_profit = entry_price * 0.985  # 1.5% profit
            stop_loss = entry_price * 1.01    # 1% loss
        
        # Simulate order fill with fees
        order_side = OrderSide.BUY if signal['side'].upper() == 'BUY' else OrderSide.SELL
        fill_result = self.fee_model.simulate_fill(
            order_id=f"ORDER_{len(self.open_positions) + 1}",
            symbol=self.symbol,
            side=order_side,
            order_type=OrderType.MARKET,
            order_price=entry_price,
            order_size=quantity
        )
        
        # Deduct fees from capital
        self.capital -= fill_result.total_cost_usd
        
        # Create open position
        position = OpenPosition(
            symbol=self.symbol,
            side=signal['side'].upper(),
            entry_price=entry_price,
            quantity=quantity,
            entry_time=tick_data['timestamp'],
            take_profit=take_profit,
            stop_loss=stop_loss,
            position_id=f"POS_{len(self.open_positions) + 1}_{tick_data['timestamp']}"
        )
        
        self.open_positions.append(position)
        self.stats['positions_opened'] += 1
        
        # Update DRB-Guard
        drb_position = Position(
            symbol=self.symbol,
            side='long' if signal['side'].upper() == 'BUY' else 'short',
            size=quantity,
            entry_price=entry_price,
            current_price=entry_price,
            entry_time=tick_data['timestamp']
        )
        self.drb_guard.update_position(drb_position)
        
        # Log to WAL
        self.wal_logger.log_decision(
            event_id=position.position_id,
            decision='OPEN_POSITION',
            reason_code='SIGNAL_LIQUIDATION',
            data={
                'side': signal['side'].upper(),
                'entry_price': entry_price,
                'quantity': quantity,
                'take_profit': take_profit,
                'stop_loss': stop_loss,
                'fee': fill_result.total_cost_usd,
                'timestamp': tick_data['timestamp']
            }
        )
        
        # Publish event
        self.event_bus.publish(Event(
            event_type=EventType.FILL,
            event_id=position.position_id,
            data={
                'side': signal['side'].upper(),
                'entry_price': entry_price,
                'quantity': quantity
            }
        ))
    
    def _close_position(self, position: OpenPosition, tick_data: Dict, reason: str) -> None:
        """Close an open position"""
        # Get exit price
        if position.side == 'BUY':
            exit_price = tick_data['bid']  # Sell at bid
        else:
            exit_price = tick_data['ask']  # Buy at ask
        
        # Calculate PnL
        pnl = position.get_pnl(exit_price)
        
        # Simulate order fill with fees
        order_side = OrderSide.SELL if position.side == 'BUY' else OrderSide.BUY
        fill_result = self.fee_model.simulate_fill(
            order_id=f"CLOSE_{position.position_id}",
            symbol=self.symbol,
            side=order_side,
            order_type=OrderType.MARKET,
            order_price=exit_price,
            order_size=position.quantity
        )
        
        # Net PnL after fees
        net_pnl = pnl - fill_result.total_cost_usd
        
        # Update capital
        self.capital += net_pnl
        
        # Update statistics
        self.stats['positions_closed'] += 1
        self.stats['total_pnl'] += net_pnl
        
        if net_pnl > 0:
            self.stats['winning_trades'] += 1
        else:
            self.stats['losing_trades'] += 1
        
        if reason == 'TAKE_PROFIT':
            self.stats['tp_exits'] += 1
        elif reason == 'STOP_LOSS':
            self.stats['sl_exits'] += 1
        
        # Remove from open positions
        self.open_positions.remove(position)
        
        # Add to closed positions
        self.closed_positions.append({
            'position_id': position.position_id,
            'side': position.side,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'quantity': position.quantity,
            'pnl': net_pnl,
            'reason': reason,
            'entry_time': position.entry_time,
            'exit_time': tick_data['timestamp']
        })
        
        # Update DRB-Guard
        self.drb_guard.remove_position(self.symbol, realized_pnl=net_pnl)
        
        # Log to WAL
        self.wal_logger.log_decision(
            event_id=position.position_id,
            decision='CLOSE_POSITION',
            reason_code=f'EXIT_{reason}',
            data={
                'exit_price': exit_price,
                'pnl': net_pnl,
                'timestamp': tick_data['timestamp']
            }
        )
        
        # Publish event
        self.event_bus.publish(Event(
            event_type=EventType.FILL,
            event_id=position.position_id,
            data={
                'pnl': net_pnl,
                'reason': reason
            }
        ))
    
    def get_statistics(self) -> Dict:
        """Get engine statistics"""
        total_trades = self.stats['winning_trades'] + self.stats['losing_trades']
        win_rate = (self.stats['winning_trades'] / total_trades * 100) if total_trades > 0 else 0.0
        
        return_pct = ((self.capital - self.initial_capital) / self.initial_capital) * 100
        
        return {
            'ticks_processed': self.stats['ticks_processed'],
            'ticks_validated': self.stats['ticks_validated'],
            'validation_rate': (self.stats['ticks_validated'] / self.stats['ticks_processed'] * 100) if self.stats['ticks_processed'] > 0 else 0.0,
            'signals_generated': self.stats['signals_generated'],
            'positions_opened': self.stats['positions_opened'],
            'positions_closed': self.stats['positions_closed'],
            'open_positions': len(self.open_positions),
            'tp_exits': self.stats['tp_exits'],
            'sl_exits': self.stats['sl_exits'],
            'winning_trades': self.stats['winning_trades'],
            'losing_trades': self.stats['losing_trades'],
            'win_rate': win_rate,
            'total_pnl': self.stats['total_pnl'],
            'initial_capital': self.initial_capital,
            'current_capital': self.capital,
            'return_pct': return_pct
        }


def test_engine():
    """Test the production engine"""
    print("Testing Production Engine V2...")
    print("=" * 60)
    
    engine = ProductionEngineV2(initial_capital=10000.0)
    
    # Simulate 1000 ticks
    base_price = 93500.0
    
    for i in range(1000):
        # Simulate price movement
        price_change = np.random.normal(0, 50)  # Random walk
        base_price += price_change
        
        # Create tick data
        spread = base_price * 0.0001  # 1 bps spread
        tick = {
            'symbol': 'BTC/USDT',
            'timestamp': time.time(),
            'bid': round(base_price - spread/2, 2),
            'ask': round(base_price + spread/2, 2),
            'bid_volume': 100.0,
            'ask_volume': 100.0
        }
        
        engine.process_tick(tick)
    
    # Get statistics
    stats = engine.get_statistics()
    
    print("\n" + "=" * 60)
    print("ENGINE STATISTICS")
    print("=" * 60)
    print(f"Ticks Processed: {stats['ticks_processed']}")
    print(f"Ticks Validated: {stats['ticks_validated']} ({stats['validation_rate']:.1f}%)")
    print(f"Signals Generated: {stats['signals_generated']}")
    print(f"Positions Opened: {stats['positions_opened']}")
    print(f"Positions Closed: {stats['positions_closed']}")
    print(f"Open Positions: {stats['open_positions']}")
    print(f"\nExit Reasons:")
    print(f"  Take Profit: {stats['tp_exits']}")
    print(f"  Stop Loss: {stats['sl_exits']}")
    print(f"\nPerformance:")
    print(f"  Winning Trades: {stats['winning_trades']}")
    print(f"  Losing Trades: {stats['losing_trades']}")
    print(f"  Win Rate: {stats['win_rate']:.1f}%")
    print(f"  Total PnL: ${stats['total_pnl']:.2f}")
    print(f"  Initial Capital: ${stats['initial_capital']:,.2f}")
    print(f"  Current Capital: ${stats['current_capital']:,.2f}")
    print(f"  Return: {stats['return_pct']:.2f}%")
    print("=" * 60)


if __name__ == '__main__':
    test_engine()
