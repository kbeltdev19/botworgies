#!/usr/bin/env python3
"""
Hybrid Scraper - Uses jobspy as primary with fallback to direct APIs.

This scraper tries jobspy first (more reliable), then falls back to
direct API calls for Greenhouse/Lever when needed.
"""

import asyncio
from typing import List, Dict, Optional
import logging

from . import BaseJobBoardScraper, JobPosting, SearchCriteria
from .greenhouse_api import GreenhouseAPIScraper
from .lever_api import LeverAPIScraper
from .jobspy_scraper import JobSpyScraper

logger = logging.getLogger(__name__)


class HybridScraper(BaseJobBoardScraper):
    """
    Hybrid scraper that combines jobspy with direct API access.
    
    Strategy:
    1. Use jobspy for Indeed/LinkedIn/ZipRecruiter (primary)
    2. Use direct APIs for Greenhouse/Lever (ATS-specific)
    3. Merge and deduplicate results
    """
    
    def __init__(self, use_jobspy: bool = True, use_direct_apis: bool = True):
        super().__init__()
        self.use_jobspy = use_jobspy
        self.use_direct_apis = use_direct_apis
        self.name = "hybrid"
        
        # Initialize sub-scrapers
        self.jobspy = JobSpyScraper() if use_jobspy else None
        self.greenhouse = GreenhouseAPIScraper() if use_direct_apis else None
        self.lever = LeverAPIScraper() if use_direct_apis else None
        
    def get_default_headers(self) -> Dict[str, str]:
        return {"User-Agent": "Mozilla/5.0 (JobBot/1.0)"}
    
    async def search(self, criteria: SearchCriteria) -> List[JobPosting]:
        """
        Search using multiple sources and merge results.
        
        Args:
            criteria: Search criteria
            
        Returns:
            Merged, deduplicated list of jobs
        """
        all_jobs = []
        seen_urls = set()
        
        # 1. JobSpy search (Indeed, LinkedIn, ZipRecruiter)
        if self.jobspy and self.jobspy.available:
            try:
                logger.info("[Hybrid] Starting JobSpy search...")
                jobspy_jobs = await self.jobspy.search(criteria)
                logger.info(f"[Hybrid] JobSpy found {len(jobspy_jobs)} jobs")
                
                for job in jobspy_jobs:
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        all_jobs.append(job)
            except Exception as e:
                logger.warning(f"[Hybrid] JobSpy failed: {e}")
        
        # 2. Direct Greenhouse API (if jobspy didn't find enough)
        if self.greenhouse and len(all_jobs) < criteria.max_results:
            try:
                logger.info("[Hybrid] Starting Greenhouse API search...")
                async with self.greenhouse:
                    gh_jobs = await self.greenhouse.search(criteria)
                logger.info(f"[Hybrid] Greenhouse found {len(gh_jobs)} jobs")
                
                for job in gh_jobs:
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        all_jobs.append(job)
            except Exception as e:
                logger.warning(f"[Hybrid] Greenhouse API failed: {e}")
        
        # 3. Direct Lever API (if still need more)
        if self.lever and len(all_jobs) < criteria.max_results:
            try:
                logger.info("[Hybrid] Starting Lever API search...")
                async with self.lever:
                    lever_jobs = await self.lever.search(criteria)
                logger.info(f"[Hybrid] Lever found {len(lever_jobs)} jobs")
                
                for job in lever_jobs:
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        all_jobs.append(job)
            except Exception as e:
                logger.warning(f"[Hybrid] Lever API failed: {e}")
        
        logger.info(f"[Hybrid] Total unique jobs: {len(all_jobs)}")
        return all_jobs[:criteria.max_results]
    
    async def search_parallel(
        self,
        queries: List[str],
        locations: List[str],
        total_target: int = 1000,
        batch_size: int = 200
    ) -> List[JobPosting]:
        """
        Parallel batch search for large targets.
        
        Args:
            queries: List of job titles
            locations: List of locations
            total_target: Total jobs needed
            batch_size: Jobs per batch
            
        Returns:
            Combined list of jobs
        """
        all_jobs = []
        seen_urls = set()
        
        # Use jobspy for parallel batch scraping
        if self.jobspy and self.jobspy.available:
            try:
                logger.info(f"[Hybrid] Starting parallel batch search for {total_target} jobs...")
                jobs = await self.jobspy.search_in_batches(
                    queries=queries,
                    locations=locations,
                    total_target=total_target
                )
                
                for job in jobs:
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        all_jobs.append(job)
                
                logger.info(f"[Hybrid] JobSpy batch search: {len(all_jobs)} jobs")
            except Exception as e:
                logger.warning(f"[Hybrid] JobSpy batch failed: {e}")
        
        # If we still need more, try direct APIs
        remaining = total_target - len(all_jobs)
        if remaining > 100 and self.use_direct_apis:
            # Search direct APIs with broader criteria
            for query in queries[:3]:  # Top 3 queries
                if len(all_jobs) >= total_target:
                    break
                
                criteria = SearchCriteria(
                    query=query,
                    location=locations[0] if locations else "Remote",
                    max_results=remaining // 3,
                )
                
                try:
                    more_jobs = await self.search(criteria)
                    for job in more_jobs:
                        if job.url not in seen_urls:
                            seen_urls.add(job.url)
                            all_jobs.append(job)
                except Exception as e:
                    logger.warning(f"[Hybrid] Direct API search failed: {e}")
        
        logger.info(f"[Hybrid] Final total: {len(all_jobs)} jobs")
        return all_jobs[:total_target]
    
    def get_ats_type(self, url: str) -> Optional[str]:
        """Detect ATS type from URL."""
        url_lower = url.lower()
        if 'greenhouse' in url_lower:
            return 'greenhouse'
        elif 'lever' in url_lower:
            return 'lever'
        elif 'indeed' in url_lower:
            return 'indeed'
        elif 'linkedin' in url_lower:
            return 'linkedin'
        elif 'ziprecruiter' in url_lower:
            return 'ziprecruiter'
        return None


# Convenience function
async def scrape_jobs_hybrid(
    queries: List[str],
    locations: List[str],
    total_target: int = 1000,
    use_jobspy: bool = True,
    use_direct_apis: bool = True
) -> List[JobPosting]:
    """
    Quick function to scrape jobs using hybrid approach.
    
    Args:
        queries: List of job titles
        locations: List of locations
        total_target: Total jobs needed
        use_jobspy: Use jobspy scraper
        use_direct_apis: Use direct API scrapers
        
    Returns:
        List of JobPosting objects
    """
    scraper = HybridScraper(
        use_jobspy=use_jobspy,
        use_direct_apis=use_direct_apis
    )
    
    return await scraper.search_parallel(
        queries=queries,
        locations=locations,
        total_target=total_target
    )
