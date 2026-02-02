"""
Parallel Job Application Processor
Handles concurrent application submissions with rate limiting.
Target: 10 applications per minute with proper throttling.
"""

import asyncio
import time
from typing import List, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


@dataclass
class ParallelApplicationResult:
    """Result of a single application in a batch."""
    job_url: str
    status: ApplicationStatus
    message: str
    application_id: str = None
    started_at: datetime = None
    completed_at: datetime = None
    duration_seconds: float = 0.0
    error: str = None


@dataclass
class BatchApplicationStats:
    """Statistics for a batch application run."""
    total: int
    completed: int
    failed: int
    rate_limited: int
    total_duration_seconds: float
    apps_per_minute: float
    average_duration_seconds: float


class RateLimiter:
    """Token bucket rate limiter for controlling application throughput."""
    
    def __init__(self, max_requests: int, time_window_seconds: float):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in time window
            time_window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window_seconds
        self.tokens = max_requests
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """
        Try to acquire a token. Blocks until token is available.
        
        Returns:
            True if token acquired
        """
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Add tokens based on elapsed time
            self.tokens = min(
                self.max_requests,
                self.tokens + (elapsed * self.max_requests / self.time_window)
            )
            self.last_update = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            
            # Calculate wait time
            wait_time = (1 - self.tokens) * (self.time_window / self.max_requests)
            await asyncio.sleep(wait_time)
            
            self.tokens = min(
                self.max_requests,
                self.tokens + (wait_time * self.max_requests / self.time_window)
            )
            self.last_update = time.time()
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            
            return False


class ParallelApplicationProcessor:
    """
    Processor for parallel job application submissions.
    
    Features:
    - Configurable concurrency (max parallel applications)
    - Rate limiting (applications per minute)
    - Progress tracking
    - Error handling with retries
    - Statistics collection
    """
    
    def __init__(
        self,
        max_concurrent: int = 3,
        target_apps_per_minute: float = 10.0,
        retry_attempts: int = 2
    ):
        """
        Initialize the parallel processor.
        
        Args:
            max_concurrent: Maximum number of concurrent applications
            target_apps_per_minute: Target applications per minute (rate limit)
            retry_attempts: Number of retry attempts for failed applications
        """
        self.max_concurrent = max_concurrent
        self.target_apps_per_minute = target_apps_per_minute
        self.retry_attempts = retry_attempts
        
        # Rate limiter: target_apps_per_minute per 60 seconds
        self.rate_limiter = RateLimiter(
            max_requests=int(target_apps_per_minute),
            time_window_seconds=60.0
        )
        
        # Semaphore for controlling concurrency
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Statistics
        self.stats = {
            "total_processed": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_rate_limited": 0,
            "total_duration": 0.0
        }
    
    async def process_single(
        self,
        job_url: str,
        application_func: Callable,
        *args,
        **kwargs
    ) -> ParallelApplicationResult:
        """
        Process a single application with rate limiting and retries.
        
        Args:
            job_url: URL of the job to apply to
            application_func: Async function to execute for application
            *args, **kwargs: Arguments to pass to application_func
            
        Returns:
            ParallelApplicationResult with status and details
        """
        app_id = f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(job_url) % 10000}"
        started_at = datetime.now()
        
        async with self.semaphore:
            # Wait for rate limiter
            await self.rate_limiter.acquire()
            
            for attempt in range(self.retry_attempts + 1):
                try:
                    logger.info(f"[{app_id}] Starting application to {job_url} (attempt {attempt + 1})")
                    
                    result = await application_func(*args, **kwargs)
                    
                    completed_at = datetime.now()
                    duration = (completed_at - started_at).total_seconds()
                    
                    logger.info(f"[{app_id}] Completed in {duration:.2f}s")
                    
                    return ParallelApplicationResult(
                        job_url=job_url,
                        status=ApplicationStatus.COMPLETED,
                        message=result.get("message", "Application submitted successfully"),
                        application_id=result.get("application_id", app_id),
                        started_at=started_at,
                        completed_at=completed_at,
                        duration_seconds=duration
                    )
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"[{app_id}] Attempt {attempt + 1} failed: {error_msg}")
                    
                    if attempt < self.retry_attempts:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.info(f"[{app_id}] Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        completed_at = datetime.now()
                        duration = (completed_at - started_at).total_seconds()
                        
                        # Check if it's a rate limit error
                        if "429" in error_msg or "rate limit" in error_msg.lower():
                            status = ApplicationStatus.RATE_LIMITED
                            self.stats["total_rate_limited"] += 1
                        else:
                            status = ApplicationStatus.FAILED
                            self.stats["total_failed"] += 1
                        
                        return ParallelApplicationResult(
                            job_url=job_url,
                            status=status,
                            message=f"Application failed after {self.retry_attempts + 1} attempts",
                            application_id=app_id,
                            started_at=started_at,
                            completed_at=completed_at,
                            duration_seconds=duration,
                            error=error_msg
                        )
    
    async def process_batch(
        self,
        jobs: List[Dict[str, Any]],
        application_func: Callable,
        progress_callback: Callable = None
    ) -> List[ParallelApplicationResult]:
        """
        Process multiple job applications in parallel.
        
        Args:
            jobs: List of job dictionaries with 'url' and other metadata
            application_func: Async function to execute for each application
            progress_callback: Optional callback function(progress_pct, current, total)
            
        Returns:
            List of ParallelApplicationResult for each job
        """
        total = len(jobs)
        results = []
        
        logger.info(f"Starting batch of {total} applications (max concurrent: {self.max_concurrent}, target: {self.target_apps_per_minute}/min)")
        
        batch_start_time = time.time()
        
        # Create tasks for all jobs
        tasks = []
        for i, job in enumerate(jobs):
            task = self.process_single(
                job_url=job["url"],
                application_func=application_func,
                job=job
            )
            tasks.append(task)
        
        # Process with progress tracking
        completed = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1
            
            if progress_callback:
                progress = int((completed / total) * 100)
                progress_callback(progress, completed, total)
        
        batch_duration = time.time() - batch_start_time
        
        # Update statistics
        self.stats["total_processed"] += total
        self.stats["total_completed"] += sum(1 for r in results if r.status == ApplicationStatus.COMPLETED)
        self.stats["total_duration"] += batch_duration
        
        # Calculate actual rate
        apps_per_minute = (total / batch_duration) * 60 if batch_duration > 0 else 0
        
        logger.info(
            f"Batch complete: {completed}/{total} apps in {batch_duration:.2f}s "
            f"({apps_per_minute:.2f} apps/min)"
        )
        
        return results
    
    def get_stats(self) -> BatchApplicationStats:
        """Get current processing statistics."""
        total_duration = self.stats["total_duration"]
        total_processed = self.stats["total_processed"]
        
        return BatchApplicationStats(
            total=total_processed,
            completed=self.stats["total_completed"],
            failed=self.stats["total_failed"],
            rate_limited=self.stats["total_rate_limited"],
            total_duration_seconds=total_duration,
            apps_per_minute=(total_processed / total_duration * 60) if total_duration > 0 else 0,
            average_duration_seconds=total_duration / total_processed if total_processed > 0 else 0
        )
    
    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = {
            "total_processed": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_rate_limited": 0,
            "total_duration": 0.0
        }


# Convenience function for 10 apps/minute processing
async def process_applications_parallel(
    jobs: List[Dict[str, Any]],
    application_func: Callable,
    max_concurrent: int = 3,
    target_apps_per_minute: float = 10.0,
    progress_callback: Callable = None
) -> tuple[List[ParallelApplicationResult], BatchApplicationStats]:
    """
    Convenience function to process applications at 10 apps/minute rate.
    
    Args:
        jobs: List of job dictionaries
        application_func: Async function for single application
        max_concurrent: Max parallel applications (default: 3)
        target_apps_per_minute: Target rate (default: 10.0)
        progress_callback: Optional progress callback
        
    Returns:
        Tuple of (results list, batch statistics)
    """
    processor = ParallelApplicationProcessor(
        max_concurrent=max_concurrent,
        target_apps_per_minute=target_apps_per_minute
    )
    
    results = await processor.process_batch(jobs, application_func, progress_callback)
    stats = processor.get_stats()
    
    return results, stats
