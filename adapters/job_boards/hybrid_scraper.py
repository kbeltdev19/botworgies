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
    Hybrid scraper that combines jobspy with BrowserBase and direct API access.
    
    Strategy:
    1. Use jobspy for Indeed/LinkedIn/ZipRecruiter (primary - HTTP)
    2. Use BrowserBase for JavaScript-heavy sites (LinkedIn, Indeed if jobspy fails)
    3. Use direct APIs for Greenhouse/Lever (ATS-specific)
    4. Merge and deduplicate results
    """
    
    def __init__(self, use_jobspy: bool = True, use_browserbase: bool = True, use_direct_apis: bool = False):
        super().__init__()
        self.use_jobspy = use_jobspy
        self.use_browserbase = use_browserbase
        self.use_direct_apis = use_direct_apis
        self.name = "hybrid"
        self.browser_manager = None
        
        # Initialize sub-scrapers
        self.jobspy = JobSpyScraper() if use_jobspy else None
        self.browserbase = None  # Will be initialized with shared browser_manager
        self.greenhouse = GreenhouseAPIScraper() if use_direct_apis else None
        self.lever = LeverAPIScraper() if use_direct_apis else None
    
    async def initialize(self):
        """Initialize browser manager if using BrowserBase."""
        if self.use_browserbase:
            from browser.stealth_manager import StealthBrowserManager
            self.browser_manager = StealthBrowserManager(prefer_local=False)
            await self.browser_manager.initialize()
            
            # Initialize BrowserBase scraper with shared manager
            from .browserbase_scraper import BrowserBaseScraper
            self.browserbase = BrowserBaseScraper(self.browser_manager)
    
    async def close(self):
        """Cleanup browser manager."""
        if self.browser_manager:
            await self.browser_manager.close()
            self.browser_manager = None
        
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
        
        Strategy:
        1. Try jobspy first (fastest, HTTP-based)
        2. If insufficient, use BrowserBase (handles JavaScript, anti-bot)
        3. If still need more, use direct APIs
        
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
        
        # 1. Use jobspy for parallel batch scraping (primary)
        if self.jobspy and self.jobspy.available:
            try:
                logger.info(f"[Hybrid] Phase 1: JobSpy batch search for {total_target} jobs...")
                jobs = await self.jobspy.search_in_batches(
                    queries=queries,
                    locations=locations,
                    total_target=total_target
                )
                
                for job in jobs:
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        all_jobs.append(job)
                
                logger.info(f"[Hybrid] JobSpy found: {len(all_jobs)} jobs")
            except Exception as e:
                logger.warning(f"[Hybrid] JobSpy batch failed: {e}")
        
        # 2. Use BrowserBase if we need more jobs (handles JavaScript-heavy sites)
        remaining = total_target - len(all_jobs)
        if remaining > 50 and self.use_browserbase and self.browserbase:
            try:
                logger.info(f"[Hybrid] Phase 2: BrowserBase scraping for {remaining} more jobs...")
                bb_jobs = await self.browserbase.search_parallel(
                    queries=queries[:3],  # Top 3 queries
                    locations=locations[:2],  # Top 2 locations
                    total_target=remaining
                )
                
                for job in bb_jobs:
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        all_jobs.append(job)
                
                logger.info(f"[Hybrid] BrowserBase found: {len(bb_jobs)} jobs (total: {len(all_jobs)})")
            except Exception as e:
                logger.warning(f"[Hybrid] BrowserBase scraping failed: {e}")
        
        # 3. Use direct APIs as final fallback
        remaining = total_target - len(all_jobs)
        if remaining > 50 and self.use_direct_apis:
            logger.info(f"[Hybrid] Phase 3: Direct API search for {remaining} more jobs...")
            for query in queries[:2]:  # Top 2 queries
                if len(all_jobs) >= total_target:
                    break
                
                criteria = SearchCriteria(
                    query=query,
                    location=locations[0] if locations else "Remote",
                    max_results=remaining // 2,
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
    use_browserbase: bool = True,
    use_direct_apis: bool = False
) -> List[JobPosting]:
    """
    Quick function to scrape jobs using hybrid approach.
    
    Args:
        queries: List of job titles
        locations: List of locations
        total_target: Total jobs needed
        use_jobspy: Use jobspy scraper (HTTP - fastest)
        use_browserbase: Use BrowserBase (handles JavaScript/anti-bot)
        use_direct_apis: Use direct API scrapers (Greenhouse/Lever)
        
    Returns:
        List of JobPosting objects
    """
    scraper = HybridScraper(
        use_jobspy=use_jobspy,
        use_browserbase=use_browserbase,
        use_direct_apis=use_direct_apis
    )
    
    # Initialize BrowserBase if needed
    if use_browserbase:
        await scraper.initialize()
    
    try:
        jobs = await scraper.search_parallel(
            queries=queries,
            locations=locations,
            total_target=total_target
        )
    finally:
        if use_browserbase:
            await scraper.close()
    
    return jobs
