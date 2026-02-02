"""
Metrics & Monitoring
Track KPIs for production monitoring.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import time
import statistics


@dataclass
class Counter:
    """Simple counter metric."""
    value: int = 0
    
    def inc(self, amount: int = 1):
        self.value += amount
    
    def reset(self):
        self.value = 0


@dataclass
class Gauge:
    """Gauge metric for current values."""
    value: float = 0.0
    labels: Dict[str, float] = field(default_factory=dict)
    
    def set(self, value: float, label: str = None):
        if label:
            self.labels[label] = value
        else:
            self.value = value
    
    def get(self, label: str = None) -> float:
        if label:
            return self.labels.get(label, 0.0)
        return self.value


@dataclass
class Histogram:
    """Histogram for latency/duration tracking."""
    buckets: List[float] = field(default_factory=lambda: [0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300])
    observations: List[float] = field(default_factory=list)
    
    def observe(self, value: float):
        self.observations.append(value)
    
    def p50(self) -> float:
        if not self.observations:
            return 0
        return statistics.median(self.observations)
    
    def p95(self) -> float:
        if not self.observations:
            return 0
        sorted_obs = sorted(self.observations)
        idx = int(len(sorted_obs) * 0.95)
        return sorted_obs[min(idx, len(sorted_obs) - 1)]
    
    def p99(self) -> float:
        if not self.observations:
            return 0
        sorted_obs = sorted(self.observations)
        idx = int(len(sorted_obs) * 0.99)
        return sorted_obs[min(idx, len(sorted_obs) - 1)]
    
    def mean(self) -> float:
        if not self.observations:
            return 0
        return statistics.mean(self.observations)


class ApplicationMetrics:
    """Centralized metrics for the application system."""
    
    def __init__(self):
        # Success metrics
        self.applications_submitted_daily = Counter()
        self.applications_attempted_daily = Counter()
        self.success_rate_by_platform = Gauge()
        
        # Quality metrics
        self.hallucination_incidents = Counter()  # Should always be 0
        self.user_corrections_needed = Counter()
        self.interview_conversion_rate = Gauge()
        
        # System health
        self.avg_time_per_application = Histogram()
        self.browser_session_lifetime = Gauge()
        self.captcha_solve_rate = Gauge()
        self.resume_parse_latency = Histogram()
        self.kimi_api_latency = Histogram()
        
        # Safety
        self.rate_limit_hits = Counter()
        self.account_warnings = Counter()
        self.ip_blocks = Counter()  # Critical - should trigger alerts
        
        # Timestamp tracking
        self.last_reset = datetime.now()
    
    def record_application_attempt(self, platform: str, success: bool, duration_seconds: float):
        """Record an application attempt."""
        self.applications_attempted_daily.inc()
        
        if success:
            self.applications_submitted_daily.inc()
        
        self.avg_time_per_application.observe(duration_seconds)
        
        # Update success rate
        current_rate = self.success_rate_by_platform.get(platform)
        # Moving average
        new_rate = current_rate * 0.9 + (1.0 if success else 0.0) * 0.1
        self.success_rate_by_platform.set(new_rate, platform)
    
    def record_kimi_call(self, duration_seconds: float, success: bool):
        """Record Kimi API call."""
        self.kimi_api_latency.observe(duration_seconds)
    
    def record_resume_parse(self, duration_seconds: float):
        """Record resume parsing time."""
        self.resume_parse_latency.observe(duration_seconds)
    
    def record_rate_limit(self, service: str):
        """Record rate limit hit."""
        self.rate_limit_hits.inc()
    
    def record_account_warning(self, platform: str):
        """Record account warning/restriction."""
        self.account_warnings.inc()
    
    def record_ip_block(self, platform: str):
        """Record IP block - CRITICAL."""
        self.ip_blocks.inc()
    
    def record_hallucination(self, description: str):
        """Record hallucination incident - should never happen."""
        self.hallucination_incidents.inc()
    
    def get_summary(self) -> dict:
        """Get current metrics summary."""
        return {
            "period_start": self.last_reset.isoformat(),
            "applications": {
                "attempted": self.applications_attempted_daily.value,
                "submitted": self.applications_submitted_daily.value,
                "success_rate": self.applications_submitted_daily.value / max(1, self.applications_attempted_daily.value)
            },
            "success_by_platform": self.success_rate_by_platform.labels,
            "latency": {
                "application_avg": self.avg_time_per_application.mean(),
                "application_p95": self.avg_time_per_application.p95(),
                "kimi_api_avg": self.kimi_api_latency.mean(),
                "kimi_api_p95": self.kimi_api_latency.p95(),
                "resume_parse_avg": self.resume_parse_latency.mean()
            },
            "safety": {
                "hallucination_incidents": self.hallucination_incidents.value,
                "rate_limit_hits": self.rate_limit_hits.value,
                "account_warnings": self.account_warnings.value,
                "ip_blocks": self.ip_blocks.value  # Should be 0
            },
            "quality": {
                "user_corrections": self.user_corrections_needed.value,
                "interview_rate": self.interview_conversion_rate.value
            }
        }
    
    def reset_daily(self):
        """Reset daily counters."""
        self.applications_submitted_daily.reset()
        self.applications_attempted_daily.reset()
        self.rate_limit_hits.reset()
        self.last_reset = datetime.now()
    
    def get_alerts(self) -> List[dict]:
        """Get any active alerts based on metrics."""
        alerts = []
        
        if self.ip_blocks.value > 0:
            alerts.append({
                "severity": "critical",
                "message": f"IP blocked {self.ip_blocks.value} times - STOP ALL OPERATIONS",
                "action": "pause_all_campaigns"
            })
        
        if self.account_warnings.value > 0:
            alerts.append({
                "severity": "high",
                "message": f"Account warnings detected ({self.account_warnings.value})",
                "action": "reduce_rate"
            })
        
        if self.hallucination_incidents.value > 0:
            alerts.append({
                "severity": "high",
                "message": f"Hallucination detected ({self.hallucination_incidents.value}) - review AI outputs",
                "action": "review_outputs"
            })
        
        if self.rate_limit_hits.value > 10:
            alerts.append({
                "severity": "medium",
                "message": f"High rate limit hits ({self.rate_limit_hits.value})",
                "action": "increase_delays"
            })
        
        return alerts


# Global metrics instance
metrics = ApplicationMetrics()


# Context manager for timing
class Timer:
    """Context manager for timing operations."""
    
    def __init__(self, histogram: Histogram = None):
        self.histogram = histogram
        self.start_time = None
        self.duration = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        self.duration = time.time() - self.start_time
        if self.histogram:
            self.histogram.observe(self.duration)


# Example usage:
# with Timer(metrics.kimi_api_latency):
#     result = await kimi.tailor_resume(...)
