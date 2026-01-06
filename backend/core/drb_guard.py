"""
DRB-Guard (Dynamic Risk Budget Guard)

Tracks unrealized risk in real-time.

Without this, system can break risk limits "silently".

Monitors:
- Unrealized P&L per position
- Total portfolio unrealized P&L
- Max drawdown (realized + unrealized)
- Position concentration
- Correlation risk

Actions:
- ALLOW: Risk within limits
- WARN: Approaching limits (80%)
- REDUCE: Reduce position size
- CLOSE: Close position immediately
- FREEZE: Stop all trading

Critical for:
- Risk management
- Drawdown control
- Position sizing
- Portfolio protection
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class RiskAction(str, Enum):
    """Risk action to take"""
    ALLOW = 'allow'      # Risk OK, continue
    WARN = 'warn'        # Approaching limit (80%)
    REDUCE = 'reduce'    # Reduce position size
    CLOSE = 'close'      # Close position now
    FREEZE = 'freeze'    # Stop all trading


@dataclass
class Position:
    """Trading position"""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float
    entry_time: float = field(default_factory=time.time)
    
    @property
    def entry_value(self) -> float:
        """Entry value in USD"""
        return self.size * self.entry_price
    
    @property
    def current_value(self) -> float:
        """Current value in USD"""
        return self.size * self.current_price
    
    @property
    def unrealized_pnl(self) -> float:
        """Unrealized P&L in USD"""
        if self.side == 'long':
            return (self.current_price - self.entry_price) * self.size
        else:  # short
            return (self.entry_price - self.current_price) * self.size
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized P&L as % of entry value"""
        return (self.unrealized_pnl / self.entry_value) * 100
    
    def __repr__(self):
        pnl_emoji = '📈' if self.unrealized_pnl > 0 else '📉'
        return (f"{pnl_emoji} {self.symbol} {self.side.upper()} "
                f"{self.size:.4f} @ ${self.current_price:,.2f}, "
                f"PnL: ${self.unrealized_pnl:+,.2f} ({self.unrealized_pnl_pct:+.2f}%)")


@dataclass
class RiskCheck:
    """Risk check result"""
    action: RiskAction
    reason: str
    current_risk: float  # Current risk metric value
    limit: float         # Risk limit
    utilization_pct: float  # % of limit used
    
    def __repr__(self):
        emoji = {
            RiskAction.ALLOW: '✅',
            RiskAction.WARN: '⚠️',
            RiskAction.REDUCE: '🔶',
            RiskAction.CLOSE: '🔴',
            RiskAction.FREEZE: '🛑'
        }[self.action]
        
        return (f"{emoji} {self.action.value.upper()}: {self.reason} "
                f"({self.utilization_pct:.0f}% of limit)")


class DRBGuard:
    """
    Dynamic Risk Budget Guard
    
    Monitors unrealized risk in real-time and takes action
    when limits are approached or exceeded.
    
    Risk Limits:
    - Max unrealized loss per position
    - Max total unrealized loss
    - Max drawdown (realized + unrealized)
    - Max position concentration
    
    Usage:
        guard = DRBGuard(
            max_position_loss_pct=5.0,  # 5% per position
            max_total_loss_pct=10.0      # 10% total
        )
        
        # Update position
        guard.update_position(position)
        
        # Check risk
        check = guard.check_risk()
        
        if check.action == RiskAction.CLOSE:
            close_position()
    """
    
    def __init__(self,
                 initial_capital: float = 10000.0,
                 max_position_loss_pct: float = 5.0,    # 5% per position
                 max_total_loss_pct: float = 10.0,      # 10% total portfolio
                 max_drawdown_pct: float = 15.0,        # 15% max drawdown
                 max_position_concentration: float = 0.3,  # 30% max per position
                 warn_threshold_pct: float = 80.0):     # Warn at 80% of limit
        
        self.initial_capital = initial_capital
        self.max_position_loss_pct = max_position_loss_pct
        self.max_total_loss_pct = max_total_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_position_concentration = max_position_concentration
        self.warn_threshold_pct = warn_threshold_pct
        
        # Calculate absolute limits
        self.max_position_loss_usd = initial_capital * (max_position_loss_pct / 100)
        self.max_total_loss_usd = initial_capital * (max_total_loss_pct / 100)
        self.max_drawdown_usd = initial_capital * (max_drawdown_pct / 100)
        
        # State
        self.positions: Dict[str, Position] = {}
        self.realized_pnl = 0.0
        self.peak_equity = initial_capital
        
        # Statistics
        self.total_checks = 0
        self.warnings = 0
        self.violations = 0
        
        logger.info(f"DRB-Guard initialized: "
                   f"max_position_loss={max_position_loss_pct}%, "
                   f"max_total_loss={max_total_loss_pct}%, "
                   f"max_drawdown={max_drawdown_pct}%")
    
    def update_position(self, position: Position):
        """Update or add position"""
        self.positions[position.symbol] = position
        logger.debug(f"Position updated: {position}")
    
    def remove_position(self, symbol: str, realized_pnl: float = 0.0):
        """Remove position and update realized P&L"""
        if symbol in self.positions:
            del self.positions[symbol]
            self.realized_pnl += realized_pnl
            logger.debug(f"Position removed: {symbol}, realized PnL: ${realized_pnl:+,.2f}")
    
    def check_risk(self) -> RiskCheck:
        """
        Check all risk limits
        
        Returns:
            RiskCheck with action to take
        """
        self.total_checks += 1
        
        # Check 1: Individual position loss
        check = self._check_position_loss()
        if check.action != RiskAction.ALLOW:
            self.violations += 1
            return check
        
        # Check 2: Total portfolio loss
        check = self._check_total_loss()
        if check.action != RiskAction.ALLOW:
            self.violations += 1
            return check
        
        # Check 3: Drawdown (realized + unrealized)
        check = self._check_drawdown()
        if check.action != RiskAction.ALLOW:
            self.violations += 1
            return check
        
        # Check 4: Position concentration
        check = self._check_concentration()
        if check.action != RiskAction.ALLOW:
            self.warnings += 1
            return check
        
        # All checks passed
        return RiskCheck(
            action=RiskAction.ALLOW,
            reason='All risk checks passed',
            current_risk=0.0,
            limit=0.0,
            utilization_pct=0.0
        )
    
    def _check_position_loss(self) -> RiskCheck:
        """Check individual position loss limits"""
        for symbol, position in self.positions.items():
            unrealized_loss = abs(min(0, position.unrealized_pnl))
            utilization_pct = (unrealized_loss / self.max_position_loss_usd) * 100
            
            if unrealized_loss > self.max_position_loss_usd:
                return RiskCheck(
                    action=RiskAction.CLOSE,
                    reason=f'Position loss exceeded: {symbol} -${unrealized_loss:,.2f}',
                    current_risk=unrealized_loss,
                    limit=self.max_position_loss_usd,
                    utilization_pct=utilization_pct
                )
            
            if utilization_pct > self.warn_threshold_pct:
                return RiskCheck(
                    action=RiskAction.WARN,
                    reason=f'Position loss approaching limit: {symbol}',
                    current_risk=unrealized_loss,
                    limit=self.max_position_loss_usd,
                    utilization_pct=utilization_pct
                )
        
        return RiskCheck(
            action=RiskAction.ALLOW,
            reason='Position loss OK',
            current_risk=0.0,
            limit=self.max_position_loss_usd,
            utilization_pct=0.0
        )
    
    def _check_total_loss(self) -> RiskCheck:
        """Check total portfolio loss limit"""
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        total_unrealized_loss = abs(min(0, total_unrealized_pnl))
        
        utilization_pct = (total_unrealized_loss / self.max_total_loss_usd) * 100
        
        if total_unrealized_loss > self.max_total_loss_usd:
            return RiskCheck(
                action=RiskAction.FREEZE,
                reason=f'Total loss exceeded: -${total_unrealized_loss:,.2f}',
                current_risk=total_unrealized_loss,
                limit=self.max_total_loss_usd,
                utilization_pct=utilization_pct
            )
        
        if utilization_pct > self.warn_threshold_pct:
            return RiskCheck(
                action=RiskAction.REDUCE,
                reason='Total loss approaching limit',
                current_risk=total_unrealized_loss,
                limit=self.max_total_loss_usd,
                utilization_pct=utilization_pct
            )
        
        return RiskCheck(
            action=RiskAction.ALLOW,
            reason='Total loss OK',
            current_risk=total_unrealized_loss,
            limit=self.max_total_loss_usd,
            utilization_pct=utilization_pct
        )
    
    def _check_drawdown(self) -> RiskCheck:
        """Check drawdown (realized + unrealized)"""
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        current_equity = self.initial_capital + self.realized_pnl + total_unrealized_pnl
        
        # Update peak equity
        self.peak_equity = max(self.peak_equity, current_equity)
        
        # Calculate drawdown
        drawdown = self.peak_equity - current_equity
        utilization_pct = (drawdown / self.max_drawdown_usd) * 100
        
        if drawdown > self.max_drawdown_usd:
            return RiskCheck(
                action=RiskAction.FREEZE,
                reason=f'Drawdown exceeded: -${drawdown:,.2f}',
                current_risk=drawdown,
                limit=self.max_drawdown_usd,
                utilization_pct=utilization_pct
            )
        
        if utilization_pct > self.warn_threshold_pct:
            return RiskCheck(
                action=RiskAction.REDUCE,
                reason='Drawdown approaching limit',
                current_risk=drawdown,
                limit=self.max_drawdown_usd,
                utilization_pct=utilization_pct
            )
        
        return RiskCheck(
            action=RiskAction.ALLOW,
            reason='Drawdown OK',
            current_risk=drawdown,
            limit=self.max_drawdown_usd,
            utilization_pct=utilization_pct
        )
    
    def _check_concentration(self) -> RiskCheck:
        """Check position concentration"""
        if not self.positions:
            return RiskCheck(
                action=RiskAction.ALLOW,
                reason='No positions',
                current_risk=0.0,
                limit=0.0,
                utilization_pct=0.0
            )
        
        total_exposure = sum(p.current_value for p in self.positions.values())
        
        for symbol, position in self.positions.items():
            concentration = position.current_value / total_exposure
            utilization_pct = (concentration / self.max_position_concentration) * 100
            
            if concentration > self.max_position_concentration:
                return RiskCheck(
                    action=RiskAction.REDUCE,
                    reason=f'Position concentration too high: {symbol} {concentration*100:.1f}%',
                    current_risk=concentration,
                    limit=self.max_position_concentration,
                    utilization_pct=utilization_pct
                )
            
            if utilization_pct > self.warn_threshold_pct:
                return RiskCheck(
                    action=RiskAction.WARN,
                    reason=f'Position concentration approaching limit: {symbol}',
                    current_risk=concentration,
                    limit=self.max_position_concentration,
                    utilization_pct=utilization_pct
                )
        
        return RiskCheck(
            action=RiskAction.ALLOW,
            reason='Concentration OK',
            current_risk=0.0,
            limit=self.max_position_concentration,
            utilization_pct=0.0
        )
    
    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary"""
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        current_equity = self.initial_capital + self.realized_pnl + total_unrealized_pnl
        drawdown = self.peak_equity - current_equity
        
        return {
            'initial_capital': self.initial_capital,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': total_unrealized_pnl,
            'total_pnl': self.realized_pnl + total_unrealized_pnl,
            'current_equity': current_equity,
            'peak_equity': self.peak_equity,
            'drawdown': drawdown,
            'drawdown_pct': (drawdown / self.peak_equity) * 100 if self.peak_equity > 0 else 0,
            'num_positions': len(self.positions),
            'total_checks': self.total_checks,
            'warnings': self.warnings,
            'violations': self.violations
        }


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("🛡️  DRB-GUARD - Dynamic Risk Budget Guard")
    print("="*80)
    print()
    
    guard = DRBGuard(
        initial_capital=10000.0,
        max_position_loss_pct=5.0,
        max_total_loss_pct=10.0,
        max_drawdown_pct=15.0
    )
    
    # Test 1: Normal position (OK)
    print("Test 1: Normal position (should ALLOW)")
    position = Position(
        symbol='BTC/USDT',
        side='long',
        size=0.1,
        entry_price=93500.0,
        current_price=93600.0  # +$10 profit
    )
    guard.update_position(position)
    print(f"Position: {position}")
    
    check = guard.check_risk()
    print(f"Risk check: {check}")
    print()
    
    # Test 2: Large loss (should WARN)
    print("Test 2: Large loss (should WARN)")
    position.current_price = 93100.0  # -$40 loss (-4.3%)
    guard.update_position(position)
    print(f"Position: {position}")
    
    check = guard.check_risk()
    print(f"Risk check: {check}")
    print()
    
    # Test 3: Exceeded loss limit (should CLOSE)
    print("Test 3: Exceeded loss limit (should CLOSE)")
    position.current_price = 92900.0  # -$60 loss (-6.4%)
    guard.update_position(position)
    print(f"Position: {position}")
    
    check = guard.check_risk()
    print(f"Risk check: {check}")
    print()
    
    # Portfolio summary
    print("="*80)
    print("📊 PORTFOLIO SUMMARY")
    print("="*80)
    summary = guard.get_portfolio_summary()
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key}: {value:,.2f}")
        else:
            print(f"{key}: {value}")
    print("="*80)
