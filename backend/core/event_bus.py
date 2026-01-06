"""
Event Bus with Metrics

Centralized event system with metrics tracking.

Every event is:
- Timestamped
- Categorized
- Measured (latency, size, etc.)
- Logged

Critical for:
- Observability (what's happening?)
- Performance tuning (where are bottlenecks?)
- Debugging (event sequence)
- Monitoring (real-time metrics)

Metrics tracked:
- Event count per type
- Event latency (processing time)
- Event rate (events/second)
- Queue depth
- Error rate
"""

import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types"""
    MARKET_DATA = 'market_data'
    SIGNAL = 'signal'
    DECISION = 'decision'
    RISK_CHECK = 'risk_check'
    ORDER = 'order'
    FILL = 'fill'
    POSITION = 'position'
    STATE_CHANGE = 'state_change'
    ERROR = 'error'


@dataclass
class Event:
    """Event"""
    event_type: EventType
    event_id: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    source: str = 'system'
    
    def __repr__(self):
        return f"Event({self.event_type.value}, {self.event_id})"


@dataclass
class EventMetrics:
    """Metrics for event type"""
    event_type: EventType
    count: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    error_count: int = 0
    
    @property
    def avg_latency_ms(self) -> float:
        """Average latency"""
        return self.total_latency_ms / self.count if self.count > 0 else 0.0
    
    def __repr__(self):
        return (f"Metrics({self.event_type.value}: "
                f"count={self.count}, "
                f"avg_latency={self.avg_latency_ms:.2f}ms)")


class EventBus:
    """
    Event Bus with Metrics
    
    Centralized event system that:
    - Publishes events
    - Subscribes handlers
    - Tracks metrics
    - Monitors performance
    
    Usage:
        bus = EventBus()
        
        # Subscribe handler
        bus.subscribe(EventType.SIGNAL, handle_signal)
        
        # Publish event
        bus.publish(Event(
            event_type=EventType.SIGNAL,
            event_id='signal_001',
            data={'symbol': 'BTC/USDT', 'action': 'buy'}
        ))
        
        # Get metrics
        metrics = bus.get_metrics(EventType.SIGNAL)
    """
    
    def __init__(self,
                 max_queue_size: int = 10000,
                 metrics_window_sec: float = 60.0):
        
        self.max_queue_size = max_queue_size
        self.metrics_window_sec = metrics_window_sec
        
        # Subscribers: event_type -> list of handlers
        self.subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        
        # Event queue (for async processing)
        self.event_queue: deque = deque(maxlen=max_queue_size)
        
        # Metrics: event_type -> EventMetrics
        self.metrics: Dict[EventType, EventMetrics] = {}
        for event_type in EventType:
            self.metrics[event_type] = EventMetrics(event_type=event_type)
        
        # Rate tracking (events in last N seconds)
        self.event_timestamps: Dict[EventType, deque] = defaultdict(lambda: deque())
        
        # Statistics
        self.total_events = 0
        self.total_errors = 0
        self.start_time = time.time()
        
        logger.info(f"Event Bus initialized: max_queue={max_queue_size}")
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """
        Subscribe handler to event type
        
        Args:
            event_type: Type of event to subscribe to
            handler: Function to call when event is published
        """
        self.subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to {event_type.value}")
    
    def publish(self, event: Event):
        """
        Publish event
        
        Args:
            event: Event to publish
        """
        start_time = time.time()
        
        # Add to queue
        self.event_queue.append(event)
        
        # Update metrics
        self._update_metrics(event, start_time)
        
        # Call subscribers
        handlers = self.subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Handler error for {event.event_type.value}: {e}")
                self.metrics[event.event_type].error_count += 1
                self.total_errors += 1
        
        # Update statistics
        self.total_events += 1
        
        logger.debug(f"Event published: {event}")
    
    def _update_metrics(self, event: Event, start_time: float):
        """Update metrics for event"""
        metrics = self.metrics[event.event_type]
        
        # Update count
        metrics.count += 1
        
        # Update latency
        latency_ms = (time.time() - start_time) * 1000
        metrics.total_latency_ms += latency_ms
        metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
        metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)
        
        # Update rate tracking
        self.event_timestamps[event.event_type].append(event.timestamp)
        
        # Clean old timestamps (outside window)
        cutoff = time.time() - self.metrics_window_sec
        while (self.event_timestamps[event.event_type] and 
               self.event_timestamps[event.event_type][0] < cutoff):
            self.event_timestamps[event.event_type].popleft()
    
    def get_metrics(self, event_type: EventType) -> EventMetrics:
        """Get metrics for event type"""
        return self.metrics[event_type]
    
    def get_rate(self, event_type: EventType) -> float:
        """
        Get event rate (events/second)
        
        Returns:
            Events per second in last metrics_window_sec
        """
        count = len(self.event_timestamps[event_type])
        return count / self.metrics_window_sec
    
    def get_queue_depth(self) -> int:
        """Get current queue depth"""
        return len(self.event_queue)
    
    def get_summary(self) -> Dict:
        """Get summary of all metrics"""
        uptime_sec = time.time() - self.start_time
        
        summary = {
            'uptime_sec': uptime_sec,
            'total_events': self.total_events,
            'total_errors': self.total_errors,
            'error_rate_pct': (self.total_errors / self.total_events * 100) if self.total_events > 0 else 0,
            'queue_depth': self.get_queue_depth(),
            'events_per_sec': self.total_events / uptime_sec if uptime_sec > 0 else 0,
            'by_type': {}
        }
        
        for event_type in EventType:
            metrics = self.metrics[event_type]
            if metrics.count > 0:
                summary['by_type'][event_type.value] = {
                    'count': metrics.count,
                    'avg_latency_ms': metrics.avg_latency_ms,
                    'min_latency_ms': metrics.min_latency_ms,
                    'max_latency_ms': metrics.max_latency_ms,
                    'error_count': metrics.error_count,
                    'rate_per_sec': self.get_rate(event_type)
                }
        
        return summary
    
    def reset_metrics(self):
        """Reset all metrics"""
        for event_type in EventType:
            self.metrics[event_type] = EventMetrics(event_type=event_type)
        
        self.event_timestamps.clear()
        self.total_events = 0
        self.total_errors = 0
        self.start_time = time.time()
        
        logger.info("Metrics reset")


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("📡 EVENT BUS - Centralized Event System with Metrics")
    print("="*80)
    print()
    
    # Create event bus
    bus = EventBus()
    
    # Subscribe handlers
    def handle_signal(event: Event):
        print(f"  📊 Signal handler: {event.data.get('action')} {event.data.get('symbol')}")
    
    def handle_order(event: Event):
        print(f"  📝 Order handler: {event.data.get('side')} {event.data.get('size')}")
    
    bus.subscribe(EventType.SIGNAL, handle_signal)
    bus.subscribe(EventType.ORDER, handle_order)
    
    # Simulate events
    print("Simulating events...")
    print()
    
    # Market data events
    for i in range(100):
        bus.publish(Event(
            event_type=EventType.MARKET_DATA,
            event_id=f'md_{i}',
            data={'symbol': 'BTC/USDT', 'price': 93500 + i}
        ))
    
    # Signal events
    for i in range(5):
        bus.publish(Event(
            event_type=EventType.SIGNAL,
            event_id=f'signal_{i}',
            data={'symbol': 'BTC/USDT', 'action': 'buy', 'confidence': 0.8}
        ))
    
    # Order events
    for i in range(3):
        bus.publish(Event(
            event_type=EventType.ORDER,
            event_id=f'order_{i}',
            data={'symbol': 'BTC/USDT', 'side': 'buy', 'size': 0.1}
        ))
    
    # Fill events
    for i in range(3):
        bus.publish(Event(
            event_type=EventType.FILL,
            event_id=f'fill_{i}',
            data={'symbol': 'BTC/USDT', 'fill_price': 93500.0}
        ))
    
    print()
    print("="*80)
    print("📊 EVENT BUS METRICS")
    print("="*80)
    print()
    
    summary = bus.get_summary()
    
    print(f"Uptime: {summary['uptime_sec']:.2f}s")
    print(f"Total events: {summary['total_events']}")
    print(f"Total errors: {summary['total_errors']}")
    print(f"Error rate: {summary['error_rate_pct']:.2f}%")
    print(f"Queue depth: {summary['queue_depth']}")
    print(f"Events/sec: {summary['events_per_sec']:.1f}")
    print()
    
    print("By Event Type:")
    print("-" * 80)
    for event_type, metrics in summary['by_type'].items():
        print(f"{event_type:15s}: "
              f"count={metrics['count']:3d}, "
              f"avg_latency={metrics['avg_latency_ms']:5.2f}ms, "
              f"rate={metrics['rate_per_sec']:5.1f}/s")
    
    print("="*80)
