#!/usr/bin/env python3
"""
Retry Handler - Automatic retry with exponential backoff and jitter.

Part of UX improvements for resilient applications.
"""

import asyncio
import random
import time
from typing import Callable, TypeVar, Optional, Any, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryReason(Enum):
    """Reasons for retry."""
    CAPTCHA = "captcha"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN = "unknown"
    SUCCESS = "success"


@dataclass
class RetryResult:
    """Result of a retry operation."""
    success: bool
    result: Any
    attempts: int
    total_duration: float
    reason: RetryReason
    error: Optional[str] = None
    retry_history: List[Dict] = None


class ExponentialBackoffRetry:
    """
    Retry operations with exponential backoff and jitter.
    
    Formula: delay = min(base_delay * 2^attempt, max_delay) + jitter
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter_factor: float = 0.1,
        retryable_exceptions: tuple = (Exception,)
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor
        self.retryable_exceptions = retryable_exceptions
        
        self.stats = {
            'total_attempts': 0,
            'success_first_try': 0,
            'success_after_retry': 0,
            'final_failures': 0,
        }
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        # Exponential backoff
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        
        # Add jitter (randomize by jitter_factor)
        jitter = random.uniform(0, delay * self.jitter_factor)
        
        return delay + jitter
    
    async def execute(
        self,
        func: Callable[[], T],
        operation_id: str = "",
        context: Optional[Dict] = None
    ) -> RetryResult:
        """
        Execute function with retry logic.
        
        Args:
            func: Async function to execute
            operation_id: Identifier for logging
            context: Additional context for logging
            
        Returns:
            RetryResult with success status and metadata
        """
        start_time = time.time()
        retry_history = []
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            self.stats['total_attempts'] += 1
            
            try:
                logger.debug(f"[Retry] Attempt {attempt + 1}/{self.max_retries + 1} for {operation_id}")
                
                result = await func()
                
                duration = time.time() - start_time
                
                if attempt == 0:
                    self.stats['success_first_try'] += 1
                else:
                    self.stats['success_after_retry'] += 1
                
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt + 1,
                    total_duration=duration,
                    reason=RetryReason.SUCCESS,
                    retry_history=retry_history
                )
                
            except self.retryable_exceptions as e:
                last_error = str(e)
                error_type = self._classify_error(e)
                
                logger.warning(
                    f"[Retry] Attempt {attempt + 1} failed for {operation_id}: {e}"
                )
                
                retry_history.append({
                    'attempt': attempt + 1,
                    'error': last_error,
                    'error_type': error_type.value,
                    'timestamp': time.time(),
                })
                
                # Don't retry on final attempt
                if attempt >= self.max_retries:
                    break
                
                # Calculate and apply delay
                delay = self.calculate_delay(attempt)
                logger.debug(f"[Retry] Waiting {delay:.2f}s before retry...")
                await asyncio.sleep(delay)
        
        # All retries exhausted
        self.stats['final_failures'] += 1
        duration = time.time() - start_time
        
        return RetryResult(
            success=False,
            result=None,
            attempts=self.max_retries + 1,
            total_duration=duration,
            reason=self._classify_error_str(last_error),
            error=last_error,
            retry_history=retry_history
        )
    
    def _classify_error(self, error: Exception) -> RetryReason:
        """Classify error type."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        if 'captcha' in error_str or 'recaptcha' in error_str:
            return RetryReason.CAPTCHA
        elif 'timeout' in error_str or 'timed out' in error_str:
            return RetryReason.TIMEOUT
        elif 'network' in error_str or 'connection' in error_str:
            return RetryReason.NETWORK_ERROR
        elif 'validation' in error_str or 'invalid' in error_str:
            return RetryReason.VALIDATION_ERROR
        else:
            return RetryReason.UNKNOWN
    
    def _classify_error_str(self, error_str: Optional[str]) -> RetryReason:
        """Classify error from string."""
        if not error_str:
            return RetryReason.UNKNOWN
        
        error_lower = error_str.lower()
        
        if 'captcha' in error_lower:
            return RetryReason.CAPTCHA
        elif 'timeout' in error_lower:
            return RetryReason.TIMEOUT
        elif 'network' in error_lower or 'connection' in error_lower:
            return RetryReason.NETWORK_ERROR
        elif 'validation' in error_lower:
            return RetryReason.VALIDATION_ERROR
        else:
            return RetryReason.UNKNOWN
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retry statistics."""
        total = self.stats['total_attempts']
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            'success_rate': f"{((self.stats['success_first_try'] + self.stats['success_after_retry']) / total * 100):.1f}%",
            'first_try_rate': f"{(self.stats['success_first_try'] / total * 100):.1f}%",
            'retry_recovery_rate': f"{(self.stats['success_after_retry'] / max(self.stats['total_attempts'] - self.stats['success_first_try'], 1) * 100):.1f}%",
        }


class SmartRetryHandler:
    """
    Smart retry handler with different strategies per error type.
    """
    
    def __init__(self):
        # Different retry configs for different error types
        self.strategies = {
            RetryReason.CAPTCHA: ExponentialBackoffRetry(
                max_retries=2,
                base_delay=5.0,
                max_delay=30.0
            ),
            RetryReason.NETWORK_ERROR: ExponentialBackoffRetry(
                max_retries=3,
                base_delay=1.0,
                max_delay=30.0
            ),
            RetryReason.TIMEOUT: ExponentialBackoffRetry(
                max_retries=2,
                base_delay=2.0,
                max_delay=20.0
            ),
            RetryReason.VALIDATION_ERROR: ExponentialBackoffRetry(
                max_retries=1,  # Don't retry validation errors much
                base_delay=1.0,
                max_delay=5.0
            ),
            RetryReason.UNKNOWN: ExponentialBackoffRetry(
                max_retries=2,
                base_delay=1.0,
                max_delay=30.0
            ),
        }
    
    async def execute(
        self,
        func: Callable[[], T],
        operation_id: str = "",
        preferred_strategy: Optional[RetryReason] = None
    ) -> RetryResult:
        """Execute with smart retry strategy."""
        
        # Use preferred strategy if specified
        if preferred_strategy and preferred_strategy in self.strategies:
            strategy = self.strategies[preferred_strategy]
        else:
            # Default to unknown strategy
            strategy = self.strategies[RetryReason.UNKNOWN]
        
        result = await strategy.execute(func, operation_id)
        
        # If failed and we have a reason, try that strategy
        if not result.success and result.retry_history:
            detected_reason = result.reason
            if detected_reason != RetryReason.UNKNOWN and detected_reason != preferred_strategy:
                logger.info(f"[SmartRetry] Retrying with {detected_reason.value} strategy")
                specific_strategy = self.strategies.get(detected_reason, strategy)
                return await specific_strategy.execute(func, operation_id)
        
        return result


# Convenience functions
async def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    operation_id: str = ""
) -> RetryResult:
    """Simple retry function."""
    handler = ExponentialBackoffRetry(
        max_retries=max_retries,
        base_delay=base_delay
    )
    return await handler.execute(func, operation_id)
