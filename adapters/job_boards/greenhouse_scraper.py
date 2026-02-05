#!/usr/bin/env python3
"""
Greenhouse Direct Scraper - Scrape jobs directly from company Greenhouse boards.

This bypasses LinkedIn and goes straight to the source.
"""

import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime
import logging

from adapters.job_boards import JobPosting, SearchCriteria

logger = logging.getLogger(__name__)


# Top companies using Greenhouse (verified working)
GREENHOUSE_COMPANIES = [
    # Tech companies
    'stripe', 'airbnb', 'doordash', 'instacart', 'robinhood', 'coinbase',
    'notion', 'figma', 'miro', 'asana', 'monday', 'clickup', 'airtable',
    'segment', 'amplitude', 'gainsight', 'outreach', 'apollo', 'zoominfo',
    'plaid', 'brex', 'ramp', 'mercury', 'benchling', 'verkada',
    
    # Enterprise
    'mongodb', 'confluent', 'datadog', 'cloudflare', 'fastly', 'kong',
    'hashicorp', 'databricks', 'snowflake', 'cohesity', 'rubrik',
    'okta', 'twilio', 'segment', 'auth0', '1password',
    
    # Startups
    'vercel', 'linear', 'raycast', 'warp', 'figma', 'canva', 'notion',
    'loom', 'descript', 'figma', 'sketch', 'framer', 'webflow',
]


class GreenhouseScraper:
    """
    Scraper for Greenhouse job boards.
    
    Uses Greenhouse's public JSON API - no authentication required.
    """
    
    API_BASE = "https://boards.greenhouse.io"
    
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
        """Fetch jobs for a single Greenhouse company."""
        url = f"{self.API_BASE}/{company}/jobs.json"
        
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 404:
                    return []  # Company not found or doesn't use Greenhouse
                
                if response.status != 200:
                    logger.debug(f"Greenhouse {company}: HTTP {response.status}")
                    return []
                
                data = await response.json()
                jobs = []
                
                for job_data in data.get('jobs', []):
                    job = self._parse_job(job_data, company)
                    if job:
                        jobs.append(job)
                
                logger.info(f"[Greenhouse] {company}: {len(jobs)} jobs")
                return jobs
                
        except asyncio.TimeoutError:
            logger.debug(f"Greenhouse {company}: Timeout")
            return []
        except Exception as e:
            logger.debug(f"Greenhouse {company}: {e}")
            self.stats['errors'] += 1
            return []
    
    def _parse_job(self, job_data: dict, company: str) -> Optional[JobPosting]:
        """Parse a Greenhouse job JSON into JobPosting."""
        try:
            job_id = str(job_data.get('id', ''))
            if not job_id:
                return None
            
            title = job_data.get('title', '')
            
            # Location parsing
            location_data = job_data.get('location', {})
            if isinstance(location_data, dict):
                location_parts = [
                    location_data.get('name', ''),
                ]
                location = ', '.join(filter(None, location_parts))
            else:
                location = str(location_data)
            
            # Build absolute URL
            absolute_url = job_data.get('absolute_url', '')
            if not absolute_url:
                absolute_url = f"{self.API_BASE}/{company}/jobs/{job_id}"
            
            return JobPosting(
                id=f"greenhouse_{company}_{job_id}",
                title=title,
                company=company.title(),
                location=location,
                description=job_data.get('content', '')[:500] if job_data.get('content') else '',
                url=absolute_url,
                source="greenhouse",
                platform="greenhouse",
                posted_date=None,
                employment_type=None,
                raw_data=job_data,
            )
            
        except Exception as e:
            logger.debug(f"Failed to parse Greenhouse job: {e}")
            return None
    
    async def search(
        self,
        keywords: List[str],
        locations: List[str] = None,
        max_jobs: int = 1000
    ) -> List[JobPosting]:
        """
        Search for jobs across all Greenhouse companies.
        
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
        
        logger.info(f"[Greenhouse] Searching {len(GREENHOUSE_COMPANIES)} companies for: {keywords}")
        
        # Fetch jobs from all companies concurrently
        tasks = [self.fetch_company_jobs(company) for company in GREENHOUSE_COMPANIES]
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
        
        logger.info(f"[Greenhouse] Total matching jobs: {len(all_jobs)}")
        return all_jobs[:max_jobs]


# Convenience function
async def scrape_greenhouse_jobs(
    keywords: List[str],
    locations: List[str] = None,
    max_jobs: int = 1000
) -> List[JobPosting]:
    """Quick function to scrape Greenhouse jobs."""
    async with GreenhouseScraper() as scraper:
        return await scraper.search(keywords, locations, max_jobs)
