#!/usr/bin/env python3
"""
Smart Rate Limiter - Platform-aware rate limiting with circuit breaker.

Impact: Prevents bans, optimizes throughput per platform
"""

import asyncio
import time
import random
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class PlatformLimits:
    """Rate limits for a platform."""
    requests_per_minute: int
    requests_per_hour: int
    burst_allowance: int
    delay_range: tuple  # (min, max) seconds between requests


class CircuitBreaker:
    """
    Circuit breaker pattern for resilience.
    
    After failure_threshold failures, opens circuit for cooldown period.
    """
    
    def __init__(self, failure_threshold: int = 5, cooldown: int = 300):
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown
        self.failures = 0
        self.last_failure: Optional[float] = None
        self.state = CircuitState.CLOSED
        self.success_count = 0
        
    def can_execute(self) -> bool:
        """Check if request can be executed."""
        if self.state == CircuitState.OPEN:
            if time.time() - (self.last_failure or 0) > self.cooldown:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info(f"[CircuitBreaker] Entering half-open state")
                return True
            return False
        return True
    
    def record_success(self):
        """Record successful request."""
        self.failures = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 3:  # Need 3 successes to close
                self.state = CircuitState.CLOSED
                logger.info(f"[CircuitBreaker] Circuit closed - recovered")
        else:
            self.state = CircuitState.CLOSED
    
    def record_failure(self, error: str):
        """Record failed request."""
        self.failures += 1
        self.last_failure = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"[CircuitBreaker] Failure in half-open, opening circuit: {error}")
        elif self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"[CircuitBreaker] Circuit opened after {self.failures} failures")
    
    def get_state(self) -> str:
        """Get current state."""
        return self.state.value


class SmartRateLimiter:
    """
    Platform-aware rate limiting with circuit breaker.
    
    Platform-specific limits:
    - Greenhouse: High limits (reliable, fast)
    - Lever: Medium limits
    - Workday: Low limits (slow, complex)
    - LinkedIn: Medium limits with strict circuit breaker
    - Indeed: Medium limits
    """
    
    # AGGRESSIVE_MODE: Set via AGGRESSIVE_RATE_LIMITS=1 env var for 2x speed
    # Default mode is conservative to avoid bans
    PLATFORM_LIMITS_AGGRESSIVE = {
        'greenhouse': PlatformLimits(60, 1000, 10, (1, 2)),      # 2x faster
        'lever': PlatformLimits(40, 600, 6, (1.5, 3)),           # 2x faster
        'workday': PlatformLimits(20, 200, 4, (5, 10)),          # 2x faster
        'linkedin': PlatformLimits(20, 200, 3, (10, 20)),        # Conservative for LinkedIn
        'indeed': PlatformLimits(40, 600, 6, (2, 5)),            # 2x faster
        'ashby': PlatformLimits(50, 800, 6, (1.5, 3)),
        'breezy': PlatformLimits(50, 800, 6, (1.5, 3)),
        'smartrecruiters': PlatformLimits(40, 600, 5, (2, 5)),
        'default': PlatformLimits(30, 400, 5, (2, 8)),
    }
    
    PLATFORM_LIMITS = {
        'greenhouse': PlatformLimits(30, 500, 5, (2, 5)),
        'lever': PlatformLimits(20, 300, 3, (3, 6)),
        'workday': PlatformLimits(10, 100, 2, (10, 20)),
        'linkedin': PlatformLimits(15, 200, 3, (15, 30)),
        'indeed': PlatformLimits(20, 300, 4, (5, 10)),
        'ashby': PlatformLimits(25, 400, 4, (3, 6)),
        'breezy': PlatformLimits(25, 400, 4, (3, 6)),
        'smartrecruiters': PlatformLimits(20, 300, 3, (4, 8)),
        'default': PlatformLimits(15, 200, 3, (5, 15)),
    }
    
    def __init__(self, aggressive: bool = False):
        self.semaphores: Dict[str, asyncio.Semaphore] = {}
        self.last_request: Dict[str, float] = {}
        self.request_counts: Dict[str, Dict[str, int]] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.stats: Dict[str, Dict] = {}
        
        # Check for aggressive mode via env var or parameter
        import os
        self.aggressive = aggressive or os.getenv('AGGRESSIVE_RATE_LIMITS', '0') == '1'
        
        limits_dict = self.PLATFORM_LIMITS_AGGRESSIVE if self.aggressive else self.PLATFORM_LIMITS
        
        if self.aggressive:
            logger.warning("[RateLimiter] AGGRESSIVE MODE ENABLED - 2x faster but higher ban risk")
        
        for platform, limits in limits_dict.items():
            self.semaphores[platform] = asyncio.Semaphore(limits.burst_allowance)
            self.last_request[platform] = 0
            self.request_counts[platform] = {'minute': 0, 'hour': 0, 'total': 0}
            self.circuit_breakers[platform] = CircuitBreaker()
            self.stats[platform] = {
                'allowed': 0,
                'denied': 0,
                'delayed': 0,
            }
    
    async def acquire(self, platform: str) -> bool:
        """
        Acquire permission to make request.
        
        Args:
            platform: Platform name
            
        Returns:
            True if allowed, False if blocked
        """
        platform = platform.lower()
        if platform not in self.PLATFORM_LIMITS:
            platform = 'default'
        
        limits = self.PLATFORM_LIMITS.get(platform)
        
        # Check circuit breaker
        if not self.circuit_breakers[platform].can_execute():
            self.stats[platform]['denied'] += 1
            logger.warning(f"[RateLimiter] Circuit open for {platform}, request blocked")
            return False
        
        async with self.semaphores[platform]:
            # Calculate delay since last request
            now = time.time()
            elapsed = now - self.last_request[platform]
            min_delay = limits.delay_range[0]
            
            # Add jitter to avoid thundering herd
            jitter = random.uniform(0, 0.5)
            
            if elapsed < min_delay:
                delay = (min_delay - elapsed) + jitter
                await asyncio.sleep(delay)
                self.stats[platform]['delayed'] += 1
            
            self.last_request[platform] = time.time()
            self.request_counts[platform]['total'] += 1
            self.stats[platform]['allowed'] += 1
            
            return True
    
    def record_success(self, platform: str):
        """Record successful request."""
        platform = platform.lower()
        if platform in self.circuit_breakers:
            self.circuit_breakers[platform].record_success()
    
    def record_failure(self, platform: str, error: str):
        """Record failed request."""
        platform = platform.lower()
        if platform in self.circuit_breakers:
            self.circuit_breakers[platform].record_failure(error)
    
    def get_delay(self, platform: str) -> float:
        """Get recommended delay for platform."""
        platform = platform.lower()
        if platform not in self.PLATFORM_LIMITS:
            platform = 'default'
        
        limits = self.PLATFORM_LIMITS[platform]
        return random.uniform(limits.delay_range[0], limits.delay_range[1])
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        return {
            'by_platform': self.stats,
            'circuit_states': {
                platform: cb.get_state()
                for platform, cb in self.circuit_breakers.items()
            },
            'request_counts': self.request_counts,
        }
    
    def is_healthy(self, platform: str) -> bool:
        """Check if platform is healthy (circuit closed)."""
        platform = platform.lower()
        if platform in self.circuit_breakers:
            return self.circuit_breakers[platform].state == CircuitState.CLOSED
        return True


# Global instance
_limiter: Optional[SmartRateLimiter] = None


def get_rate_limiter(aggressive: bool = False) -> SmartRateLimiter:
    """Get global rate limiter."""
    global _limiter
    if _limiter is None:
        _limiter = SmartRateLimiter(aggressive=aggressive)
    return _limiter


async def rate_limit(platform: str) -> bool:
    """Convenience function for rate limiting."""
    return await get_rate_limiter().acquire(platform)
