"""
WAL (Write-Ahead Logging) Logger

Logs every decision BEFORE execution.

Critical for:
- System recovery after crash
- Debugging (replay decisions)
- Compliance (audit trail)
- Performance analysis

Format: JSONL (JSON Lines)
- One JSON object per line
- Easy to parse
- Append-only
- Crash-safe

Every log entry contains:
- Timestamp
- Event type
- Decision details
- Reason code
- System state

Can reconstruct entire system state from WAL.
"""

import json
import time
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class WALEntry:
    """Write-Ahead Log entry"""
    timestamp: float
    event_type: str
    event_id: str
    data: Dict[str, Any]
    reason_code: Optional[str] = None
    reason_detail: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, json_str: str) -> 'WALEntry':
        """Create from JSON string"""
        data = json.loads(json_str)
        return cls(**data)
    
    def __repr__(self):
        return f"WAL({self.event_type} @ {datetime.fromtimestamp(self.timestamp).strftime('%H:%M:%S.%f')[:-3]})"


class WALLogger:
    """
    Write-Ahead Logger
    
    Logs every decision to JSONL file BEFORE execution.
    
    If system crashes, can replay from WAL to recover state.
    
    Usage:
        wal = WALLogger('logs/wal.jsonl')
        
        # Log decision
        wal.log_decision(
            event_id='trade_001',
            decision='buy',
            reason_code='SIGNAL_STRONG',
            data={'symbol': 'BTC/USDT', 'size': 0.1}
        )
        
        # Log execution
        wal.log_execution(
            event_id='trade_001',
            result='filled',
            data={'fill_price': 93500.0}
        )
        
        # Replay from WAL
        entries = wal.replay()
    """
    
    # Event types
    EVENT_DECISION = 'decision'
    EVENT_EXECUTION = 'execution'
    EVENT_RISK_CHECK = 'risk_check'
    EVENT_STATE_CHANGE = 'state_change'
    EVENT_ERROR = 'error'
    
    def __init__(self,
                 log_path: str = 'logs/wal.jsonl',
                 auto_flush: bool = True,
                 max_file_size_mb: int = 100):
        
        self.log_path = Path(log_path)
        self.auto_flush = auto_flush
        self.max_file_size_mb = max_file_size_mb
        
        # Create log directory
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open log file in append mode
        self.log_file = open(self.log_path, 'a', buffering=1 if auto_flush else -1)
        
        # Statistics
        self.entries_written = 0
        self.bytes_written = 0
        
        logger.info(f"WAL Logger initialized: {self.log_path}")
    
    def log(self,
            event_type: str,
            event_id: str,
            data: Dict[str, Any],
            reason_code: Optional[str] = None,
            reason_detail: Optional[str] = None):
        """
        Log entry to WAL
        
        Args:
            event_type: Type of event
            event_id: Unique event identifier
            data: Event data
            reason_code: Optional reason code
            reason_detail: Optional reason detail
        """
        entry = WALEntry(
            timestamp=time.time(),
            event_type=event_type,
            event_id=event_id,
            data=data,
            reason_code=reason_code,
            reason_detail=reason_detail
        )
        
        # Write to file
        json_str = entry.to_json()
        self.log_file.write(json_str + '\n')
        
        # Update statistics
        self.entries_written += 1
        self.bytes_written += len(json_str) + 1
        
        # Check file size
        if self.bytes_written > self.max_file_size_mb * 1024 * 1024:
            self._rotate_log()
        
        logger.debug(f"WAL entry written: {entry}")
    
    def log_decision(self,
                    event_id: str,
                    decision: str,
                    reason_code: str,
                    data: Dict[str, Any],
                    reason_detail: Optional[str] = None):
        """Log trading decision"""
        self.log(
            event_type=self.EVENT_DECISION,
            event_id=event_id,
            data={'decision': decision, **data},
            reason_code=reason_code,
            reason_detail=reason_detail
        )
    
    def log_execution(self,
                     event_id: str,
                     result: str,
                     data: Dict[str, Any]):
        """Log execution result"""
        self.log(
            event_type=self.EVENT_EXECUTION,
            event_id=event_id,
            data={'result': result, **data}
        )
    
    def log_risk_check(self,
                      event_id: str,
                      action: str,
                      reason: str,
                      data: Dict[str, Any]):
        """Log risk check"""
        self.log(
            event_type=self.EVENT_RISK_CHECK,
            event_id=event_id,
            data={'action': action, **data},
            reason_code=action,
            reason_detail=reason
        )
    
    def log_state_change(self,
                        event_id: str,
                        old_state: str,
                        new_state: str,
                        reason: str):
        """Log system state change"""
        self.log(
            event_type=self.EVENT_STATE_CHANGE,
            event_id=event_id,
            data={'old_state': old_state, 'new_state': new_state},
            reason_code='STATE_CHANGE',
            reason_detail=reason
        )
    
    def log_error(self,
                 event_id: str,
                 error_type: str,
                 error_message: str,
                 data: Optional[Dict[str, Any]] = None):
        """Log error"""
        self.log(
            event_type=self.EVENT_ERROR,
            event_id=event_id,
            data={'error_type': error_type, 'error_message': error_message, **(data or {})},
            reason_code='ERROR',
            reason_detail=error_message
        )
    
    def replay(self, start_time: Optional[float] = None) -> List[WALEntry]:
        """
        Replay WAL from start
        
        Args:
            start_time: Optional start timestamp (replay from this point)
        
        Returns:
            List of WAL entries
        """
        entries = []
        
        # Close current file handle
        self.log_file.close()
        
        # Read all entries
        with open(self.log_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry = WALEntry.from_json(line)
                    
                    # Filter by start time
                    if start_time and entry.timestamp < start_time:
                        continue
                    
                    entries.append(entry)
                except Exception as e:
                    logger.error(f"Failed to parse WAL entry: {e}")
                    continue
        
        # Reopen file for writing
        self.log_file = open(self.log_path, 'a', buffering=1 if self.auto_flush else -1)
        
        logger.info(f"Replayed {len(entries)} WAL entries")
        
        return entries
    
    def _rotate_log(self):
        """Rotate log file when it gets too large"""
        # Close current file
        self.log_file.close()
        
        # Rename to timestamped file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_path = self.log_path.parent / f"{self.log_path.stem}_{timestamp}.jsonl"
        self.log_path.rename(archive_path)
        
        logger.info(f"WAL rotated: {archive_path}")
        
        # Open new file
        self.log_file = open(self.log_path, 'a', buffering=1 if self.auto_flush else -1)
        self.bytes_written = 0
    
    def get_stats(self) -> Dict:
        """Get WAL statistics"""
        return {
            'log_path': str(self.log_path),
            'entries_written': self.entries_written,
            'bytes_written': self.bytes_written,
            'file_size_mb': self.bytes_written / (1024 * 1024)
        }
    
    def close(self):
        """Close WAL logger"""
        self.log_file.close()
        logger.info(f"WAL Logger closed: {self.entries_written} entries written")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("📝 WAL LOGGER - Write-Ahead Logging")
    print("="*80)
    print()
    
    # Create WAL logger
    wal = WALLogger('logs/wal_test.jsonl')
    
    # Simulate trading sequence
    print("Simulating trading sequence...")
    print()
    
    # 1. Decision to buy
    print("1. Log decision: BUY BTC/USDT")
    wal.log_decision(
        event_id='trade_001',
        decision='buy',
        reason_code='SIGNAL_STRONG',
        data={
            'symbol': 'BTC/USDT',
            'size': 0.1,
            'price': 93500.0,
            'confidence': 0.85
        },
        reason_detail='Liquidation cluster + CVD confirmation'
    )
    
    # 2. Risk check
    print("2. Log risk check: ALLOW")
    wal.log_risk_check(
        event_id='risk_001',
        action='ALLOW',
        reason='Risk within limits',
        data={
            'position_risk': 0.05,
            'total_risk': 0.08,
            'drawdown': 0.02
        }
    )
    
    # 3. Execution
    print("3. Log execution: FILLED")
    wal.log_execution(
        event_id='trade_001',
        result='filled',
        data={
            'fill_price': 93515.0,
            'fill_size': 0.1,
            'fees': 9.35,
            'execution_time_ms': 45.2
        }
    )
    
    # 4. State change
    print("4. Log state change: IDLE -> TRADING")
    wal.log_state_change(
        event_id='state_001',
        old_state='IDLE',
        new_state='TRADING',
        reason='Position opened'
    )
    
    # 5. Error (simulate)
    print("5. Log error: CONNECTION_LOST")
    wal.log_error(
        event_id='error_001',
        error_type='CONNECTION_LOST',
        error_message='WebSocket connection lost',
        data={'exchange': 'binance', 'reconnect_attempt': 1}
    )
    
    print()
    print("="*80)
    print("📊 WAL STATISTICS")
    print("="*80)
    stats = wal.get_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
    print("="*80)
    print()
    
    # Replay WAL
    print("="*80)
    print("🔄 REPLAYING WAL")
    print("="*80)
    entries = wal.replay()
    
    for i, entry in enumerate(entries, 1):
        print(f"{i}. {entry.event_type.upper():15s} | "
              f"{entry.event_id:12s} | "
              f"{entry.reason_code or 'N/A':20s}")
    
    print("="*80)
    
    # Close
    wal.close()
    
    print()
    print(f"✅ WAL file created: logs/wal_test.jsonl")
    print(f"   Entries: {stats['entries_written']}")
    print(f"   Size: {stats['file_size_mb']:.2f} MB")
