"""
Reason Codes

Every decision MUST have a reason code.

Critical for:
- Debugging (why did system do X?)
- Compliance (audit trail)
- Performance analysis (which reasons work?)
- Strategy evaluation (filter by reason)

Reason codes are hierarchical:
- Category (SIGNAL, RISK, MARKET, SYSTEM)
- Subcategory (SIGNAL_STRONG, RISK_EXCEEDED, etc.)
- Detail (free text)

Example:
    reason_code = ReasonCode.SIGNAL_STRONG
    reason_detail = "Liquidation cluster at $93,000 + CVD bearish divergence"
"""

from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ReasonCategory(str, Enum):
    """Reason category"""
    SIGNAL = 'signal'      # Trading signal
    RISK = 'risk'          # Risk management
    MARKET = 'market'      # Market conditions
    SYSTEM = 'system'      # System state
    ERROR = 'error'        # Error condition


class ReasonCode(str, Enum):
    """
    Reason codes for all decisions
    
    Format: CATEGORY_SUBCATEGORY
    """
    
    # === SIGNAL REASONS ===
    SIGNAL_STRONG = 'SIGNAL_STRONG'                    # High confidence signal
    SIGNAL_MEDIUM = 'SIGNAL_MEDIUM'                    # Medium confidence signal
    SIGNAL_WEAK = 'SIGNAL_WEAK'                        # Low confidence signal
    SIGNAL_LIQUIDATION = 'SIGNAL_LIQUIDATION'          # Liquidation cluster detected
    SIGNAL_CVD = 'SIGNAL_CVD'                          # CVD divergence/exhaustion
    SIGNAL_VOLATILITY = 'SIGNAL_VOLATILITY'            # Volatility spike
    SIGNAL_TREND = 'SIGNAL_TREND'                      # Trend following
    SIGNAL_MEAN_REVERSION = 'SIGNAL_MEAN_REVERSION'    # Mean reversion
    SIGNAL_ARBITRAGE = 'SIGNAL_ARBITRAGE'              # Arbitrage opportunity
    
    # === RISK REASONS ===
    RISK_LIMIT_OK = 'RISK_LIMIT_OK'                    # Risk within limits
    RISK_LIMIT_WARN = 'RISK_LIMIT_WARN'                # Approaching risk limit
    RISK_LIMIT_EXCEEDED = 'RISK_LIMIT_EXCEEDED'        # Risk limit exceeded
    RISK_POSITION_TOO_LARGE = 'RISK_POSITION_TOO_LARGE'  # Position size too large
    RISK_DRAWDOWN_EXCEEDED = 'RISK_DRAWDOWN_EXCEEDED'  # Drawdown limit exceeded
    RISK_CONCENTRATION = 'RISK_CONCENTRATION'          # Position concentration too high
    RISK_CORRELATION = 'RISK_CORRELATION'              # Correlation risk
    
    # === MARKET REASONS ===
    MARKET_TREND_BLOCK = 'MARKET_TREND_BLOCK'          # Trend filter blocked trade
    MARKET_SPREAD_WIDE = 'MARKET_SPREAD_WIDE'          # Spread too wide (low liquidity)
    MARKET_VOLATILITY_HIGH = 'MARKET_VOLATILITY_HIGH'  # Volatility too high
    MARKET_VOLUME_LOW = 'MARKET_VOLUME_LOW'            # Volume too low
    MARKET_HOURS = 'MARKET_HOURS'                      # Outside trading hours
    
    # === SYSTEM REASONS ===
    SYSTEM_STARTUP = 'SYSTEM_STARTUP'                  # System starting up
    SYSTEM_SHUTDOWN = 'SYSTEM_SHUTDOWN'                # System shutting down
    SYSTEM_FREEZE = 'SYSTEM_FREEZE'                    # System frozen (risk/error)
    SYSTEM_RESUME = 'SYSTEM_RESUME'                    # System resumed
    SYSTEM_MAINTENANCE = 'SYSTEM_MAINTENANCE'          # Maintenance mode
    
    # === ERROR REASONS ===
    ERROR_DATA_INVALID = 'ERROR_DATA_INVALID'          # Invalid data
    ERROR_DATA_STALE = 'ERROR_DATA_STALE'              # Stale data
    ERROR_LATENCY_HIGH = 'ERROR_LATENCY_HIGH'          # Latency too high
    ERROR_CONNECTION_LOST = 'ERROR_CONNECTION_LOST'    # Connection lost
    ERROR_EXECUTION_FAILED = 'ERROR_EXECUTION_FAILED'  # Order execution failed
    ERROR_UNKNOWN = 'ERROR_UNKNOWN'                    # Unknown error
    
    # === HISTORICAL REASONS ===
    HIST_FAILURE = 'HIST_FAILURE'                      # Similar thesis failed historically
    HIST_SUCCESS = 'HIST_SUCCESS'                      # Similar thesis succeeded historically
    
    @property
    def category(self) -> ReasonCategory:
        """Get reason category"""
        prefix = self.value.split('_')[0].lower()
        return ReasonCategory(prefix)
    
    def __repr__(self):
        return self.value


@dataclass
class Decision:
    """
    Trading decision with reason code
    
    Every decision MUST have:
    - Action (buy/sell/hold/close)
    - Reason code (why?)
    - Reason detail (specifics)
    - Confidence (0-1)
    """
    action: str
    reason_code: ReasonCode
    reason_detail: str
    confidence: float
    timestamp: float
    data: Optional[Dict] = None
    
    def __repr__(self):
        return (f"Decision({self.action.upper()}, "
                f"{self.reason_code.value}, "
                f"confidence={self.confidence:.2f})")


class ReasonCodeTracker:
    """
    Track reason code statistics
    
    Analyze which reason codes lead to:
    - Profitable trades
    - Losing trades
    - Blocked trades
    
    Usage:
        tracker = ReasonCodeTracker()
        
        # Record decision
        tracker.record_decision(
            reason_code=ReasonCode.SIGNAL_STRONG,
            action='buy',
            outcome='profit',
            pnl=100.0
        )
        
        # Get statistics
        stats = tracker.get_stats(ReasonCode.SIGNAL_STRONG)
    """
    
    def __init__(self):
        # Storage: reason_code -> list of outcomes
        self.decisions: Dict[ReasonCode, List[Dict]] = defaultdict(list)
        
        # Statistics
        self.total_decisions = 0
        self.total_profits = 0.0
        self.total_losses = 0.0
    
    def record_decision(self,
                       reason_code: ReasonCode,
                       action: str,
                       outcome: Optional[str] = None,
                       pnl: Optional[float] = None):
        """
        Record decision with reason code
        
        Args:
            reason_code: Reason for decision
            action: Action taken (buy/sell/hold/close)
            outcome: Outcome (profit/loss/blocked/pending)
            pnl: P&L if applicable
        """
        decision = {
            'reason_code': reason_code,
            'action': action,
            'outcome': outcome,
            'pnl': pnl,
            'timestamp': __import__('time').time()
        }
        
        self.decisions[reason_code].append(decision)
        self.total_decisions += 1
        
        if pnl:
            if pnl > 0:
                self.total_profits += pnl
            else:
                self.total_losses += abs(pnl)
        
        logger.debug(f"Decision recorded: {reason_code.value} -> {action} ({outcome})")
    
    def get_stats(self, reason_code: ReasonCode) -> Dict:
        """Get statistics for specific reason code"""
        decisions = self.decisions.get(reason_code, [])
        
        if not decisions:
            return {
                'count': 0,
                'win_rate': 0.0,
                'avg_pnl': 0.0,
                'total_pnl': 0.0
            }
        
        # Calculate statistics
        count = len(decisions)
        wins = sum(1 for d in decisions if d.get('pnl') is not None and d.get('pnl') > 0)
        losses = sum(1 for d in decisions if d.get('pnl') is not None and d.get('pnl') < 0)
        total_pnl = sum(d.get('pnl', 0) or 0 for d in decisions)
        
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        avg_pnl = total_pnl / count if count > 0 else 0
        
        return {
            'count': count,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'total_pnl': total_pnl
        }
    
    def get_summary(self) -> Dict[ReasonCode, Dict]:
        """Get summary for all reason codes"""
        summary = {}
        
        for reason_code in self.decisions.keys():
            summary[reason_code] = self.get_stats(reason_code)
        
        return summary
    
    def get_best_reasons(self, top_n: int = 5) -> List[tuple]:
        """
        Get best performing reason codes
        
        Returns:
            List of (reason_code, stats) tuples sorted by total_pnl
        """
        summary = self.get_summary()
        
        # Sort by total_pnl
        sorted_reasons = sorted(
            summary.items(),
            key=lambda x: x[1]['total_pnl'],
            reverse=True
        )
        
        return sorted_reasons[:top_n]
    
    def get_worst_reasons(self, top_n: int = 5) -> List[tuple]:
        """
        Get worst performing reason codes
        
        Returns:
            List of (reason_code, stats) tuples sorted by total_pnl (ascending)
        """
        summary = self.get_summary()
        
        # Sort by total_pnl (ascending)
        sorted_reasons = sorted(
            summary.items(),
            key=lambda x: x[1]['total_pnl']
        )
        
        return sorted_reasons[:top_n]


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("🏷️  REASON CODES - Decision Tracking")
    print("="*80)
    print()
    
    # Create tracker
    tracker = ReasonCodeTracker()
    
    # Simulate trading decisions
    print("Simulating trading decisions...")
    print()
    
    # Strong signals (mostly profitable)
    for i in range(10):
        tracker.record_decision(
            reason_code=ReasonCode.SIGNAL_STRONG,
            action='buy',
            outcome='profit' if i < 7 else 'loss',
            pnl=100.0 if i < 7 else -50.0
        )
    
    # Weak signals (mostly losing)
    for i in range(5):
        tracker.record_decision(
            reason_code=ReasonCode.SIGNAL_WEAK,
            action='buy',
            outcome='profit' if i < 2 else 'loss',
            pnl=50.0 if i < 2 else -75.0
        )
    
    # Risk blocks (no P&L)
    for i in range(3):
        tracker.record_decision(
            reason_code=ReasonCode.RISK_LIMIT_EXCEEDED,
            action='block',
            outcome='blocked'
        )
    
    # Trend blocks (no P&L)
    for i in range(5):
        tracker.record_decision(
            reason_code=ReasonCode.MARKET_TREND_BLOCK,
            action='block',
            outcome='blocked'
        )
    
    print("="*80)
    print("📊 REASON CODE STATISTICS")
    print("="*80)
    print()
    
    # Get statistics for each reason code
    for reason_code in [ReasonCode.SIGNAL_STRONG, ReasonCode.SIGNAL_WEAK,
                       ReasonCode.RISK_LIMIT_EXCEEDED, ReasonCode.MARKET_TREND_BLOCK]:
        stats = tracker.get_stats(reason_code)
        print(f"{reason_code.value:25s}: "
              f"count={stats['count']:2d}, "
              f"win_rate={stats['win_rate']:5.1f}%, "
              f"avg_pnl=${stats['avg_pnl']:+7.2f}, "
              f"total=${stats['total_pnl']:+8.2f}")
    
    print()
    print("="*80)
    print("🏆 BEST PERFORMING REASONS")
    print("="*80)
    best = tracker.get_best_reasons(top_n=3)
    for i, (reason_code, stats) in enumerate(best, 1):
        print(f"{i}. {reason_code.value:25s}: ${stats['total_pnl']:+8.2f} "
              f"({stats['win_rate']:.1f}% win rate)")
    
    print()
    print("="*80)
    print("📉 WORST PERFORMING REASONS")
    print("="*80)
    worst = tracker.get_worst_reasons(top_n=3)
    for i, (reason_code, stats) in enumerate(worst, 1):
        print(f"{i}. {reason_code.value:25s}: ${stats['total_pnl']:+8.2f} "
              f"({stats['win_rate']:.1f}% win rate)")
    
    print("="*80)
