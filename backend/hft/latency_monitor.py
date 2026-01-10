"""Latency Monitor - Track performance metrics"""

import time
from collections import defaultdict, deque
from typing import Dict, List
import numpy as np

class LatencyMonitor:
    """Monitor and track latency metrics across system"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.latencies = defaultdict(lambda: deque(maxlen=window_size))
        self.counts = defaultdict(int)
    
    def start_timer(self) -> float:
        """Start a timer, return timestamp in nanoseconds"""
        return time.perf_counter_ns()
    
    def record(self, stage: str, start_time_ns: float):
        """Record latency for a stage"""
        end_time_ns = time.perf_counter_ns()
        duration_ns = end_time_ns - start_time_ns
        duration_us = duration_ns / 1000  # Convert to microseconds
        
        self.latencies[stage].append(duration_us)
        self.counts[stage] += 1
    
    def record_duration(self, stage: str, duration_us: float):
        """Record a pre-calculated duration"""
        self.latencies[stage].append(duration_us)
        self.counts[stage] += 1
    
    def get_stats(self, stage: str = None) -> Dict:
        """Get latency statistics"""
        if stage:
            return self._get_stage_stats(stage)
        
        # Return all stages
        stats = {}
        for stage_name in self.latencies.keys():
            stats[stage_name] = self._get_stage_stats(stage_name)
        
        # Add total end-to-end if available
        if "total" in self.latencies:
            stats["total"] = self._get_stage_stats("total")
        
        return stats
    
    def _get_stage_stats(self, stage: str) -> Dict:
        """Get statistics for a specific stage"""
        if stage not in self.latencies or len(self.latencies[stage]) == 0:
            return {
                "count": 0,
                "mean_us": 0,
                "median_us": 0,
                "p95_us": 0,
                "p99_us": 0,
                "min_us": 0,
                "max_us": 0
            }
        
        data = np.array(list(self.latencies[stage]))
        
        return {
            "count": len(data),
            "mean_us": float(np.mean(data)),
            "median_us": float(np.median(data)),
            "p95_us": float(np.percentile(data, 95)),
            "p99_us": float(np.percentile(data, 99)),
            "min_us": float(np.min(data)),
            "max_us": float(np.max(data))
        }
    
    def get_breakdown(self) -> Dict:
        """Get latency breakdown by stage"""
        breakdown = {}
        for stage in self.latencies.keys():
            stats = self._get_stage_stats(stage)
            breakdown[stage] = {
                "mean_us": stats["mean_us"],
                "mean_ms": stats["mean_us"] / 1000
            }
        return breakdown
    
    def reset(self, stage: str = None):
        """Reset statistics"""
        if stage:
            self.latencies[stage].clear()
            self.counts[stage] = 0
        else:
            self.latencies.clear()
            self.counts.clear()
