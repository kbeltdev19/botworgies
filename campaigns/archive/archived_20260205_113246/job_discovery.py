#!/usr/bin/env python3
"""
Job Discovery Pipeline - Optimized for external/direct job URLs.

This module discovers jobs from multiple sources and extracts
direct ATS URLs (Greenhouse, Lever, Workday) from job listings.

Sources:
- JobSpy (Indeed, ZipRecruiter, Google)
- LinkedIn (for external redirect extraction only)
- Direct ATS company lists
"""

import asyncio
import json
import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredJob:
    """A discovered job with source tracking."""
    id: str
    title: str
    company: str
    location: str
    url: str  # Original URL (Indeed, LinkedIn, etc.)
    apply_url: Optional[str] = None  # Direct ATS URL if extracted
    source: str = "unknown"  # indeed, linkedin, ziprecruiter, etc.
    platform: str = "unknown"  # indeed, greenhouse, lever, workday
    description: str = ""
    posted_date: Optional[datetime] = None
    employment_type: Optional[str] = None
    remote: bool = False
    salary: Optional[str] = None
    easy_apply: bool = False
    discovered_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'url': self.url,
            'apply_url': self.apply_url,
            'source': self.source,
            'platform': self.platform,
            'description': self.description[:500] if self.description else "",
            'posted_date': self.posted_date.isoformat() if self.posted_date else None,
            'employment_type': self.employment_type,
            'remote': self.remote,
            'salary': self.salary,
            'easy_apply': self.easy_apply,
            'discovered_at': self.discovered_at.isoformat(),
        }


class JobDiscoveryPipeline:
    """
    Pipeline for discovering jobs from multiple sources.
    Optimized for finding external/direct apply URLs.
    """
    
    # ATS URL patterns
    ATS_PATTERNS = {
        'greenhouse': ['boards.greenhouse.io', 'greenhouse.io', 'grnh.se'],
        'lever': ['jobs.lever.co', 'lever.co'],
        'workday': ['myworkdayjobs.com', 'workday.com', r'wd\d+\.myworkdayjobs\.com'],
        'ashby': ['jobs.ashbyhq.com'],
        'breezy': ['breezy.hr'],
        'smartrecruiters': ['smartrecruiters.com'],
        'applytojob': ['applytojob.com'],
        'workable': ['apply.workable.com', 'workable.com'],
        'jobvite': ['app.jobvite.com', 'jobvite.com'],
        'paycor': ['recruitingbypaycor.com', 'paycor.com'],
        'adp': ['recruiting.adp.com'],
        'dayforce': ['dayforcehcm.com'],
        'taleo': ['tbe.taleo.net', 'taleo.net'],
        'icims': ['icims.com'],
        'recruitee': ['recruitee.com'],
    }
    
    def __init__(self, 
                 output_dir: str = "campaigns/output",
                 max_workers: int = 4,
                 enable_external_extraction: bool = True):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers
        self.enable_external_extraction = enable_external_extraction
        
        self.discovered_jobs: List[DiscoveredJob] = []
        self.seen_urls: Set[str] = set()
        self.stats = {
            'from_jobspy': 0,
            'from_direct_ats': 0,
            'external_urls_extracted': 0,
            'duplicates_skipped': 0,
        }
        
    def _generate_id(self, url: str) -> str:
        """Generate unique ID from URL."""
        return hashlib.md5(url.encode()).hexdigest()[:12]
    
    def _is_duplicate(self, url: str) -> bool:
        """Check if URL already seen."""
        normalized = url.lower().strip().rstrip('/')
        if normalized in self.seen_urls:
            return True
        self.seen_urls.add(normalized)
        return False
    
    def _detect_platform(self, url: str) -> str:
        """Detect ATS platform from URL."""
        import re
        url_lower = url.lower()
        for platform, patterns in self.ATS_PATTERNS.items():
            for pattern in patterns:
                # Use regex for patterns with special chars, simple contains otherwise
                if any(c in pattern for c in ['\\', '*', '+', '?', '^', '$']):
                    if re.search(pattern, url_lower):
                        return platform
                elif pattern in url_lower:
                    return platform
        if 'indeed' in url_lower:
            return 'indeed'
        elif 'linkedin' in url_lower:
            return 'linkedin'
        elif 'ziprecruiter' in url_lower:
            return 'ziprecruiter'
        return 'unknown'
    
    async def discover_from_jobspy(self,
                                   queries: List[str],
                                   locations: List[str] = None,
                                   sites: List[str] = None,
                                   max_results_per_query: int = 50,
                                   posted_within_days: int = 7) -> List[DiscoveredJob]:
        """
        Discover jobs using JobSpy library.
        
        Args:
            queries: Job search terms
            locations: Locations to search
            sites: Job sites (indeed, zip_recruiter, google)
            max_results_per_query: Max results per query
            posted_within_days: Only jobs posted within N days
        """
        if locations is None:
            locations = ["United States", "Remote"]
        if sites is None:
            sites = ["indeed", "zip_recruiter"]  # Exclude LinkedIn (blocks)
        
        logger.info(f"[Discovery] Starting JobSpy search...")
        logger.info(f"  Queries: {queries}")
        logger.info(f"  Locations: {locations}")
        logger.info(f"  Sites: {sites}")
        
        jobs = []
        
        try:
            from jobspy import scrape_jobs
            
            # Use ThreadPool for parallel searches
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                
                for query in queries:
                    for location in locations:
                        future = executor.submit(
                            self._search_jobspy_sync,
                            scrape_jobs,
                            sites,
                            query,
                            location,
                            max_results_per_query,
                            posted_within_days
                        )
                        futures.append((future, query, location))
                
                for future, query, location in futures:
                    try:
                        result = future.result(timeout=60)
                        if result is not None and hasattr(result, 'empty') and not result.empty:
                            df_jobs = self._convert_jobspy_results(result, sites[0])
                            jobs.extend(df_jobs)
                            logger.info(f"[JobSpy] {query} in {location}: {len(df_jobs)} jobs")
                    except Exception as e:
                        logger.warning(f"[JobSpy] Search failed for {query}/{location}: {e}")
            
            # Deduplicate
            unique_jobs = []
            for job in jobs:
                if not self._is_duplicate(job.url):
                    unique_jobs.append(job)
                else:
                    self.stats['duplicates_skipped'] += 1
            
            self.discovered_jobs.extend(unique_jobs)
            self.stats['from_jobspy'] += len(unique_jobs)
            
            logger.info(f"[Discovery] JobSpy complete: {len(unique_jobs)} unique jobs")
            return unique_jobs
            
        except ImportError:
            logger.error("[Discovery] jobspy not installed")
            return []
        except Exception as e:
            logger.error(f"[Discovery] JobSpy discovery failed: {e}")
            return []
    
    def _search_jobspy_sync(self, scrape_fn, sites, query, location, max_results, hours):
        """Synchronous JobSpy search for ThreadPool."""
        try:
            return scrape_fn(
                site_name=sites,
                search_term=query,
                location=location,
                results_wanted=max_results,
                hours_old=hours * 24,
            )
        except Exception as e:
            logger.debug(f"[JobSpy] Search error: {e}")
            return None
    
    def _convert_jobspy_results(self, df, default_source: str) -> List[DiscoveredJob]:
        """Convert JobSpy DataFrame to DiscoveredJob objects."""
        jobs = []
        
        if df is None or df.empty:
            return jobs
        
        import pandas as pd
        
        for _, row in df.iterrows():
            try:
                job_url = str(row.get('job_url', ''))
                if not job_url or 'http' not in job_url:
                    continue
                
                # Try to get direct apply URL from jobspy
                # job_url_direct contains the actual ATS URL (Greenhouse, Lever, etc.)
                apply_url = None
                if 'job_url_direct' in row and pd.notna(row['job_url_direct']):
                    apply_url = str(row['job_url_direct'])
                elif 'apply_url' in row and pd.notna(row['apply_url']):
                    apply_url = str(row['apply_url'])
                
                # Detect platform from direct URL first, then fallback to job_url
                platform = self._detect_platform(apply_url or job_url)
                
                # Parse date
                posted_date = None
                if 'date_posted' in row and pd.notna(row['date_posted']):
                    try:
                        posted_date = pd.to_datetime(row['date_posted'])
                    except:
                        pass
                
                job = DiscoveredJob(
                    id=self._generate_id(job_url),
                    title=str(row.get('title', '')).strip(),
                    company=str(row.get('company', '')).strip(),
                    location=str(row.get('location', '')).strip(),
                    url=job_url,
                    apply_url=apply_url,
                    source=str(row.get('site', default_source)).lower(),
                    platform=platform,
                    description=str(row.get('description', ''))[:1000],
                    posted_date=posted_date,
                    employment_type=str(row.get('job_type', '')) if pd.notna(row.get('job_type')) else None,
                    remote='remote' in str(row.get('location', '')).lower(),
                    salary=str(row.get('salary', '')) if pd.notna(row.get('salary')) else None,
                    easy_apply=row.get('easy_apply', False) if 'easy_apply' in row else False,
                )
                
                jobs.append(job)
                
            except Exception as e:
                logger.debug(f"[Discovery] Conversion error: {e}")
                continue
        
        return jobs
    
    async def extract_external_urls(self, jobs: List[DiscoveredJob]) -> List[DiscoveredJob]:
        """
        Extract external apply URLs from job listings.
        For Indeed jobs, navigate to page and find direct ATS link.
        """
        if not self.enable_external_extraction:
            return jobs
        
        logger.info(f"[Discovery] Extracting external URLs for {len(jobs)} jobs...")
        
        updated_jobs = []
        extraction_count = 0
        
        # Only process jobs without direct ATS URLs
        jobs_to_process = [j for j in jobs if not j.apply_url or j.platform == 'unknown']
        
        logger.info(f"[Discovery] {len(jobs_to_process)} jobs need external URL extraction")
        
        # Process in batches
        batch_size = 10
        for i in range(0, len(jobs_to_process), batch_size):
            batch = jobs_to_process[i:i + batch_size]
            
            tasks = [self._extract_single_url(job) for job in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for job, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.debug(f"[Discovery] Extraction failed: {result}")
                    updated_jobs.append(job)
                else:
                    if result.apply_url and result.apply_url != job.url:
                        extraction_count += 1
                    updated_jobs.append(result)
            
            # Small delay between batches
            await asyncio.sleep(1)
        
        # Add jobs that already had apply URLs
        jobs_with_apply_url = [j for j in jobs if j.apply_url and j.platform != 'unknown']
        updated_jobs.extend(jobs_with_apply_url)
        
        self.stats['external_urls_extracted'] += extraction_count
        logger.info(f"[Discovery] External URL extraction complete: {extraction_count} URLs found")
        
        return updated_jobs
    
    async def _extract_single_url(self, job: DiscoveredJob) -> DiscoveredJob:
        """Extract external URL from a single job listing."""
        from adapters.handlers.browser_manager import BrowserManager
        
        if job.source != 'indeed':
            return job
        
        browser = None
        try:
            browser = BrowserManager(headless=True)
            context, page = await browser.create_context()
            
            # Navigate to Indeed job page
            await page.goto(job.url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)
            
            # Look for apply button/external link
            apply_selectors = [
                'a[href*="greenhouse.io"]',
                'a[href*="lever.co"]',
                'a[href*="myworkdayjobs.com"]',
                'a[href*="ashbyhq.com"]',
                'a[href*="applytojob.com"]',
                'button:has-text("Apply")',
                'a:has-text("Apply")',
            ]
            
            for selector in apply_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        href = await element.get_attribute('href')
                        if href:
                            # Resolve relative URLs
                            if href.startswith('/'):
                                href = f"https://www.indeed.com{href}"
                            
                            # Update job with apply URL
                            job.apply_url = href
                            job.platform = self._detect_platform(href)
                            break
                except:
                    continue
            
            await browser.close()
            return job
            
        except Exception as e:
            logger.debug(f"[Discovery] URL extraction failed for {job.url}: {e}")
            if browser:
                await browser.close()
            return job
    
    async def discover_direct_ats_jobs(self, 
                                       company_lists: Dict[str, List[str]],
                                       keywords: List[str]) -> List[DiscoveredJob]:
        """
        Discover jobs from direct ATS company lists.
        
        Args:
            company_lists: Dict of platform -> list of company names/domains
            keywords: Job keywords to search for
        """
        logger.info(f"[Discovery] Searching direct ATS companies...")
        
        jobs = []
        
        for platform, companies in company_lists.items():
            logger.info(f"[Discovery] {platform}: {len(companies)} companies")
            
            if platform == 'greenhouse':
                platform_jobs = await self._search_greenhouse(companies, keywords)
            elif platform == 'lever':
                platform_jobs = await self._search_lever(companies, keywords)
            elif platform == 'workday':
                platform_jobs = await self._search_workday(companies, keywords)
            else:
                continue
            
            # Deduplicate
            for job in platform_jobs:
                if not self._is_duplicate(job.url):
                    jobs.append(job)
                else:
                    self.stats['duplicates_skipped'] += 1
            
            logger.info(f"[Discovery] {platform}: {len(platform_jobs)} jobs")
        
        self.discovered_jobs.extend(jobs)
        self.stats['from_direct_ats'] += len(jobs)
        
        return jobs
    
    async def _search_greenhouse(self, companies: List[str], keywords: List[str]) -> List[DiscoveredJob]:
        """Search Greenhouse companies."""
        from adapters.job_boards.greenhouse_scraper import GreenhouseScraper
        
        jobs = []
        scraper = GreenhouseScraper()
        
        try:
            await scraper.initialize()
            
            for company in companies[:50]:  # Limit for performance
                try:
                    company_jobs = await scraper.get_company_jobs(company)
                    for job_data in company_jobs:
                        # Filter by keywords
                        title_lower = job_data.get('title', '').lower()
                        if any(kw.lower() in title_lower for kw in keywords):
                            job = DiscoveredJob(
                                id=self._generate_id(job_data['url']),
                                title=job_data['title'],
                                company=job_data['company'],
                                location=job_data.get('location', ''),
                                url=job_data['url'],
                                apply_url=job_data['url'],
                                source='greenhouse',
                                platform='greenhouse',
                                description=job_data.get('description', ''),
                            )
                            jobs.append(job)
                except Exception as e:
                    logger.debug(f"[Greenhouse] {company} failed: {e}")
                    continue
            
            await scraper.close()
        except Exception as e:
            logger.error(f"[Greenhouse] Search failed: {e}")
        
        return jobs
    
    async def _search_lever(self, companies: List[str], keywords: List[str]) -> List[DiscoveredJob]:
        """Search Lever companies."""
        from adapters.job_boards.lever_scraper import LeverScraper
        
        jobs = []
        scraper = LeverScraper()
        
        try:
            await scraper.initialize()
            
            for company in companies[:50]:
                try:
                    company_jobs = await scraper.get_company_jobs(company)
                    for job_data in company_jobs:
                        title_lower = job_data.get('title', '').lower()
                        if any(kw.lower() in title_lower for kw in keywords):
                            job = DiscoveredJob(
                                id=self._generate_id(job_data['url']),
                                title=job_data['title'],
                                company=job_data['company'],
                                location=job_data.get('location', ''),
                                url=job_data['url'],
                                apply_url=job_data['url'],
                                source='lever',
                                platform='lever',
                                description=job_data.get('description', ''),
                            )
                            jobs.append(job)
                except Exception as e:
                    logger.debug(f"[Lever] {company} failed: {e}")
                    continue
            
            await scraper.close()
        except Exception as e:
            logger.error(f"[Lever] Search failed: {e}")
        
        return jobs
    
    async def _search_workday(self, companies: List[str], keywords: List[str]) -> List[DiscoveredJob]:
        """Search Workday companies."""
        # Workday requires browser automation per company
        # For now, return empty - can be enhanced later
        logger.info("[Workday] Skipping (requires individual browser sessions)")
        return []
    
    def save_results(self, filename: str = None):
        """Save discovered jobs to JSON."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"discovered_jobs_{timestamp}.json"
        
        filepath = self.output_dir / filename
        
        data = {
            'metadata': {
                'discovered_at': datetime.now().isoformat(),
                'total_jobs': len(self.discovered_jobs),
                'stats': self.stats,
            },
            'jobs': [job.to_dict() for job in self.discovered_jobs]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"[Discovery] Saved {len(self.discovered_jobs)} jobs to {filepath}")
        return filepath
    
    def get_jobs_by_platform(self) -> Dict[str, List[DiscoveredJob]]:
        """Group jobs by platform."""
        by_platform = {}
        for job in self.discovered_jobs:
            platform = job.platform
            if platform not in by_platform:
                by_platform[platform] = []
            by_platform[platform].append(job)
        return by_platform
    
    def get_direct_apply_jobs(self) -> List[DiscoveredJob]:
        """Get jobs with direct ATS apply URLs."""
        return [j for j in self.discovered_jobs 
                if j.apply_url and j.platform in ['greenhouse', 'lever', 'workday', 'ashby']]


async def main():
    """Test the job discovery pipeline."""
    logging.basicConfig(level=logging.INFO)
    
    pipeline = JobDiscoveryPipeline()
    
    # Test JobSpy
    jobs = await pipeline.discover_from_jobspy(
        queries=["Software Engineer", "DevOps", "IT Manager"],
        locations=["Remote", "United States"],
        sites=["indeed", "zip_recruiter"],
        max_results_per_query=20,
    )
    
    print(f"\nDiscovered {len(jobs)} jobs from JobSpy")
    
    # Show breakdown
    by_platform = pipeline.get_jobs_by_platform()
    print("\nBy platform:")
    for platform, platform_jobs in by_platform.items():
        print(f"  {platform}: {len(platform_jobs)}")
    
    # Save results
    pipeline.save_results()


if __name__ == "__main__":
    asyncio.run(main())
