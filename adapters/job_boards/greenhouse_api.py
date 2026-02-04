"""
Greenhouse API Scraper

Uses Greenhouse's public JSON API - no authentication required.
Returns full job descriptions and structured data.
"""

import asyncio
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin
import logging

from . import BaseJobBoardScraper, JobPosting, SearchCriteria

logger = logging.getLogger(__name__)


class GreenhouseAPIScraper(BaseJobBoardScraper):
    """
    Scraper for Greenhouse job boards using their public API.
    
    Features:
    - No authentication required
    - Full JSON responses with descriptions
    - Direct application URLs
    - Company-specific boards
    """
    
    API_BASE = "https://boards.greenhouse.io"
    
    # Popular Greenhouse companies to search
    DEFAULT_COMPANIES = [
        'stripe', 'airbnb', 'uber', 'lyft', 'slack', 'notion', 'figma',
        'gitlab', 'hashicorp', 'datadog', 'plaid', 'figma', 'vercel',
        'linear', 'raycast', 'supabase', 'retool', 'rippling', 'gusto',
        'scale', 'cruise', 'zoox', 'waymo', 'aurora', 'nuro',
    ]
    
    def __init__(self, companies: Optional[List[str]] = None, session=None):
        super().__init__(session)
        self.companies = companies or self.DEFAULT_COMPANIES
        
    def get_default_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': 'Mozilla/5.0 (compatible; JobBot/1.0)',
            'Accept': 'application/json',
        }
        
    def get_ats_type(self, url: str) -> Optional[str]:
        """Greenhouse URLs are always Greenhouse ATS."""
        if 'greenhouse.io' in url.lower():
            return 'greenhouse'
        return None
        
    async def _fetch_company_jobs(self, company: str) -> List[JobPosting]:
        """Fetch jobs for a single Greenhouse company."""
        url = f"{self.API_BASE}/{company}/jobs.json"
        
        try:
            data = await self.fetch_json(url)
            
            jobs = []
            for job_data in data.get('jobs', []):
                job = self._parse_job(job_data, company)
                if job:
                    jobs.append(job)
                    
            return jobs
            
        except Exception as e:
            logger.warning(f"Failed to fetch jobs for {company}: {e}")
            return []
            
    def _parse_job(self, job_data: Dict, company: str) -> Optional[JobPosting]:
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
                    location_data.get('city', ''),
                    location_data.get('state', ''),
                    location_data.get('country', ''),
                ]
                location = ', '.join(filter(None, location_parts))
            else:
                location = str(location_data)
                
            # Clean up location
            location = location.replace('Remote,', '').strip()
            remote = 'remote' in location.lower() or job_data.get('remote', False)
            
            # Description
            description = job_data.get('content', '') or job_data.get('description', '')
            if description:
                # Clean HTML
                description = re.sub(r'<[^>]+>', ' ', description)
                description = re.sub(r'\s+', ' ', description).strip()
                
            # Application URL
            apply_url = job_data.get('absolute_url', '')
            if not apply_url:
                apply_url = f"{self.API_BASE}/{company}/jobs/{job_id}"
                
            # Posted date
            posted_date = None
            if 'updated_at' in job_data:
                try:
                    posted_date = datetime.fromisoformat(
                        job_data['updated_at'].replace('Z', '+00:00')
                    )
                except:
                    pass
                    
            # Employment type
            employment_type = None
            if 'metadata' in job_data:
                for meta in job_data['metadata']:
                    if meta.get('name', '').lower() in ['employment type', 'type']:
                        employment_type = meta.get('value')
                        break
                        
            return JobPosting(
                id=f"gh_{company}_{job_id}",
                title=title,
                company=company.replace('-', ' ').title(),
                location=location or "Unknown",
                description=description[:2000],
                url=apply_url,
                source='greenhouse',
                posted_date=posted_date,
                employment_type=employment_type,
                remote=remote,
                easy_apply=True,  # Greenhouse has direct apply
                apply_url=apply_url,
                raw_data=job_data,
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse Greenhouse job: {e}")
            return None
            
    async def search(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Search Greenhouse across configured companies."""
        all_jobs = []
        
        # Search companies concurrently (with limit)
        semaphore = asyncio.Semaphore(10)  # Limit concurrent requests
        
        async def fetch_with_limit(company: str):
            async with semaphore:
                jobs = await self._fetch_company_jobs(company)
                await asyncio.sleep(0.5)  # Be polite
                return jobs
                
        tasks = [fetch_with_limit(company) for company in self.companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for company, result in zip(self.companies, results):
            if isinstance(result, Exception):
                logger.error(f"Greenhouse fetch failed for {company}: {result}")
                continue
                
            # Filter by query
            query_lower = criteria.query.lower()
            for job in result:
                if query_lower in job.title.lower() or query_lower in job.description.lower():
                    # Additional filters
                    if criteria.remote_only and not job.remote:
                        continue
                    all_jobs.append(job)
                    
        # Sort by date
        all_jobs.sort(key=lambda j: j.posted_date or datetime.min, reverse=True)
        
        logger.info(f"Greenhouse API: Found {len(all_jobs)} matching jobs")
        return all_jobs[:criteria.max_results]
        
    async def search_single_company(self, company: str, criteria: SearchCriteria) -> List[JobPosting]:
        """Search jobs for a specific Greenhouse company."""
        jobs = await self._fetch_company_jobs(company)
        
        # Apply filters
        filtered = []
        query_lower = criteria.query.lower()
        
        for job in jobs:
            if query_lower in job.title.lower() or query_lower in job.description.lower():
                if criteria.remote_only and not job.remote:
                    continue
                filtered.append(job)
                
        return filtered[:criteria.max_results]


# For testing
if __name__ == "__main__":
    import asyncio
    
    async def test():
        criteria = SearchCriteria(
            query="software engineer",
            remote_only=True,
            max_results=20
        )
        
        # Test with specific companies
        scraper = GreenhouseAPIScraper(companies=['stripe', 'airbnb', 'uber'])
        
        async with scraper:
            jobs = await scraper.search(criteria)
            print(f"Found {len(jobs)} jobs from Greenhouse")
            for job in jobs[:5]:
                print(f"\n{job.title} at {job.company}")
                print(f"  Location: {job.location}")
                print(f"  Remote: {job.remote}")
                print(f"  URL: {job.apply_url}")
                
    asyncio.run(test())
