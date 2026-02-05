#!/usr/bin/env python3
"""
JobSpy Scraper - Parallel job scraping with jobspy library.

Supports parallel searches across multiple queries and locations.
"""

import asyncio
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
import logging

from ..job_boards import BaseJobBoardScraper, SearchCriteria, JobPosting

logger = logging.getLogger(__name__)


class JobSpyScraper(BaseJobBoardScraper):
    """
    Scraper using the jobspy library.
    
    Supports:
    - Indeed
    - LinkedIn
    - ZipRecruiter
    - Glassdoor
    - Google
    """
    
    # Supported sites by jobspy
    SUPPORTED_SITES = ["indeed", "linkedin", "zip_recruiter", "glassdoor", "google"]
    
    def __init__(self, sites: List[str] = None):
        super().__init__()
        # Filter to only supported sites
        if sites:
            self.sites = [s for s in sites if s in self.SUPPORTED_SITES]
        else:
            self.sites = ["indeed", "linkedin", "zip_recruiter"]
        
        if not self.sites:
            self.sites = ["indeed"]  # Default fallback
        
        self.name = "jobspy"
        
        try:
            from jobspy import scrape_jobs
            self.scrape_jobs = scrape_jobs
            self.available = True
        except ImportError:
            logger.warning("jobspy not available")
            self.available = False
            self.scrape_jobs = None
    
    def get_default_headers(self) -> Dict[str, str]:
        """Return default headers."""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def search(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Search for jobs using jobspy."""
        if not self.available:
            logger.error("jobspy not available")
            return []
        
        jobs = []
        
        try:
            # Use jobspy to scrape
            import pandas as pd
            
            logger.info(f"[JobSpy] Searching: '{criteria.query}' in '{criteria.location}'")
            
            jobs_df = self.scrape_jobs(
                site_name=self.sites,
                search_term=criteria.query,
                location=criteria.location,
                results_wanted=min(criteria.max_results, 100),
                hours_old=criteria.posted_within_days * 24,
            )
            
            if jobs_df is None or jobs_df.empty:
                logger.info(f"[JobSpy] No jobs found")
                return []
            
            # Convert to JobPosting objects
            for _, row in jobs_df.iterrows():
                try:
                    job = self._convert_to_jobposting(row)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.debug(f"[JobSpy] Failed to convert job: {e}")
                    continue
            
            logger.info(f"[JobSpy] Found {len(jobs)} jobs")
            
        except Exception as e:
            logger.error(f"[JobSpy] Search failed: {e}")
        
        return jobs
    
    def _convert_to_jobposting(self, row) -> Optional[JobPosting]:
        """Convert jobspy row to JobPosting."""
        try:
            from datetime import datetime
            
            job_url = str(row.get('job_url', ''))
            if not job_url or 'http' not in job_url:
                return None
            
            # Detect platform from URL
            platform = self._detect_platform(job_url)
            
            # Parse date
            date_posted = None
            if 'date_posted' in row and pd.notna(row['date_posted']):
                try:
                    date_posted = pd.to_datetime(row['date_posted'])
                except:
                    pass
            
            return JobPosting(
                id=f"{platform}_{abs(hash(job_url)) % 10000000}",
                title=str(row.get('title', '')).strip(),
                company=str(row.get('company', '')).strip(),
                location=str(row.get('location', '')).strip(),
                description=str(row.get('description', ''))[:500],
                url=job_url,
                source="jobspy",
                posted_date=date_posted,
                employment_type=str(row.get('job_type', '')) if pd.notna(row.get('job_type')) else None,
                remote='remote' in str(row.get('location', '')).lower(),
                easy_apply=row.get('easy_apply', False) if 'easy_apply' in row else False,
                raw_data=row.to_dict(),
            )
        except Exception as e:
            logger.debug(f"[JobSpy] Conversion error: {e}")
            return None
    
    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        url_lower = url.lower()
        if 'indeed' in url_lower:
            return 'indeed'
        elif 'linkedin' in url_lower:
            return 'linkedin'
        elif 'ziprecruiter' in url_lower or 'zip_recruiter' in url_lower:
            return 'ziprecruiter'
        elif 'glassdoor' in url_lower:
            return 'glassdoor'
        else:
            return 'unknown'
    
    async def search_parallel(
        self,
        queries: List[str],
        locations: List[str],
        max_results: int = 100,
        max_workers: int = 4,
        per_search_timeout: int = 30
    ) -> List[JobPosting]:
        """
        Search multiple queries/locations in parallel.
        
        Args:
            queries: List of job titles to search
            locations: List of locations
            max_results: Max results per search
            max_workers: Max parallel workers
            per_search_timeout: Timeout per search in seconds
            
        Returns:
            Combined list of unique jobs
        """
        if not self.available:
            return []
        
        # Create all search combinations
        search_configs = []
        for query in queries:
            for location in locations:
                search_configs.append(SearchCriteria(
                    query=query,
                    location=location,
                    max_results=max_results,
                ))
        
        logger.info(f"[JobSpy] Starting {len(search_configs)} parallel searches")
        
        # Execute in parallel
        all_jobs = []
        seen_urls = set()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all searches
            futures = [
                executor.submit(self._search_sync, criteria)
                for criteria in search_configs
            ]
            
            # Collect results as they complete
            for i, future in enumerate(futures):
                try:
                    jobs = future.result(timeout=per_search_timeout)
                    logger.info(f"[JobSpy] Search {i+1}/{len(search_configs)}: {len(jobs)} jobs")
                    
                    # Deduplicate
                    for job in jobs:
                        if job.url not in seen_urls:
                            seen_urls.add(job.url)
                            all_jobs.append(job)
                    
                except Exception as e:
                    logger.warning(f"[JobSpy] Search failed or timed out: {e}")
        
        logger.info(f"[JobSpy] Total unique jobs: {len(all_jobs)}")
        return all_jobs
    
    def _search_sync(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Synchronous search for thread pool."""
        import asyncio
        return asyncio.run(self.search(criteria))
    
    async def search_in_batches(
        self,
        queries: List[str],
        locations: List[str],
        total_target: int = 1000,
        batch_size: int = 200,
        max_search_time: int = 30  # Max seconds to spend on JobSpy (reduced for faster fallback)
    ) -> List[JobPosting]:
        """
        Search in batches until target is reached.
        
        Args:
            queries: Job titles
            locations: Locations
            total_target: Total jobs needed
            batch_size: Jobs per batch
            max_search_time: Max seconds to spend before giving up
            
        Returns:
            List of jobs (up to total_target)
        """
        if not self.available:
            return []
        
        import time
        start_time = time.time()
        all_jobs = []
        seen_urls = set()
        
        # Process queries in chunks (smaller chunks for faster response)
        query_chunks = [queries[i:i+2] for i in range(0, len(queries), 2)]
        
        for chunk_num, query_chunk in enumerate(query_chunks):
            # Check if we've exceeded max search time
            elapsed = time.time() - start_time
            if elapsed > max_search_time:
                logger.warning(f"[JobSpy] Max search time ({max_search_time}s) exceeded, returning {len(all_jobs)} jobs")
                break
            
            if len(all_jobs) >= total_target:
                break
            
            logger.info(f"[JobSpy] Batch {chunk_num+1}: Searching {query_chunk}")
            
            # Search this chunk with shorter timeout per search
            jobs = await self.search_parallel(
                queries=query_chunk,
                locations=locations[:2],  # Limit to top 2 locations
                max_results=50,
                max_workers=2,  # Reduced parallelism
                per_search_timeout=15  # 15 seconds per search max
            )
            
            # Add unique jobs
            for job in jobs:
                if job.url not in seen_urls:
                    seen_urls.add(job.url)
                    all_jobs.append(job)
                    
                    if len(all_jobs) >= total_target:
                        break
            
            logger.info(f"[JobSpy] Progress: {len(all_jobs)}/{total_target} jobs (elapsed: {elapsed:.1f}s)")
            
            # Small delay between batches
            await asyncio.sleep(0.5)
        
        return all_jobs[:total_target]
    
    def get_ats_type(self, url: str) -> Optional[str]:
        """Detect ATS type from URL."""
        return self._detect_platform(url)


# Convenience function for quick job search
async def scrape_jobs_with_jobspy(
    queries: List[str],
    locations: List[str],
    total_target: int = 1000,
    sites: List[str] = None
) -> List[JobPosting]:
    """
    Quick function to scrape jobs using jobspy.
    
    Args:
        queries: List of job titles
        locations: List of locations
        total_target: Total jobs needed
        sites: Sites to search (default: indeed, linkedin, zip_recruiter)
        
    Returns:
        List of JobPosting objects
    """
    scraper = JobSpyScraper(sites=sites)
    
    if not scraper.available:
        logger.error("jobspy not available")
        return []
    
    return await scraper.search_in_batches(
        queries=queries,
        locations=locations,
        total_target=total_target
    )
