"""
Job Pipeline - Producer/Consumer architecture for continuous job scraping + applying.

Flow:
1. Scraper (Producer) fills job queue from multiple platforms
2. Applicator (Consumer) pulls jobs and applies
3. When queue drops below threshold, scraper refills
4. Never runs out of jobs during a batch run
"""

import asyncio
from asyncio import Queue
from typing import List, Set, Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class QueuedJob:
    """Job in the application queue."""
    job_id: str
    title: str
    company: str
    url: str
    platform: str
    location: str
    remote: bool
    status: JobStatus = JobStatus.QUEUED
    queued_at: datetime = field(default_factory=datetime.now)
    applied_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class PipelineConfig:
    """Configuration for the job pipeline."""
    # Queue thresholds
    initial_batch_size: int = 100  # Jobs to fetch before starting
    refill_threshold: int = 25     # Refill when queue drops to this
    refill_batch_size: int = 50    # Jobs to fetch on refill
    
    # Application limits
    max_applications: int = 250    # Total apps in this run
    concurrent_applications: int = 3  # Parallel browser sessions
    
    # Timing
    min_delay_between_apps: float = 5.0  # Seconds
    max_delay_between_apps: float = 15.0
    
    # Filters
    roles: List[str] = field(default_factory=lambda: ["software engineer"])
    locations: List[str] = field(default_factory=lambda: ["Remote"])
    exclude_companies: Set[str] = field(default_factory=set)
    already_applied: Set[str] = field(default_factory=set)


class JobPipeline:
    """
    Manages the continuous job scraping and application pipeline.
    
    Usage:
        pipeline = JobPipeline(config)
        await pipeline.run(
            scraper=my_scraper_func,
            applicator=my_apply_func,
            on_progress=my_callback
        )
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.job_queue: Queue[QueuedJob] = Queue()
        self.seen_jobs: Set[str] = set()  # Deduplication
        self.applied_jobs: List[QueuedJob] = []
        self.failed_jobs: List[QueuedJob] = []
        self.skipped_jobs: List[QueuedJob] = []
        
        # State
        self._running = False
        self._scrape_offset = 0  # For pagination
        self._total_scraped = 0
        self._total_applied = 0
        
        # Locks
        self._scrape_lock = asyncio.Lock()
    
    async def run(
        self,
        scraper: Callable,
        applicator: Callable,
        on_progress: Optional[Callable] = None
    ) -> Dict:
        """
        Run the pipeline until max_applications reached or no more jobs.
        
        Args:
            scraper: async function(roles, locations, offset, limit) -> List[Job]
            applicator: async function(job) -> ApplicationResult
            on_progress: callback(stats_dict) called after each application
        
        Returns:
            Final statistics dict
        """
        self._running = True
        
        logger.info(f"Starting pipeline: target={self.config.max_applications} apps")
        
        # Initial batch scrape
        await self._scrape_batch(scraper, self.config.initial_batch_size)
        
        if self.job_queue.empty():
            logger.warning("No jobs found in initial scrape")
            return self._get_stats()
        
        logger.info(f"Initial queue: {self.job_queue.qsize()} jobs")
        
        # Start consumer tasks
        consumers = [
            asyncio.create_task(self._consumer(applicator, on_progress))
            for _ in range(self.config.concurrent_applications)
        ]
        
        # Start refill monitor
        refiller = asyncio.create_task(self._refill_monitor(scraper))
        
        # Wait for completion
        try:
            await asyncio.gather(*consumers)
        finally:
            self._running = False
            refiller.cancel()
        
        return self._get_stats()
    
    async def _scrape_batch(self, scraper: Callable, limit: int):
        """Scrape a batch of jobs and add to queue."""
        async with self._scrape_lock:
            try:
                logger.info(f"Scraping batch: offset={self._scrape_offset}, limit={limit}")
                
                jobs = await scraper(
                    roles=self.config.roles,
                    locations=self.config.locations,
                    offset=self._scrape_offset,
                    limit=limit
                )
                
                added = 0
                for job in jobs:
                    # Skip if already seen
                    job_key = f"{job.company}-{job.title}".lower()
                    if job_key in self.seen_jobs:
                        continue
                    
                    # Skip if already applied
                    if job.url in self.config.already_applied:
                        continue
                    
                    # Skip excluded companies
                    if job.company.lower() in {c.lower() for c in self.config.exclude_companies}:
                        continue
                    
                    self.seen_jobs.add(job_key)
                    
                    queued = QueuedJob(
                        job_id=job.id,
                        title=job.title,
                        company=job.company,
                        url=job.url,
                        platform=job.platform.value if hasattr(job.platform, 'value') else str(job.platform),
                        location=job.location,
                        remote=job.remote
                    )
                    
                    await self.job_queue.put(queued)
                    added += 1
                
                self._scrape_offset += limit
                self._total_scraped += added
                
                logger.info(f"Added {added} jobs to queue (total: {self.job_queue.qsize()})")
                
            except Exception as e:
                logger.error(f"Scrape failed: {e}")
    
    async def _consumer(self, applicator: Callable, on_progress: Optional[Callable]):
        """Consumer task that applies to jobs from queue."""
        import random
        
        while self._running:
            # Check if we've hit the limit
            if self._total_applied >= self.config.max_applications:
                logger.info("Reached max applications limit")
                break
            
            try:
                # Get next job (with timeout to check _running)
                try:
                    job = await asyncio.wait_for(self.job_queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    if self.job_queue.empty() and self._total_applied > 0:
                        logger.info("Queue empty, stopping consumer")
                        break
                    continue
                
                job.status = JobStatus.IN_PROGRESS
                
                # Apply to job
                try:
                    result = await applicator(job)
                    
                    if result.get('status') == 'success':
                        job.status = JobStatus.APPLIED
                        job.applied_at = datetime.now()
                        self.applied_jobs.append(job)
                        self._total_applied += 1
                    elif result.get('status') == 'skipped':
                        job.status = JobStatus.SKIPPED
                        self.skipped_jobs.append(job)
                    else:
                        job.status = JobStatus.FAILED
                        job.error = result.get('error', 'Unknown error')
                        self.failed_jobs.append(job)
                    
                except Exception as e:
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    self.failed_jobs.append(job)
                    logger.error(f"Application failed: {e}")
                
                # Progress callback
                if on_progress:
                    await on_progress(self._get_stats())
                
                # Human-like delay
                delay = random.uniform(
                    self.config.min_delay_between_apps,
                    self.config.max_delay_between_apps
                )
                await asyncio.sleep(delay)
                
            except Exception as e:
                logger.error(f"Consumer error: {e}")
                await asyncio.sleep(1)
    
    async def _refill_monitor(self, scraper: Callable):
        """Monitor queue and refill when low."""
        while self._running:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                queue_size = self.job_queue.qsize()
                
                if queue_size < self.config.refill_threshold:
                    logger.info(f"Queue low ({queue_size}), refilling...")
                    await self._scrape_batch(scraper, self.config.refill_batch_size)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Refill monitor error: {e}")
    
    def _get_stats(self) -> Dict:
        """Get current pipeline statistics."""
        return {
            "queue_size": self.job_queue.qsize(),
            "total_scraped": self._total_scraped,
            "total_applied": self._total_applied,
            "total_failed": len(self.failed_jobs),
            "total_skipped": len(self.skipped_jobs),
            "progress_percent": round(
                (self._total_applied / self.config.max_applications) * 100, 1
            ) if self.config.max_applications > 0 else 0,
            "applied_jobs": [
                {"company": j.company, "title": j.title, "url": j.url}
                for j in self.applied_jobs[-10:]  # Last 10
            ],
            "failed_jobs": [
                {"company": j.company, "title": j.title, "error": j.error}
                for j in self.failed_jobs[-5:]  # Last 5
            ]
        }
    
    def stop(self):
        """Stop the pipeline gracefully."""
        self._running = False


# Example usage
async def example_run():
    """Example of how to use the pipeline."""
    from adapters.router import JobSourceRouter
    from adapters.base import SearchConfig
    
    # Initialize router
    router = JobSourceRouter()
    await router.initialize()
    
    # Scraper function
    async def scraper(roles, locations, offset, limit):
        criteria = SearchConfig(
            roles=roles,
            locations=locations,
            posted_within_days=30
        )
        results = await router.search_all(criteria, max_results=limit)
        return results['jobs']
    
    # Applicator function (mock)
    async def applicator(job):
        print(f"Applying to: {job.title} at {job.company}")
        # In real implementation, this would use browser automation
        return {"status": "success"}
    
    # Progress callback
    async def on_progress(stats):
        print(f"Progress: {stats['total_applied']}/{stats['total_scraped']} applied")
    
    # Run pipeline
    config = PipelineConfig(
        initial_batch_size=50,
        refill_threshold=10,
        max_applications=20,
        concurrent_applications=2,
        roles=["software", "engineer"],
        locations=["Remote"]
    )
    
    pipeline = JobPipeline(config)
    
    try:
        stats = await pipeline.run(
            scraper=scraper,
            applicator=applicator,
            on_progress=on_progress
        )
        print(f"\nFinal stats: {stats}")
    finally:
        await router.close()


if __name__ == "__main__":
    asyncio.run(example_run())
