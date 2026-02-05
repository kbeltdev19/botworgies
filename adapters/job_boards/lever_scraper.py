#!/usr/bin/env python3
"""
Lever Direct Scraper - Scrape jobs directly from company Lever boards.
"""

import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime
import logging

from adapters.job_boards import JobPosting, SearchCriteria

logger = logging.getLogger(__name__)


# Top companies using Lever
LEVER_COMPANIES = [
    # Tech companies
    'netlify', 'vercel', 'notion', 'linear', 'raycast', 'warp',
    'figma', 'sketch', 'framer', 'webflow', 'descript', 'loom',
    'retool', 'airplane', 'superhuman', 'calendly', 'loom',
    'sentry', 'launchdarkly', 'datadog', 'honeycomb', 'mux',
    'dbt', 'fivetran', 'hightouch', 'census', 'airbyte',
    'gong', 'chorus', 'execvision', 'salesloft', 'outreach',
    'apollo', '6sense', 'demandbase', 'terminus', 'zoominfo',
    'braze', 'iterable', 'segment', 'mparticle', 'lytics',
    'persona', 'veriff', 'sentilink', 'socure', 'castle',
    'stripe', 'plaid', 'brex', 'ramp', 'mercury', 'lithic',
    'checkr', 'gusto', 'zenefits', 'rippling', 'deel',
]


class LeverScraper:
    """
    Scraper for Lever job boards.
    
    Uses Lever's public JSON API - no authentication required.
    """
    
    API_BASE = "https://api.lever.co/v0/postings"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.stats = {
            'companies_checked': 0,
            'jobs_found': 0,
            'errors': 0,
        }
    
    async def __aenter__(self):
        import ssl
        # Create SSL context that allows us to connect
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        self.session = aiohttp.ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            connector=aiohttp.TCPConnector(ssl=ssl_context)
        )
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def fetch_company_jobs(self, company: str) -> List[JobPosting]:
        """Fetch jobs for a single Lever company."""
        url = f"{self.API_BASE}/{company}?mode=json"
        
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 404:
                    return []
                
                if response.status != 200:
                    logger.debug(f"Lever {company}: HTTP {response.status}")
                    return []
                
                data = await response.json()
                jobs = []
                
                # Lever returns a list directly
                job_list = data if isinstance(data, list) else data.get('postings', [])
                
                for job_data in job_list:
                    job = self._parse_job(job_data, company)
                    if job:
                        jobs.append(job)
                
                if jobs:
                    logger.info(f"[Lever] {company}: {len(jobs)} jobs")
                return jobs
                
        except asyncio.TimeoutError:
            logger.debug(f"Lever {company}: Timeout")
            return []
        except Exception as e:
            logger.debug(f"Lever {company}: {e}")
            self.stats['errors'] += 1
            return []
    
    def _parse_job(self, job_data: dict, company: str) -> Optional[JobPosting]:
        """Parse a Lever job JSON into JobPosting."""
        try:
            job_id = str(job_data.get('id', ''))
            if not job_id:
                return None
            
            title = job_data.get('text', '')
            
            # Location
            categories = job_data.get('categories', {})
            location = categories.get('location', '') if isinstance(categories, dict) else ''
            
            # URL
            apply_url = job_data.get('applyUrl', '') or job_data.get('hostedUrl', '')
            if not apply_url:
                apply_url = f"https://jobs.lever.co/{company}/{job_id}"
            
            return JobPosting(
                id=f"lever_{company}_{job_id}",
                title=title,
                company=company.title(),
                location=location,
                description=job_data.get('description', '')[:500] if job_data.get('description') else '',
                url=apply_url,
                source="lever",
                platform="lever",
                posted_date=None,
                employment_type=categories.get('commitment', '') if isinstance(categories, dict) else None,
                raw_data=job_data,
            )
            
        except Exception as e:
            logger.debug(f"Failed to parse Lever job: {e}")
            return None
    
    async def search(
        self,
        keywords: List[str],
        locations: List[str] = None,
        max_jobs: int = 500
    ) -> List[JobPosting]:
        """
        Search for jobs across all Lever companies.
        
        Args:
            keywords: List of job title keywords to filter by
            locations: List of location keywords to filter by
            max_jobs: Maximum total jobs to return
            
        Returns:
            List of matching JobPosting objects
        """
        all_jobs = []
        seen_urls = set()
        
        # Convert keywords to lowercase for matching
        keywords_lower = [k.lower() for k in keywords]
        locations_lower = [l.lower() for l in (locations or [])]
        
        logger.info(f"[Lever] Searching {len(LEVER_COMPANIES)} companies for: {keywords}")
        
        # Fetch jobs from all companies concurrently (in batches to avoid rate limiting)
        batch_size = 10
        for i in range(0, len(LEVER_COMPANIES), batch_size):
            batch = LEVER_COMPANIES[i:i+batch_size]
            tasks = [self.fetch_company_jobs(company) for company in batch]
            results = await asyncio.gather(*tasks)
            
            for jobs in results:
                for job in jobs:
                    # Deduplicate
                    if job.url in seen_urls:
                        continue
                    seen_urls.add(job.url)
                    
                    # Check if matches keywords
                    title_lower = job.title.lower()
                    if not any(kw in title_lower for kw in keywords_lower):
                        continue
                    
                    # Check location if specified
                    if locations_lower:
                        location_lower = job.location.lower()
                        if not any(loc in location_lower for loc in locations_lower):
                            continue
                    
                    all_jobs.append(job)
                    
                    if len(all_jobs) >= max_jobs:
                        break
                
                if len(all_jobs) >= max_jobs:
                    break
            
            # Small delay between batches
            await asyncio.sleep(0.5)
        
        logger.info(f"[Lever] Total matching jobs: {len(all_jobs)}")
        return all_jobs[:max_jobs]


# Convenience function
async def scrape_lever_jobs(
    keywords: List[str],
    locations: List[str] = None,
    max_jobs: int = 500
) -> List[JobPosting]:
    """Quick function to scrape Lever jobs."""
    async with LeverScraper() as scraper:
        return await scraper.search(keywords, locations, max_jobs)
