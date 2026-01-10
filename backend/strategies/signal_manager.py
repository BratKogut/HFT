"""
Signal Manager - Inspired by SOMA Ghost/Helix System

Manages multiple trading strategies and selects the best signal based on:
- Confidence score
- Priority level
- Revenue performance
- Market conditions

Each strategy is like a "Ghost" - autonomous intelligence agent
that generates signals independently.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import numpy as np


class SignalPriority(str, Enum):
    """Signal priority levels"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class StrategyStatus(str, Enum):
    """Strategy status"""
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    DEGRADED = 'degraded'
    DISABLED = 'disabled'


@dataclass
class TradingSignal:
    """
    Unified trading signal from any strategy
    
    Inspired by SOMA Helix Signal system
    """
    strategy_id: str
    strategy_name: str
    side: str  # 'buy' or 'sell'
    entry_price: float
    take_profit: float
    stop_loss: float
    size: float
    confidence: float  # 0.0 to 1.0
    priority: SignalPriority
    reason: str
    metadata: Dict[str, Any]
    timestamp: datetime
    
    def __repr__(self):
        return (f"Signal({self.strategy_name} {self.side.upper()} "
                f"conf={self.confidence:.0%} pri={self.priority.value})")


@dataclass
class StrategyMetrics:
    """
    Performance metrics for a strategy
    
    Inspired by SOMA Helix Metrics
    """
    strategy_id: str
    strategy_name: str
    status: StrategyStatus
    revenue_target: float  # Target % of total revenue
    revenue_generated: float  # Actual $ generated
    signals_generated: int
    trades_executed: int
    wins: int
    losses: int
    win_rate: float
    avg_profit: float
    sharpe_ratio: float
    last_signal_at: Optional[datetime] = None
    
    def performance_score(self) -> float:
        """
        Calculate overall performance score (0-1)
        
        Based on:
        - Win rate
        - Sharpe ratio
        - Revenue vs target
        """
        # Win rate component (0-0.4)
        win_rate_score = min(self.win_rate / 100, 1.0) * 0.4
        
        # Sharpe component (0-0.3)
        sharpe_score = min(max(self.sharpe_ratio, 0) / 3.0, 1.0) * 0.3
        
        # Revenue component (0-0.3)
        if self.revenue_target > 0:
            revenue_score = min(self.revenue_generated / self.revenue_target, 1.0) * 0.3
        else:
            revenue_score = 0.15  # Neutral if no target
        
        return win_rate_score + sharpe_score + revenue_score


class SignalManager:
    """
    Manages multiple trading strategies and selects best signals
    
    Inspired by SOMA Ghost Manager system
    """
    
    def __init__(self):
        self.strategies: Dict[str, Any] = {}
        self.strategy_metrics: Dict[str, StrategyMetrics] = {}
        
        # Signal history
        self.signal_history: List[TradingSignal] = []
        self.max_history = 1000
        
        # Performance tracking
        self.total_revenue = 0.0
        self.total_trades = 0
        
    def register_strategy(self,
                         strategy_id: str,
                         strategy: Any,
                         revenue_target: float = 0.33):
        """
        Register a trading strategy
        
        Args:
            strategy_id: Unique identifier (e.g., 'liquidation_hunter')
            strategy: Strategy instance
            revenue_target: Target % of total revenue (default 33%)
        """
        self.strategies[strategy_id] = strategy
        
        # Initialize metrics
        self.strategy_metrics[strategy_id] = StrategyMetrics(
            strategy_id=strategy_id,
            strategy_name=getattr(strategy, '__class__').__name__,
            status=StrategyStatus.ACTIVE,
            revenue_target=revenue_target,
            revenue_generated=0.0,
            signals_generated=0,
            trades_executed=0,
            wins=0,
            losses=0,
            win_rate=0.0,
            avg_profit=0.0,
            sharpe_ratio=0.0
        )
        
        print(f"✅ Registered strategy: {strategy_id} (target: {revenue_target*100:.0f}%)")
    
    def collect_signals(self, market_data: Dict) -> List[TradingSignal]:
        """
        Collect signals from all active strategies
        
        Like Ghost Intelligence Collection
        """
        signals = []
        
        for strategy_id, strategy in self.strategies.items():
            metrics = self.strategy_metrics[strategy_id]
            
            # Skip inactive strategies
            if metrics.status != StrategyStatus.ACTIVE:
                continue
            
            try:
                # Get signal from strategy
                signal_data = strategy.analyze_market(**market_data)
                
                if signal_data:
                    # Convert to unified TradingSignal
                    signal = self._convert_to_signal(strategy_id, signal_data)
                    signals.append(signal)
                    
                    # Update metrics
                    metrics.signals_generated += 1
                    metrics.last_signal_at = datetime.utcnow()
                    
            except Exception as e:
                print(f"⚠️  Strategy {strategy_id} failed: {e}")
                metrics.status = StrategyStatus.DEGRADED
        
        return signals
    
    def select_best_signal(self, signals: List[TradingSignal]) -> Optional[TradingSignal]:
        """
        Select the best signal from multiple options
        
        Selection criteria:
        1. Priority (critical > high > medium > low)
        2. Confidence score
        3. Strategy performance
        """
        if not signals:
            return None
        
        # Score each signal
        scored_signals = []
        for signal in signals:
            score = self._calculate_signal_score(signal)
            scored_signals.append((score, signal))
        
        # Sort by score (descending)
        scored_signals.sort(key=lambda x: x[0], reverse=True)
        
        # Return best signal
        best_score, best_signal = scored_signals[0]
        
        print(f"🎯 Selected: {best_signal} (score: {best_score:.2f})")
        
        return best_signal
    
    def _calculate_signal_score(self, signal: TradingSignal) -> float:
        """
        Calculate overall score for a signal
        
        Components:
        - Confidence (0-0.4)
        - Priority (0-0.3)
        - Strategy performance (0-0.3)
        """
        # Confidence component
        confidence_score = signal.confidence * 0.4
        
        # Priority component
        priority_scores = {
            SignalPriority.LOW: 0.1,
            SignalPriority.MEDIUM: 0.2,
            SignalPriority.HIGH: 0.25,
            SignalPriority.CRITICAL: 0.3
        }
        priority_score = priority_scores.get(signal.priority, 0.2)
        
        # Strategy performance component
        metrics = self.strategy_metrics.get(signal.strategy_id)
        if metrics:
            performance_score = metrics.performance_score() * 0.3
        else:
            performance_score = 0.15  # Neutral
        
        return confidence_score + priority_score + performance_score
    
    def _convert_to_signal(self, strategy_id: str, signal_data: Dict) -> TradingSignal:
        """Convert strategy-specific signal to unified TradingSignal"""
        
        # Determine priority based on confidence
        confidence = signal_data.get('confidence', 0.5)
        if confidence >= 0.8:
            priority = SignalPriority.CRITICAL
        elif confidence >= 0.6:
            priority = SignalPriority.HIGH
        elif confidence >= 0.4:
            priority = SignalPriority.MEDIUM
        else:
            priority = SignalPriority.LOW
        
        return TradingSignal(
            strategy_id=strategy_id,
            strategy_name=signal_data.get('strategy', strategy_id),
            side=signal_data['side'],
            entry_price=signal_data['entry_price'],
            take_profit=signal_data['take_profit'],
            stop_loss=signal_data['stop_loss'],
            size=signal_data['size'],
            confidence=confidence,
            priority=priority,
            reason=signal_data.get('reason', ''),
            metadata=signal_data,
            timestamp=signal_data.get('timestamp', datetime.utcnow())
        )
    
    def update_strategy_performance(self,
                                   strategy_id: str,
                                   pnl: float,
                                   was_win: bool):
        """
        Update strategy performance after trade completion
        """
        metrics = self.strategy_metrics.get(strategy_id)
        if not metrics:
            return
        
        # Update metrics
        metrics.trades_executed += 1
        metrics.revenue_generated += pnl
        
        if was_win:
            metrics.wins += 1
        else:
            metrics.losses += 1
        
        # Recalculate win rate
        metrics.win_rate = (metrics.wins / metrics.trades_executed) * 100
        
        # Update total revenue
        self.total_revenue += pnl
        self.total_trades += 1
        
        # Check if strategy should be disabled
        if metrics.trades_executed >= 10:
            if metrics.win_rate < 30:
                print(f"⚠️  Disabling {strategy_id}: Low win rate ({metrics.win_rate:.1f}%)")
                metrics.status = StrategyStatus.DISABLED
            elif metrics.sharpe_ratio < -1.0:
                print(f"⚠️  Disabling {strategy_id}: Negative Sharpe ({metrics.sharpe_ratio:.2f})")
                metrics.status = StrategyStatus.DISABLED
    
    def get_dashboard(self) -> Dict:
        """Get performance dashboard for all strategies"""
        
        dashboard = {
            'total_revenue': self.total_revenue,
            'total_trades': self.total_trades,
            'strategies': []
        }
        
        for strategy_id, metrics in self.strategy_metrics.items():
            dashboard['strategies'].append({
                'id': strategy_id,
                'name': metrics.strategy_name,
                'status': metrics.status.value,
                'revenue_target': f"{metrics.revenue_target*100:.0f}%",
                'revenue_generated': f"${metrics.revenue_generated:,.2f}",
                'trades': metrics.trades_executed,
                'win_rate': f"{metrics.win_rate:.1f}%",
                'sharpe': f"{metrics.sharpe_ratio:.2f}",
                'performance_score': f"{metrics.performance_score():.2f}"
            })
        
        return dashboard
    
    def print_dashboard(self):
        """Print performance dashboard"""
        print()
        print("="*80)
        print("📊 SIGNAL MANAGER DASHBOARD")
        print("="*80)
        print()
        print(f"💰 Total Revenue:  ${self.total_revenue:>12,.2f}")
        print(f"📈 Total Trades:   {self.total_trades:>12}")
        print()
        print("🎯 STRATEGY PERFORMANCE")
        print("-"*80)
        
        for strategy_id, metrics in self.strategy_metrics.items():
            status_emoji = {
                StrategyStatus.ACTIVE: '✅',
                StrategyStatus.INACTIVE: '⏸️',
                StrategyStatus.DEGRADED: '⚠️',
                StrategyStatus.DISABLED: '❌'
            }
            
            print(f"{status_emoji[metrics.status]} {metrics.strategy_name:30s} | "
                  f"Rev: ${metrics.revenue_generated:>8,.2f} | "
                  f"Trades: {metrics.trades_executed:>4} | "
                  f"Win: {metrics.win_rate:>5.1f}% | "
                  f"Score: {metrics.performance_score():.2f}")
        
        print("="*80)
        print()


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("🎯 SIGNAL MANAGER - Inspired by SOMA Ghost/Helix")
    print("="*80)
    print()
    print("Multi-strategy signal management system")
    print("- Collects signals from multiple strategies")
    print("- Selects best signal based on confidence + priority + performance")
    print("- Tracks revenue per strategy")
    print("- Auto-disables underperforming strategies")
    print()
    print("Ready for integration!")
    print("="*80)
