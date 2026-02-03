"""
SmartRecruiters Adapter - Tier 1 (API-Based with OAuth)
Public API available, requires API key for full access.
Can also scrape public job pages without auth.
"""

import aiohttp
import asyncio
import os
from typing import List, Optional
from datetime import datetime
from urllib.parse import quote

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


# Popular companies using SmartRecruiters
DEFAULT_SR_COMPANIES = [
    "visa",
    "birchbox",
    "equinox",
    "loreal",
    "mckesson",
    "colgate",
    "skechers",
    "hootsuite",
    "meredith",
    "just-eat",
]


class SmartRecruitersAdapter(JobPlatformAdapter):
    """
    SmartRecruiters job board adapter.
    Uses public API or job page scraping.
    """
    
    platform = PlatformType.SMARTRECRUITERS
    tier = "api"
    
    # SmartRecruiters API
    API_BASE = "https://api.smartrecruiters.com/v1"
    
    def __init__(self, browser_manager=None, companies: List[str] = None, api_key: str = None):
        super().__init__(browser_manager)
        self.companies = companies or DEFAULT_SR_COMPANIES
        self.api_key = api_key or os.environ.get("SMARTRECRUITERS_API_KEY")
        self._session = None
    
    async def _get_session(self):
        if not self._session:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"}
            if self.api_key:
                headers["X-SmartToken"] = self.api_key
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search SmartRecruiters job boards across multiple companies."""
        session = await self._get_session()
        all_jobs = []
        
        query_lower = " ".join(criteria.roles).lower()
        location_filter = criteria.locations[0] if criteria.locations else None
        
        for company in self.companies:
            try:
                # Try API first if key available
                if self.api_key:
                    jobs = await self._search_via_api(session, company, query_lower, location_filter)
                else:
                    # Fall back to public job page scraping
                    jobs = await self._search_via_scrape(session, company, query_lower, location_filter)
                
                all_jobs.extend(jobs)
                await asyncio.sleep(0.3)
                
            except Exception as e:
                print(f"[SmartRecruiters] Error fetching {company}: {e}")
                continue
        
        print(f"[SmartRecruiters] Found {len(all_jobs)} jobs across {len(self.companies)} companies")
        return all_jobs
    
    async def _search_via_api(
        self, 
        session: aiohttp.ClientSession, 
        company: str, 
        query: str,
        location_filter: Optional[str]
    ) -> List[JobPosting]:
        """Search using SmartRecruiters API."""
        jobs = []
        
        url = f"{self.API_BASE}/companies/{company}/postings"
        params = {"q": query} if query else {}
        
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            
            data = await resp.json()
            
            for posting in data.get("content", []):
                title = posting.get("name", "").lower()
                
                # Additional keyword filter
                if query and query not in title:
                    continue
                
                # Location filtering
                locations = posting.get("location", {})
                location_parts = [
                    locations.get("city", ""),
                    locations.get("region", ""),
                    locations.get("country", "")
                ]
                location = ", ".join(filter(None, location_parts))
                
                if location_filter and location_filter.lower() not in location.lower():
                    if "remote" not in location.lower():
                        continue
                
                job_id = posting.get("id", "")
                company_name = posting.get("company", {}).get("name", company)
                
                jobs.append(JobPosting(
                    id=f"sr_{job_id}",
                    platform=self.platform,
                    title=posting.get("name", ""),
                    company=company_name,
                    location=location or "Remote",
                    url=f"https://jobs.smartrecruiters.com/{company}/{job_id}",
                    description=posting.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", ""),
                    easy_apply=True,
                    remote="remote" in location.lower() or posting.get("location", {}).get("remote", False),
                    job_type=posting.get("typeOfEmployment", {}).get("label", "full-time").lower()
                ))
        
        return jobs
    
    async def _search_via_scrape(
        self, 
        session: aiohttp.ClientSession, 
        company: str, 
        query: str,
        location_filter: Optional[str]
    ) -> List[JobPosting]:
        """Search by scraping public job pages."""
        jobs = []
        
        # SmartRecruiters public job board
        url = f"https://jobs.smartrecruiters.com/{company}"
        
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return []
            
            html = await resp.text()
            
            # Parse job listings from HTML
            # Look for JSON-LD or embedded data
            import re
            
            # Try to find JSON-LD job postings
            jsonld_pattern = re.compile(
                r'<script type="application/ld\+json">(.*?)</script>',
                re.DOTALL
            )
            
            for match in jsonld_pattern.finditer(html):
                try:
                    data = json.loads(match.group(1))
                    if data.get("@type") == "JobPosting":
                        title = data.get("title", "").lower()
                        
                        if query and query not in title:
                            continue
                        
                        location = data.get("jobLocation", {}).get("address", {}).get("addressLocality", "")
                        
                        if location_filter and location_filter.lower() not in location.lower():
                            continue
                        
                        jobs.append(JobPosting(
                            id=f"sr_{hash(data.get('url', ''))}",
                            platform=self.platform,
                            title=data.get("title", ""),
                            company=data.get("hiringOrganization", {}).get("name", company),
                            location=location,
                            url=data.get("url", ""),
                            description=data.get("description", ""),
                            easy_apply=True,
                            remote="remote" in location.lower() or data.get("jobLocationType") == "TELECOMMUTE"
                        ))
                except Exception:
                    continue
        
        return jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details from SmartRecruiters."""
        session = await self._get_session()
        
        # Try to extract job ID and company from URL
        # Format: https://jobs.smartrecruiters.com/{company}/{job_id}
        parts = job_url.rstrip("/").split("/")
        job_id = parts[-1]
        company = parts[-2] if len(parts) >= 2 else "unknown"
        
        # Try API first
        if self.api_key:
            api_url = f"{self.API_BASE}/companies/{company}/postings/{job_id}"
            
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    locations = data.get("location", {})
                    location_parts = [
                        locations.get("city", ""),
                        locations.get("region", ""),
                        locations.get("country", "")
                    ]
                    location = ", ".join(filter(None, location_parts))
                    
                    return JobPosting(
                        id=f"sr_{job_id}",
                        platform=self.platform,
                        title=data.get("name", ""),
                        company=data.get("company", {}).get("name", company),
                        location=location or "Remote",
                        url=job_url,
                        description=data.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", ""),
                        easy_apply=True,
                        remote="remote" in location.lower()
                    )
        
        # Fall back to scraping
        async with session.get(job_url) as resp:
            if resp.status != 200:
                raise Exception(f"Job not found: {job_url}")
            
            html = await resp.text()
            
            # Extract from JSON-LD
            import re
            jsonld_pattern = re.compile(
                r'<script type="application/ld\+json">(.*?)</script>',
                re.DOTALL
            )
            
            for match in jsonld_pattern.finditer(html):
                try:
                    data = json.loads(match.group(1))
                    if data.get("@type") == "JobPosting":
                        location = data.get("jobLocation", {}).get("address", {}).get("addressLocality", "")
                        
                        return JobPosting(
                            id=f"sr_{job_id}",
                            platform=self.platform,
                            title=data.get("title", ""),
                            company=data.get("hiringOrganization", {}).get("name", company),
                            location=location,
                            url=job_url,
                            description=data.get("description", ""),
                            easy_apply=True,
                            remote="remote" in location.lower()
                        )
                except Exception:
                    continue
            
            raise Exception(f"Could not parse job details: {job_url}")
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """Apply to SmartRecruiters job."""
        return ApplicationResult(
            status=ApplicationStatus.EXTERNAL_APPLICATION,
            message=f"Apply at: {job.url}",
            external_url=job.url
        )


async def test_smartrecruiters():
    """Test SmartRecruiters adapter."""
    from .base import SearchConfig
    
    adapter = SmartRecruitersAdapter()
    
    criteria = SearchConfig(
        roles=["software", "engineer", "developer"],
        locations=["Remote", "United States"],
        posted_within_days=30
    )
    
    try:
        jobs = await adapter.search_jobs(criteria)
        print(f"\nFound {len(jobs)} jobs:")
        for job in jobs[:10]:
            print(f"  - {job.title} at {job.company} ({job.location})")
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(test_smartrecruiters())
