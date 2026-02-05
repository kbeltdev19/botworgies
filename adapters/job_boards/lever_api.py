"""
Lever API Scraper

Uses Lever's public JSON API - no authentication required.
Clean JSON responses with full job details.
"""

import asyncio
import re
from datetime import datetime
from typing import Dict, List, Optional
import logging

from . import BaseJobBoardScraper, JobPosting, SearchCriteria

logger = logging.getLogger(__name__)


class LeverAPIScraper(BaseJobBoardScraper):
    """
    Scraper for Lever job boards using their public API.
    
    Features:
    - No authentication required
    - Clean JSON API
    - Full job descriptions
    - Direct apply URLs
    
    API Endpoint: https://api.lever.co/v0/postings/{company}
    """
    
    API_BASE = "https://api.lever.co/v0/postings"
    
    # Popular Lever companies (verified working)
    # Reduced list for speed - top companies most likely to have relevant jobs
    DEFAULT_COMPANIES = [
        'netlify', 'sentry', 'launchdarkly', 'fivetran', 'dbt', 'front',
        'intercom', 'zendesk', 'gong', 'salesloft', 'braze', 'segment',
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
        """Lever URLs are always Lever ATS."""
        if 'jobs.lever.co' in url.lower():
            return 'lever'
        return None
        
    async def _fetch_company_jobs(self, company: str) -> List[JobPosting]:
        """Fetch jobs for a single Lever company."""
        url = f"{self.API_BASE}/{company}"
        
        try:
            import aiohttp
            data = await self.fetch_json(url, timeout=aiohttp.ClientTimeout(total=10))
            
            jobs = []
            for job_data in data:
                job = self._parse_job(job_data, company)
                if job:
                    jobs.append(job)
                    
            return jobs
            
        except Exception as e:
            logger.warning(f"Failed to fetch Lever jobs for {company}: {e}")
            return []
            
    def _parse_job(self, job_data: Dict, company: str) -> Optional[JobPosting]:
        """Parse a Lever job JSON into JobPosting."""
        try:
            job_id = job_data.get('id', '')
            if not job_id:
                return None
                
            text_data = job_data.get('text', '')
            description = job_data.get('description', '')
            
            # Lever puts title in 'text' field
            title = text_data if text_data else 'Unknown'
            
            # Categories contain additional metadata
            categories = job_data.get('categories', {})
            
            # Location
            location = categories.get('location', 'Unknown')
            if isinstance(location, list):
                location = ', '.join(location)
            elif not location:
                location = categories.get('allLocations', ['Unknown'])[0]
                
            # Remote detection
            commitment = categories.get('commitment', '')
            remote = 'remote' in location.lower() or job_data.get('workplaceType') == 'remote'
            
            # Clean description
            if description:
                description = re.sub(r'<[^>]+>', ' ', description)
                description = re.sub(r'\s+', ' ', description).strip()
                
            # Application URL
            apply_url = job_data.get('applyUrl', '') or job_data.get('hostedUrl', '')
            if not apply_url:
                apply_url = f"https://jobs.lever.co/{company}/{job_id}"
                
            # Posted date
            posted_date = None
            if 'createdAt' in job_data:
                try:
                    # Lever uses timestamp in milliseconds
                    timestamp = job_data['createdAt']
                    if timestamp > 1000000000000:  # Milliseconds
                        timestamp = timestamp / 1000
                    posted_date = datetime.fromtimestamp(timestamp)
                except:
                    pass
                    
            # Employment type from categories
            employment_type = categories.get('commitment', '')
            
            # Department/team
            department = categories.get('department', '')
            
            return JobPosting(
                id=f"lever_{company}_{job_id}",
                title=title,
                company=company.replace('-', ' ').title(),
                location=location,
                description=description[:2000],
                url=apply_url,
                source='lever',
                posted_date=posted_date,
                employment_type=employment_type if employment_type else None,
                remote=remote,
                easy_apply=True,  # Lever has direct apply
                apply_url=apply_url,
                raw_data={
                    'department': department,
                    'categories': categories,
                }
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse Lever job: {e}")
            return None
            
    async def search(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Search Lever across configured companies."""
        all_jobs = []
        
        # Search companies concurrently
        semaphore = asyncio.Semaphore(10)
        
        async def fetch_with_limit(company: str):
            async with semaphore:
                jobs = await self._fetch_company_jobs(company)
                await asyncio.sleep(0.5)
                return jobs
                
        tasks = [fetch_with_limit(company) for company in self.companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for company, result in zip(self.companies, results):
            if isinstance(result, Exception):
                logger.error(f"Lever fetch failed for {company}: {result}")
                continue
                
            # Filter by query
            query_lower = criteria.query.lower()
            for job in result:
                if query_lower in job.title.lower() or query_lower in job.description.lower():
                    if criteria.remote_only and not job.remote:
                        continue
                    all_jobs.append(job)
                    
        # Sort by date
        all_jobs.sort(key=lambda j: j.posted_date or datetime.min, reverse=True)
        
        logger.info(f"Lever API: Found {len(all_jobs)} matching jobs")
        return all_jobs[:criteria.max_results]
        
    async def search_single_company(self, company: str, criteria: SearchCriteria) -> List[JobPosting]:
        """Search jobs for a specific Lever company."""
        jobs = await self._fetch_company_jobs(company)
        
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
            query="engineer",
            remote_only=True,
            max_results=20
        )
        
        scraper = LeverAPIScraper(companies=['notion', 'figma', 'vercel'])
        
        async with scraper:
            jobs = await scraper.search(criteria)
            print(f"Found {len(jobs)} jobs from Lever")
            for job in jobs[:5]:
                print(f"\n{job.title} at {job.company}")
                print(f"  Location: {job.location}")
                print(f"  Remote: {job.remote}")
                print(f"  URL: {job.apply_url}")
                
    asyncio.run(test())
