"""
Form Validation Retry Handler
Implements intelligent retry logic for form submission failures
"""

import asyncio
import logging
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class RetryReason(Enum):
    """Reasons for form submission retry."""
    VALIDATION_ERROR = "validation_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    ELEMENT_NOT_FOUND = "element_not_found"
    SUBMIT_FAILED = "submit_failed"
    UNKNOWN = "unknown"


@dataclass
class RetryAttempt:
    """Record of a retry attempt."""
    attempt_number: int
    timestamp: datetime
    reason: RetryReason
    error_message: str
    wait_time_seconds: float
    success: bool = False


@dataclass
class FormRetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 30.0
    exponential_base: float = 2.0
    jitter_max_seconds: float = 1.0
    
    # Retryable errors
    retryable_reasons: List[RetryReason] = field(default_factory=lambda: [
        RetryReason.NETWORK_ERROR,
        RetryReason.TIMEOUT,
        RetryReason.RATE_LIMITED,
        RetryReason.SUBMIT_FAILED,
        RetryReason.UNKNOWN
    ])
    
    # Non-retryable errors (fail immediately)
    non_retryable_reasons: List[RetryReason] = field(default_factory=lambda: [
        RetryReason.VALIDATION_ERROR,
    ])


class FormRetryHandler:
    """
    Intelligent form submission retry handler.
    
    Implements:
    - Exponential backoff with jitter
    - Smart error categorization
    - Form state preservation between retries
    - Detailed retry history tracking
    """
    
    def __init__(self, config: Optional[FormRetryConfig] = None):
        self.config = config or FormRetryConfig()
        self.retry_history: Dict[str, List[RetryAttempt]] = {}
    
    async def execute_with_retry(
        self,
        operation_id: str,
        submit_func: Callable,
        validate_func: Optional[Callable] = None,
        cleanup_func: Optional[Callable] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute form submission with intelligent retry logic.
        
        Args:
            operation_id: Unique identifier for this operation
            submit_func: Async function to execute (should raise on failure)
            validate_func: Optional function to validate result
            cleanup_func: Optional function to clean up between retries
            **kwargs: Arguments to pass to submit_func
            
        Returns:
            Dict with success status, result, and retry history
        """
        self.retry_history[operation_id] = []
        last_error = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.info(f"[Attempt {attempt}/{self.config.max_attempts}] {operation_id}")
                
                # Execute the operation
                result = await submit_func(**kwargs)
                
                # Validate result if validator provided
                if validate_func:
                    is_valid, error_msg = await validate_func(result)
                    if not is_valid:
                        raise FormSubmissionError(
                            error_msg, 
                            RetryReason.VALIDATION_ERROR
                        )
                
                # Success!
                self._record_attempt(operation_id, attempt, None, None, True)
                logger.info(f"✅ {operation_id} succeeded on attempt {attempt}")
                
                return {
                    "success": True,
                    "result": result,
                    "attempts": attempt,
                    "retry_history": self.retry_history[operation_id]
                }
                
            except FormSubmissionError as e:
                last_error = e
                reason = e.reason
                
                # Check if this error is retryable
                if reason in self.config.non_retryable_reasons:
                    logger.error(f"❌ Non-retryable error: {e.message}")
                    self._record_attempt(operation_id, attempt, reason, e.message, False)
                    break
                
                if reason not in self.config.retryable_reasons:
                    logger.error(f"❌ Unknown error type: {reason}")
                    self._record_attempt(operation_id, attempt, reason, e.message, False)
                    break
                
                # Calculate wait time
                wait_time = self._calculate_wait_time(attempt)
                
                self._record_attempt(operation_id, attempt, reason, e.message, False, wait_time)
                
                if attempt < self.config.max_attempts:
                    logger.warning(
                        f"⚠️ Attempt {attempt} failed ({reason.value}): {e.message}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    
                    # Clean up if needed
                    if cleanup_func:
                        try:
                            await cleanup_func()
                        except Exception as cleanup_error:
                            logger.warning(f"Cleanup error: {cleanup_error}")
                    
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ All {self.config.max_attempts} attempts failed for {operation_id}")
                    
            except Exception as e:
                # Unexpected error
                last_error = e
                reason = RetryReason.UNKNOWN
                wait_time = self._calculate_wait_time(attempt)
                
                self._record_attempt(operation_id, attempt, reason, str(e), False, wait_time)
                
                if attempt < self.config.max_attempts:
                    logger.warning(f"⚠️ Unexpected error on attempt {attempt}: {e}. Retrying...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ All attempts failed with unexpected error: {e}")
        
        # All retries exhausted
        return {
            "success": False,
            "error": str(last_error) if last_error else "Unknown error",
            "error_type": getattr(last_error, 'reason', RetryReason.UNKNOWN).value if hasattr(last_error, 'reason') else "unknown",
            "attempts": len(self.retry_history.get(operation_id, [])),
            "retry_history": self.retry_history.get(operation_id, [])
        }
    
    def _calculate_wait_time(self, attempt: int) -> float:
        """Calculate wait time with exponential backoff and jitter."""
        import random
        
        # Exponential backoff
        delay = self.config.base_delay_seconds * (self.config.exponential_base ** (attempt - 1))
        delay = min(delay, self.config.max_delay_seconds)
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, self.config.jitter_max_seconds)
        
        return delay + jitter
    
    def _record_attempt(
        self,
        operation_id: str,
        attempt_number: int,
        reason: Optional[RetryReason],
        error_message: Optional[str],
        success: bool,
        wait_time: float = 0.0
    ):
        """Record a retry attempt."""
        if operation_id not in self.retry_history:
            self.retry_history[operation_id] = []
        
        self.retry_history[operation_id].append(RetryAttempt(
            attempt_number=attempt_number,
            timestamp=datetime.now(),
            reason=reason or RetryReason.UNKNOWN,
            error_message=error_message or "",
            wait_time_seconds=wait_time,
            success=success
        ))
    
    def get_retry_stats(self) -> Dict[str, Any]:
        """Get statistics about retry performance."""
        total_operations = len(self.retry_history)
        total_attempts = sum(len(attempts) for attempts in self.retry_history.values())
        successful_first_try = sum(
            1 for attempts in self.retry_history.values()
            if len(attempts) == 1 and attempts[0].success
        )
        
        reason_counts = {}
        for attempts in self.retry_history.values():
            for attempt in attempts:
                if not attempt.success:
                    reason = attempt.reason.value
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        return {
            "total_operations": total_operations,
            "total_attempts": total_attempts,
            "avg_attempts_per_operation": total_attempts / total_operations if total_operations > 0 else 0,
            "successful_first_try": successful_first_try,
            "success_rate_first_try": successful_first_try / total_operations if total_operations > 0 else 0,
            "failure_reasons": reason_counts
        }


class FormSubmissionError(Exception):
    """Custom exception for form submission errors with categorization."""
    
    def __init__(self, message: str, reason: RetryReason):
        self.message = message
        self.reason = reason
        super().__init__(f"[{reason.value}] {message}")


class FieldValidationError(FormSubmissionError):
    """Specific error for field validation failures."""
    
    def __init__(self, field_name: str, message: str):
        self.field_name = field_name
        super().__init__(f"Field '{field_name}': {message}", RetryReason.VALIDATION_ERROR)


# Common validation functions
async def validate_no_error_message(result: Any) -> tuple:
    """Validate that result doesn't contain error indicators."""
    if isinstance(result, dict):
        if result.get('error') or result.get('success') is False:
            return False, result.get('message', 'Unknown error')
    return True, ""


async def validate_page_not_error_page(html: str) -> tuple:
    """Validate that page HTML doesn't indicate an error."""
    error_indicators = [
        'error occurred',
        'something went wrong',
        'please try again',
        'submission failed',
        'invalid input'
    ]
    
    html_lower = html.lower()
    for indicator in error_indicators:
        if indicator in html_lower:
            return False, f"Error indicator found: {indicator}"
    
    return True, ""


# Retry decorator
def with_retry(config: Optional[FormRetryConfig] = None):
    """Decorator to add retry logic to async functions."""
    handler = FormRetryHandler(config)
    
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            operation_id = f"{func.__name__}_{datetime.now().timestamp()}"
            
            async def submit_func(**submit_kwargs):
                return await func(*args, **kwargs)
            
            return await handler.execute_with_retry(
                operation_id=operation_id,
                submit_func=submit_func
            )
        
        return wrapper
    return decorator


# Example usage
if __name__ == "__main__":
    async def test():
        handler = FormRetryHandler(FormRetryConfig(max_attempts=3))
        
        attempt_count = 0
        
        async def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise FormSubmissionError(
                    "Simulated network error",
                    RetryReason.NETWORK_ERROR
                )
            return {"status": "success"}
        
        result = await handler.execute_with_retry(
            operation_id="test_form",
            submit_func=flaky_operation
        )
        
        print(f"Success: {result['success']}")
        print(f"Attempts: {result['attempts']}")
        print(f"Stats: {handler.get_retry_stats()}")
    
    asyncio.run(test())
