"""
Job Source Router - Aggregates jobs from multiple platforms.
Handles deduplication, priority ordering, and fallbacks.
"""

import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

from .base import JobPosting, SearchConfig

logger = logging.getLogger(__name__)


@dataclass
class SourceResult:
    """Result from a single source."""
    source: str
    jobs: List[JobPosting]
    duration_seconds: float
    error: Optional[str] = None


class JobSourceRouter:
    """
    Aggregates jobs from multiple platforms with intelligent routing.
    
    Priority order (safest first):
    1. API-based (Greenhouse, Lever) - No ban risk
    2. Easy scraping (HN Jobs, WeWorkRemotely) - Minimal risk
    3. Aggressive (Indeed, LinkedIn) - High ban risk, last resort
    """
    
    # Source priority (order matters - safest first)
    PRIORITY_ORDER = [
        'greenhouse',    # API-based, 0% ban risk
        'hn_jobs',       # Algolia API, 0% ban risk
        'weworkremotely', # Simple scraping, low risk
        # 'lever',       # API changed, disabled for now
        # 'indeed',      # Cloudflare blocked
        # 'linkedin',    # High ban risk
    ]
    
    def __init__(self):
        self.adapters = {}
        self._initialized = False
    
    async def initialize(self):
        """Lazy-load adapters."""
        if self._initialized:
            return
        
        # Import adapters
        from .greenhouse import GreenhouseAdapter
        from .hn_jobs import HNJobsAdapter
        from .weworkremotely import WeWorkRemotelyAdapter
        
        self.adapters = {
            'greenhouse': GreenhouseAdapter(),
            'hn_jobs': HNJobsAdapter(),
            'weworkremotely': WeWorkRemotelyAdapter(),
        }
        
        self._initialized = True
    
    async def close(self):
        """Close all adapters."""
        for adapter in self.adapters.values():
            if hasattr(adapter, 'close'):
                await adapter.close()
    
    async def search_all(
        self,
        criteria: SearchConfig,
        sources: List[str] = None,
        max_results: int = 100,
        timeout_per_source: int = 30
    ) -> Dict:
        """
        Search all configured sources and aggregate results.
        
        Returns:
            {
                "jobs": [...],
                "sources": {
                    "greenhouse": {"count": 50, "duration": 2.3},
                    ...
                },
                "total": 150,
                "deduplicated": 120
            }
        """
        await self.initialize()
        
        sources = sources or self.PRIORITY_ORDER
        results = []
        source_stats = {}
        
        # Fetch from all sources concurrently
        tasks = []
        for source in sources:
            if source in self.adapters:
                tasks.append(self._fetch_source(source, criteria, timeout_per_source))
        
        source_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        all_jobs = []
        for result in source_results:
            if isinstance(result, Exception):
                logger.error(f"Source error: {result}")
                continue
            
            if isinstance(result, SourceResult):
                source_stats[result.source] = {
                    "count": len(result.jobs),
                    "duration_seconds": round(result.duration_seconds, 2),
                    "error": result.error
                }
                all_jobs.extend(result.jobs)
        
        # Deduplicate
        total_before = len(all_jobs)
        unique_jobs = self._deduplicate(all_jobs)
        
        # Sort by relevance (could add scoring later)
        unique_jobs = unique_jobs[:max_results]
        
        return {
            "jobs": unique_jobs,
            "sources": source_stats,
            "total_raw": total_before,
            "total_deduplicated": len(unique_jobs)
        }
    
    async def _fetch_source(
        self,
        source: str,
        criteria: SearchConfig,
        timeout: int
    ) -> SourceResult:
        """Fetch jobs from a single source with timeout."""
        adapter = self.adapters.get(source)
        if not adapter:
            return SourceResult(source=source, jobs=[], duration_seconds=0, error="Adapter not found")
        
        start = datetime.now()
        
        try:
            jobs = await asyncio.wait_for(
                adapter.search_jobs(criteria),
                timeout=timeout
            )
            duration = (datetime.now() - start).total_seconds()
            
            return SourceResult(
                source=source,
                jobs=jobs,
                duration_seconds=duration
            )
            
        except asyncio.TimeoutError:
            duration = (datetime.now() - start).total_seconds()
            return SourceResult(
                source=source,
                jobs=[],
                duration_seconds=duration,
                error="Timeout"
            )
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"Error fetching {source}: {e}")
            return SourceResult(
                source=source,
                jobs=[],
                duration_seconds=duration,
                error=str(e)
            )
    
    def _deduplicate(self, jobs: List[JobPosting]) -> List[JobPosting]:
        """Remove duplicate jobs based on company+title combination."""
        seen = set()
        unique = []
        
        for job in jobs:
            # Create a normalized key for deduplication
            key = self._job_key(job)
            if key not in seen:
                seen.add(key)
                unique.append(job)
        
        return unique
    
    def _job_key(self, job: JobPosting) -> str:
        """Generate a unique key for a job."""
        company = job.company.lower().replace(' ', '').replace('-', '')[:20]
        title = job.title.lower().replace(' ', '').replace('-', '')[:30]
        return f"{company}-{title}"


async def test_router():
    """Test the job source router."""
    router = JobSourceRouter()
    
    criteria = SearchConfig(
        roles=['software', 'engineer'],
        locations=['Remote'],
        posted_within_days=30
    )
    
    try:
        print("Searching all sources...")
        results = await router.search_all(criteria, max_results=50)
        
        print(f"\n=== Results ===")
        print(f"Total raw: {results['total_raw']}")
        print(f"After dedup: {results['total_deduplicated']}")
        
        print(f"\n=== Sources ===")
        for source, stats in results['sources'].items():
            print(f"  {source}: {stats['count']} jobs in {stats['duration_seconds']}s")
            if stats.get('error'):
                print(f"    Error: {stats['error']}")
        
        print(f"\n=== Sample Jobs ===")
        for job in results['jobs'][:10]:
            print(f"  • [{job.platform.value if hasattr(job.platform, 'value') else job.platform}] {job.title} at {job.company}")
            print(f"    {job.location}")
    
    finally:
        await router.close()


if __name__ == "__main__":
    asyncio.run(test_router())
