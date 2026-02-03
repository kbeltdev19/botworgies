"""
Retry utilities for ATS automation
"""

import asyncio
import functools
from typing import Callable, TypeVar, Any

T = TypeVar('T')


def async_retry(
    max_retries: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Callable = None
):
    """
    Decorator for async functions with retry logic
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Optional callback function called on each retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        if on_retry:
                            on_retry(attempt + 1, max_retries, e)
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        raise last_exception
            
            raise last_exception  # Should never reach here
        
        return wrapper
    return decorator


class RetryConfig:
    """Configuration for retry behavior"""
    
    # Default settings
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_DELAY = 2.0
    DEFAULT_BACKOFF = 2.0
    
    # Platform-specific settings
    INDEED_RETRIES = 3
    INDEED_DELAY = 2.0
    
    LINKEDIN_RETRIES = 2  # LinkedIn is slower, fewer retries
    LINKEDIN_DELAY = 3.0
    
    # Statuses that warrant a retry
    RETRYABLE_STATUSES = [
        'unknown_format',
        'timeout',
        'navigation_error',
        'element_not_found',
    ]


def should_retry(status: str) -> bool:
    """Check if a status warrants a retry"""
    return status in RetryConfig.RETRYABLE_STATUSES
