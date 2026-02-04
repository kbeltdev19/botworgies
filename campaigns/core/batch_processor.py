#!/usr/bin/env python3
"""
Batch Processor - Process jobs in optimized batches with platform grouping.

Impact: Better session reuse, controlled concurrency, checkpointing
"""

import asyncio
from typing import List, Dict, Any, Callable, TypeVar
from dataclasses import dataclass
import json
from datetime import datetime
from pathlib import Path
import logging

from .browser_pool import get_browser_pool
from .rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class BatchJob:
    """A job in a batch."""
    job_id: str
    platform: str
    job_data: Dict[str, Any]
    priority: int = 50  # Lower = higher priority
    retry_count: int = 0
    max_retries: int = 3


@dataclass 
class BatchResult:
    """Result of processing a batch job."""
    job_id: str
    success: bool
    result: Any
    error: Optional[str] = None
    duration_seconds: float = 0.0
    retry_count: int = 0


class BatchProcessor:
    """
    Process jobs in optimized batches.
    
    Features:
    - Groups jobs by platform for session reuse
    - Controlled concurrency with semaphore
    - Checkpointing after each batch
    - Retry logic for failed jobs
    """
    
    def __init__(
        self,
        batch_size: int = 25,
        max_concurrent: int = 7,
        checkpoint_dir: str = "campaigns/output/checkpoints"
    ):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.browser_pool = get_browser_pool()
        self.rate_limiter = get_rate_limiter()
        
        self.stats = {
            'batches_processed': 0,
            'jobs_processed': 0,
            'jobs_succeeded': 0,
            'jobs_failed': 0,
            'jobs_retried': 0,
        }
    
    async def process_batch(
        self,
        jobs: List[BatchJob],
        processor_func: Callable[[BatchJob, Any], T],
        browser_manager=None
    ) -> List[BatchResult]:
        """
        Process jobs with controlled concurrency.
        
        Args:
            jobs: List of BatchJob objects
            processor_func: Function to process each job (job, session) -> result
            browser_manager: StealthBrowserManager instance
            
        Returns:
            List of BatchResult objects
        """
        results = []
        
        # Sort by priority (lower number = higher priority)
        jobs.sort(key=lambda j: j.priority)
        
        # Process in batches
        for i in range(0, len(jobs), self.batch_size):
            batch = jobs[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(jobs) - 1) // self.batch_size + 1
            
            logger.info(f"[Batch] Processing batch {batch_num}/{total_batches} ({len(batch)} jobs)")
            
            # Group by platform for session reuse
            by_platform = self._group_by_platform(batch)
            
            # Process each platform group
            tasks = []
            for platform, platform_jobs in by_platform.items():
                task = self._process_platform_batch(
                    platform, platform_jobs, processor_func, browser_manager
                )
                tasks.append(task)
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"[Batch] Platform batch failed: {result}")
                elif isinstance(result, list):
                    results.extend(result)
            
            self.stats['batches_processed'] += 1
            
            # Checkpoint after each batch
            await self._save_checkpoint(results)
            
            logger.info(f"[Batch] Completed batch {batch_num}/{total_batches}")
        
        return results
    
    def _group_by_platform(self, jobs: List[BatchJob]) -> Dict[str, List[BatchJob]]:
        """Group jobs by platform for efficient session reuse."""
        groups = {}
        for job in jobs:
            platform = job.platform.lower()
            if platform not in groups:
                groups[platform] = []
            groups[platform].append(job)
        return groups
    
    async def _process_platform_batch(
        self,
        platform: str,
        jobs: List[BatchJob],
        processor_func: Callable,
        browser_manager
    ) -> List[BatchResult]:
        """Process all jobs for a platform using shared session."""
        results = []
        
        async with self.semaphore:
            # Acquire session for this platform
            session = None
            if browser_manager:
                try:
                    session = await self.browser_pool.acquire(platform, browser_manager)
                except Exception as e:
                    logger.error(f"[Batch] Failed to acquire session for {platform}: {e}")
                    # Return failures for all jobs
                    return [
                        BatchResult(
                            job_id=job.job_id,
                            success=False,
                            result=None,
                            error=f"Session acquisition failed: {e}"
                        )
                        for job in jobs
                    ]
            
            try:
                for job in jobs:
                    # Rate limit
                    allowed = await self.rate_limiter.acquire(platform)
                    if not allowed:
                        results.append(BatchResult(
                            job_id=job.job_id,
                            success=False,
                            result=None,
                            error="Rate limited - circuit open"
                        ))
                        continue
                    
                    # Process with retry
                    result = await self._process_with_retry(
                        job, processor_func, session
                    )
                    results.append(result)
                    
                    # Update stats
                    self.stats['jobs_processed'] += 1
                    if result.success:
                        self.stats['jobs_succeeded'] += 1
                        self.rate_limiter.record_success(platform)
                        if session:
                            await self.browser_pool.release(platform, success=True)
                    else:
                        self.stats['jobs_failed'] += 1
                        self.rate_limiter.record_failure(platform, result.error or "Unknown")
                        if session:
                            await self.browser_pool.release(platform, success=False)
                            
            finally:
                # Note: We don't close the session here - it's pooled
                pass
        
        return results
    
    async def _process_with_retry(
        self,
        job: BatchJob,
        processor_func: Callable,
        session
    ) -> BatchResult:
        """Process a job with retry logic."""
        import time
        
        start_time = time.time()
        last_error = None
        
        for attempt in range(job.max_retries + 1):
            try:
                result = await processor_func(job, session)
                duration = time.time() - start_time
                
                return BatchResult(
                    job_id=job.job_id,
                    success=True,
                    result=result,
                    duration_seconds=duration,
                    retry_count=attempt
                )
                
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"[Batch] Job {job.job_id} failed (attempt {attempt + 1}/{job.max_retries + 1}): {e}"
                )
                
                if attempt < job.max_retries:
                    # Exponential backoff with jitter
                    delay = min(2 ** attempt, 30) + (attempt * 0.5)
                    await asyncio.sleep(delay)
                    self.stats['jobs_retried'] += 1
        
        # All retries exhausted
        duration = time.time() - start_time
        return BatchResult(
            job_id=job.job_id,
            success=False,
            result=None,
            error=last_error,
            duration_seconds=duration,
            retry_count=job.max_retries
        )
    
    async def _save_checkpoint(self, results: List[BatchResult]):
        """Save checkpoint of processed jobs."""
        checkpoint_file = self.checkpoint_dir / f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        checkpoint_data = {
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats,
            'results': [
                {
                    'job_id': r.job_id,
                    'success': r.success,
                    'error': r.error,
                    'duration': r.duration_seconds,
                    'retries': r.retry_count,
                }
                for r in results
            ]
        }
        
        try:
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)
        except Exception as e:
            logger.warning(f"[Batch] Failed to save checkpoint: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        success_rate = (
            self.stats['jobs_succeeded'] / self.stats['jobs_processed'] * 100
            if self.stats['jobs_processed'] > 0 else 0
        )
        
        return {
            **self.stats,
            'success_rate': f"{success_rate:.1f}%",
            'pool_stats': self.browser_pool.get_stats(),
            'rate_limiter_stats': self.rate_limiter.get_stats(),
        }


# Convenience function
async def process_jobs_batch(
    jobs: List[BatchJob],
    processor: Callable,
    browser_manager=None,
    batch_size: int = 25,
    max_concurrent: int = 7
) -> List[BatchResult]:
    """Process jobs in batches."""
    processor = BatchProcessor(
        batch_size=batch_size,
        max_concurrent=max_concurrent
    )
    return await processor.process_batch(jobs, processor, browser_manager)
