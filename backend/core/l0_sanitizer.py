"""
L0 Sanitizer - Layer 0 Data Validation

Critical data validation layer that runs BEFORE any processing.

Validates:
- Latency (< 100ms)
- Spread (liquidity check)
- Tick size (exchange compliance)
- Checksum (data integrity)
- Stale data (timestamp freshness)

If validation fails, system enters FREEZE state.
"""

import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import hashlib
import logging

logger = logging.getLogger(__name__)


class ValidationAction(str, Enum):
    """Action to take on validation failure"""
    ALLOW = 'allow'      # Data is valid, proceed
    SKIP = 'skip'        # Skip this data point, continue
    REJECT = 'reject'    # Reject data, log error
    FREEZE = 'freeze'    # STOP TRADING immediately


@dataclass
class ValidationResult:
    """Result of data validation"""
    valid: bool
    action: ValidationAction
    reason: str = ''
    latency_ms: float = 0.0
    spread_bps: float = 0.0
    
    def __repr__(self):
        status = '✅' if self.valid else '❌'
        return f"{status} {self.action.value.upper()}: {self.reason}"


class L0Sanitizer:
    """
    Layer 0: Data Sanitization
    
    First line of defense against bad data.
    Runs BEFORE any strategy logic.
    
    Validation Hierarchy:
    1. Latency (< 100ms) → FREEZE if exceeded
    2. Spread (< 0.5%) → SKIP if too wide
    3. Tick size → REJECT if invalid
    4. Checksum → FREEZE if failed
    5. Stale data (< 2s old) → FREEZE if stale
    """
    
    def __init__(self,
                 max_latency_ms: float = 100.0,      # 100ms max latency
                 max_spread_bps: float = 50.0,       # 50 bps (0.5%) max spread
                 max_data_age_sec: float = 2.0,      # 2 seconds max data age
                 enable_checksum: bool = True):
        
        self.max_latency_ms = max_latency_ms
        self.max_spread_bps = max_spread_bps
        self.max_data_age_sec = max_data_age_sec
        self.enable_checksum = enable_checksum
        
        # Statistics
        self.total_validations = 0
        self.passed_validations = 0
        self.failed_validations = 0
        self.freeze_count = 0
        
        # Tick size rules (exchange-specific)
        self.tick_size_rules = {
            'BTC/USDT': 0.01,   # $0.01 tick
            'ETH/USDT': 0.01,   # $0.01 tick
            'BNB/USDT': 0.01,   # $0.01 tick
        }
        
        logger.info(f"L0 Sanitizer initialized: "
                   f"max_latency={max_latency_ms}ms, "
                   f"max_spread={max_spread_bps}bps, "
                   f"max_age={max_data_age_sec}s")
    
    def validate(self, market_data: Dict) -> ValidationResult:
        """
        Validate market data
        
        Args:
            market_data: {
                'symbol': 'BTC/USDT',
                'bid': 93500.0,
                'ask': 93505.0,
                'timestamp': 1704672000.0,
                'exchange_timestamp': 1704671999.5,
                'checksum': 'abc123...'
            }
        
        Returns:
            ValidationResult with action to take
        """
        self.total_validations += 1
        
        # Extract fields
        symbol = market_data.get('symbol', 'UNKNOWN')
        bid = market_data.get('bid', 0.0)
        ask = market_data.get('ask', 0.0)
        timestamp = market_data.get('timestamp', time.time())
        exchange_timestamp = market_data.get('exchange_timestamp', timestamp)
        checksum = market_data.get('checksum', '')
        
        # Validation 1: Latency
        result = self._check_latency(timestamp, exchange_timestamp)
        if not result.valid:
            self.failed_validations += 1
            if result.action == ValidationAction.FREEZE:
                self.freeze_count += 1
            return result
        
        # Validation 2: Spread (liquidity)
        result = self._check_spread(bid, ask)
        if not result.valid:
            self.failed_validations += 1
            return result
        
        # Validation 3: Tick size
        result = self._check_tick_size(symbol, bid, ask)
        if not result.valid:
            self.failed_validations += 1
            return result
        
        # Validation 4: Checksum (if enabled)
        if self.enable_checksum and checksum:
            result = self._check_checksum(market_data, checksum)
            if not result.valid:
                self.failed_validations += 1
                if result.action == ValidationAction.FREEZE:
                    self.freeze_count += 1
                return result
        
        # Validation 5: Stale data
        result = self._check_staleness(timestamp)
        if not result.valid:
            self.failed_validations += 1
            if result.action == ValidationAction.FREEZE:
                self.freeze_count += 1
            return result
        
        # All validations passed!
        self.passed_validations += 1
        
        return ValidationResult(
            valid=True,
            action=ValidationAction.ALLOW,
            reason='All validations passed',
            latency_ms=result.latency_ms,
            spread_bps=self._calculate_spread_bps(bid, ask)
        )
    
    def _check_latency(self, 
                      local_timestamp: float,
                      exchange_timestamp: float) -> ValidationResult:
        """
        Check if latency is acceptable
        
        Latency = time between exchange timestamp and local receipt
        """
        latency_sec = local_timestamp - exchange_timestamp
        latency_ms = latency_sec * 1000
        
        if latency_ms > self.max_latency_ms:
            return ValidationResult(
                valid=False,
                action=ValidationAction.FREEZE,
                reason=f'LATENCY_EXCEEDED: {latency_ms:.1f}ms > {self.max_latency_ms}ms',
                latency_ms=latency_ms
            )
        
        return ValidationResult(
            valid=True,
            action=ValidationAction.ALLOW,
            latency_ms=latency_ms
        )
    
    def _check_spread(self, bid: float, ask: float) -> ValidationResult:
        """
        Check if spread is acceptable (liquidity check)
        
        Wide spread = low liquidity = dangerous to trade
        """
        if bid <= 0 or ask <= 0:
            return ValidationResult(
                valid=False,
                action=ValidationAction.REJECT,
                reason='INVALID_PRICES: bid or ask <= 0'
            )
        
        if ask <= bid:
            return ValidationResult(
                valid=False,
                action=ValidationAction.REJECT,
                reason=f'CROSSED_MARKET: ask ({ask}) <= bid ({bid})'
            )
        
        spread_bps = self._calculate_spread_bps(bid, ask)
        
        if spread_bps > self.max_spread_bps:
            return ValidationResult(
                valid=False,
                action=ValidationAction.SKIP,
                reason=f'SPREAD_TOO_WIDE: {spread_bps:.1f}bps > {self.max_spread_bps}bps',
                spread_bps=spread_bps
            )
        
        return ValidationResult(
            valid=True,
            action=ValidationAction.ALLOW,
            spread_bps=spread_bps
        )
    
    def _calculate_spread_bps(self, bid: float, ask: float) -> float:
        """Calculate spread in basis points (bps)"""
        mid = (bid + ask) / 2
        spread = ask - bid
        spread_bps = (spread / mid) * 10000
        return spread_bps
    
    def _check_tick_size(self, 
                        symbol: str,
                        bid: float,
                        ask: float) -> ValidationResult:
        """
        Check if prices conform to exchange tick size rules
        
        Example: BTC/USDT has $0.01 tick size
        So $93,500.123 is INVALID (should be $93,500.12)
        """
        tick_size = self.tick_size_rules.get(symbol)
        
        if not tick_size:
            # Unknown symbol, skip check
            return ValidationResult(
                valid=True,
                action=ValidationAction.ALLOW,
                reason=f'TICK_SIZE_UNKNOWN: {symbol}'
            )
        
        # Check if bid/ask are multiples of tick size
        bid_remainder = bid % tick_size
        ask_remainder = ask % tick_size
        
        tolerance = tick_size * 0.001  # 0.1% tolerance for floating point
        
        if bid_remainder > tolerance:
            return ValidationResult(
                valid=False,
                action=ValidationAction.REJECT,
                reason=f'INVALID_TICK_SIZE: bid {bid} not multiple of {tick_size}'
            )
        
        if ask_remainder > tolerance:
            return ValidationResult(
                valid=False,
                action=ValidationAction.REJECT,
                reason=f'INVALID_TICK_SIZE: ask {ask} not multiple of {tick_size}'
            )
        
        return ValidationResult(
            valid=True,
            action=ValidationAction.ALLOW
        )
    
    def _check_checksum(self,
                       market_data: Dict,
                       provided_checksum: str) -> ValidationResult:
        """
        Verify data integrity using checksum
        
        Protects against data corruption in transit
        """
        # Calculate checksum from data
        data_str = f"{market_data['symbol']}{market_data['bid']}{market_data['ask']}{market_data['timestamp']}"
        calculated_checksum = hashlib.md5(data_str.encode()).hexdigest()[:8]
        
        if calculated_checksum != provided_checksum:
            return ValidationResult(
                valid=False,
                action=ValidationAction.FREEZE,
                reason=f'CHECKSUM_FAILED: {calculated_checksum} != {provided_checksum}'
            )
        
        return ValidationResult(
            valid=True,
            action=ValidationAction.ALLOW
        )
    
    def _check_staleness(self, timestamp: float) -> ValidationResult:
        """
        Check if data is stale (too old)
        
        Stale data = exchange stopped sending updates = FREEZE
        """
        age_sec = time.time() - timestamp
        
        if age_sec > self.max_data_age_sec:
            return ValidationResult(
                valid=False,
                action=ValidationAction.FREEZE,
                reason=f'STALE_DATA: {age_sec:.1f}s old > {self.max_data_age_sec}s'
            )
        
        return ValidationResult(
            valid=True,
            action=ValidationAction.ALLOW
        )
    
    def get_stats(self) -> Dict:
        """Get validation statistics"""
        pass_rate = (self.passed_validations / self.total_validations * 100) if self.total_validations > 0 else 0
        
        return {
            'total_validations': self.total_validations,
            'passed': self.passed_validations,
            'failed': self.failed_validations,
            'pass_rate': pass_rate,
            'freeze_count': self.freeze_count
        }
    
    def reset_stats(self):
        """Reset statistics"""
        self.total_validations = 0
        self.passed_validations = 0
        self.failed_validations = 0
        self.freeze_count = 0


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("🛡️  L0 SANITIZER - Data Validation Layer")
    print("="*80)
    print()
    
    sanitizer = L0Sanitizer(
        max_latency_ms=100.0,
        max_spread_bps=50.0,
        max_data_age_sec=2.0
    )
    
    # Test 1: Valid data
    print("Test 1: Valid data")
    market_data = {
        'symbol': 'BTC/USDT',
        'bid': 93500.00,
        'ask': 93505.00,
        'timestamp': time.time(),
        'exchange_timestamp': time.time() - 0.050  # 50ms latency
    }
    result = sanitizer.validate(market_data)
    print(f"Result: {result}")
    print()
    
    # Test 2: High latency
    print("Test 2: High latency (should FREEZE)")
    market_data = {
        'symbol': 'BTC/USDT',
        'bid': 93500.00,
        'ask': 93505.00,
        'timestamp': time.time(),
        'exchange_timestamp': time.time() - 0.150  # 150ms latency
    }
    result = sanitizer.validate(market_data)
    print(f"Result: {result}")
    print()
    
    # Test 3: Wide spread
    print("Test 3: Wide spread (should SKIP)")
    market_data = {
        'symbol': 'BTC/USDT',
        'bid': 93000.00,
        'ask': 93500.00,  # 0.54% spread
        'timestamp': time.time(),
        'exchange_timestamp': time.time() - 0.050
    }
    result = sanitizer.validate(market_data)
    print(f"Result: {result}")
    print()
    
    # Statistics
    print("="*80)
    print("📊 STATISTICS")
    print("="*80)
    stats = sanitizer.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    print("="*80)
