#!/usr/bin/env python3
"""
Campaign Core - Optimization framework for job application campaigns.

Modules:
- browser_pool: Session pooling for 3-5x throughput
- rate_limiter: Smart rate limiting with circuit breaker
- batch_processor: Optimized batch processing
- retry_handler: Exponential backoff retry logic
- resume_manager: Smart resume version management
- dashboard: Real-time monitoring
"""

from .browser_pool import BrowserSessionPool, get_browser_pool
from .rate_limiter import SmartRateLimiter, get_rate_limiter
from .batch_processor import BatchProcessor, BatchJob, BatchResult
from .retry_handler import ExponentialBackoffRetry, retry_with_backoff
from .resume_manager import ResumeManager, get_resume_manager

__all__ = [
    'BrowserSessionPool',
    'get_browser_pool',
    'SmartRateLimiter',
    'get_rate_limiter',
    'BatchProcessor',
    'BatchJob',
    'BatchResult',
    'ExponentialBackoffRetry',
    'retry_with_backoff',
    'ResumeManager',
    'get_resume_manager',
]
