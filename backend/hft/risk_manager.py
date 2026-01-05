"""Risk Manager - Pre-trade risk checks and limits"""

from typing import Optional, Dict
from datetime import datetime, timedelta
from models.order import Order, OrderSide

class RiskManager:
    """Manage risk controls and pre-trade checks"""
    
    def __init__(self, settings):
        self.settings = settings
        self.daily_pnl = 0.0
        self.daily_pnl_reset_time = datetime.utcnow().replace(hour=0, minute=0, second=0)
        self.kill_switch_active = False
        self.rejected_orders = 0
    
    def check_order(self, order: Order, current_position: float, current_price: float) -> tuple[bool, Optional[str]]:
        """Pre-trade risk checks
        
        Returns: (is_valid, error_message)
        """
        # Check kill switch
        if self.kill_switch_active:
            return False, "Kill switch is active"
        
        # Check max order size
        if order.size > self.settings.max_order_size:
            self.rejected_orders += 1
            return False, f"Order size {order.size} exceeds max {self.settings.max_order_size}"
        
        # Check max position size
        new_position = current_position + (order.size if order.side == OrderSide.BUY else -order.size)
        if abs(new_position) > self.settings.max_position_size:
            self.rejected_orders += 1
            return False, f"Position {new_position} would exceed max {self.settings.max_position_size}"
        
        # Check price collar (fat-finger check)
        price_diff_pct = abs(order.price - current_price) / current_price
        if price_diff_pct > self.settings.price_collar_pct:
            self.rejected_orders += 1
            return False, f"Price {order.price} outside collar (current: {current_price}, max diff: {self.settings.price_collar_pct * 100}%)"
        
        # Check daily loss limit
        self._update_daily_pnl()
        if self.daily_pnl < -abs(self.settings.daily_loss_limit):
            self.activate_kill_switch()
            return False, f"Daily loss limit exceeded: {self.daily_pnl}"
        
        return True, None
    
    def update_pnl(self, pnl_change: float):
        """Update daily PnL"""
        self._update_daily_pnl()
        self.daily_pnl += pnl_change
    
    def _update_daily_pnl(self):
        """Reset daily PnL if new day"""
        now = datetime.utcnow()
        if now.date() > self.daily_pnl_reset_time.date():
            self.daily_pnl = 0.0
            self.daily_pnl_reset_time = now.replace(hour=0, minute=0, second=0)
            if self.kill_switch_active:
                print("✅ New day - deactivating kill switch")
                self.kill_switch_active = False
    
    def activate_kill_switch(self):
        """Activate emergency kill switch"""
        if not self.kill_switch_active:
            self.kill_switch_active = True
            print("❌ KILL SWITCH ACTIVATED!")
    
    def deactivate_kill_switch(self):
        """Manually deactivate kill switch"""
        self.kill_switch_active = False
        print("✅ Kill switch deactivated")
    
    def get_status(self) -> Dict:
        """Get risk status"""
        return {
            "kill_switch_active": self.kill_switch_active,
            "daily_pnl": self.daily_pnl,
            "daily_loss_limit": self.settings.daily_loss_limit,
            "max_position_size": self.settings.max_position_size,
            "max_order_size": self.settings.max_order_size,
            "rejected_orders": self.rejected_orders
        }
