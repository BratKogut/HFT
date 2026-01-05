"""Strategy Engine - Trading strategies implementation"""

import asyncio
from typing import Optional, Dict
import uuid
from datetime import datetime

from hft.order_book import OrderBook
from hft.latency_monitor import LatencyMonitor
from models.order import Order, OrderType, OrderSide

class StrategyEngine:
    """Core trading strategy engine
    
    Currently implements:
    - Market Making
    - Order Book Imbalance signals
    """
    
    def __init__(self, settings, latency_monitor: LatencyMonitor):
        self.settings = settings
        self.latency_monitor = latency_monitor
        
        # Strategy parameters
        self.spread_target = settings.market_making_spread  # 0.1%
        self.order_size = settings.market_making_size  # 0.1 BTC
        
        # State
        self.active_orders = {}
        self.last_signal_time = 0
        self.signal_cooldown = 1.0  # 1 second between signals
        
        # Canary mode (safety feature)
        self.canary_mode = True
        self.canary_multiplier = 0.1  # 10% of normal size
        
        # Statistics
        self.signals_generated = 0
        self.orders_placed = 0
    
    async def on_market_data(self, order_book: OrderBook, tick: Dict):
        """Process market data and generate trading signals
        
        This is the main strategy execution path
        """
        start_time = self.latency_monitor.start_timer()
        
        try:
            # Get current market state
            mid_price = order_book.get_mid_price()
            spread = order_book.get_spread()
            imbalance = order_book.get_imbalance()
            
            if mid_price == 0:
                return
            
            # Generate signals
            signals = self._generate_signals(order_book, imbalance)
            
            # Execute strategy based on signals
            if signals:
                await self._execute_market_making(signals, mid_price, spread)
            
            # Record strategy latency
            self.latency_monitor.record("strategy", start_time)
            
        except Exception as e:
            print(f"❌ Error in strategy engine: {e}")
    
    def _generate_signals(self, order_book: OrderBook, imbalance: float) -> Optional[Dict]:
        """Generate trading signals
        
        Uses:
        1. Order book imbalance
        2. Spread analysis
        3. Market making opportunities
        """
        # Check cooldown
        current_time = asyncio.get_event_loop().time()
        if current_time - self.last_signal_time < self.signal_cooldown:
            return None
        
        mid_price = order_book.get_mid_price()
        spread_bps = order_book.get_spread_bps()
        
        # Market making signal: provide liquidity when spread is wide
        if spread_bps > 5.0:  # > 5 basis points
            signal_strength = min(spread_bps / 10.0, 1.0)  # Normalize to 0-1
            
            # Adjust based on imbalance
            buy_signal = signal_strength * (1 + imbalance)  # Stronger buy if buy pressure
            sell_signal = signal_strength * (1 - imbalance)  # Stronger sell if sell pressure
            
            self.last_signal_time = current_time
            self.signals_generated += 1
            
            return {
                "type": "market_making",
                "mid_price": mid_price,
                "buy_signal": buy_signal,
                "sell_signal": sell_signal,
                "imbalance": imbalance,
                "spread_bps": spread_bps
            }
        
        return None
    
    async def _execute_market_making(self, signals: Dict, mid_price: float, current_spread: float):
        """Execute market making strategy
        
        Places limit orders on both sides of the book to capture spread
        """
        try:
            # Calculate order prices
            target_spread = mid_price * self.spread_target
            bid_price = mid_price - target_spread / 2
            ask_price = mid_price + target_spread / 2
            
            # Adjust order size based on signal strength and canary mode
            base_size = self.order_size
            if self.canary_mode:
                base_size *= self.canary_multiplier
            
            buy_size = base_size * signals["buy_signal"]
            sell_size = base_size * signals["sell_signal"]
            
            # Only place orders if signal is strong enough
            if buy_size > 0.01:  # Minimum size threshold
                print(f"🟢 Signal: BUY {buy_size:.4f} @ {bid_price:.2f} (imbalance: {signals['imbalance']:.3f})")
                # In real system, would place order here
                # For now, just log
                self.orders_placed += 1
            
            if sell_size > 0.01:
                print(f"🔴 Signal: SELL {sell_size:.4f} @ {ask_price:.2f} (imbalance: {signals['imbalance']:.3f})")
                # In real system, would place order here
                # For now, just log
                self.orders_placed += 1
            
        except Exception as e:
            print(f"❌ Error executing market making: {e}")
    
    def enable_canary_mode(self):
        """Enable canary mode (10% size for safety)"""
        self.canary_mode = True
        print("✅ Canary mode enabled (10% size)")
    
    def disable_canary_mode(self):
        """Disable canary mode (full size)"""
        self.canary_mode = False
        print("⚠️  Canary mode disabled (full size)")
    
    def get_stats(self) -> Dict:
        """Get strategy statistics"""
        return {
            "signals_generated": self.signals_generated,
            "orders_placed": self.orders_placed,
            "canary_mode": self.canary_mode,
            "spread_target_pct": self.spread_target * 100,
            "order_size": self.order_size,
            "effective_size": self.order_size * (self.canary_multiplier if self.canary_mode else 1.0)
        }
