"""
Lever Adapter - Tier 1 (API-Based)
Public JSON API, no browser needed.
"""

import aiohttp
import asyncio
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


# Popular companies using Lever
DEFAULT_LEVER_COMPANIES = [
    "netflix", "twitch", "lyft", "spotify", "cloudflare",
    "databricks", "dbt-labs", "hashicorp", "pulumi", "temporal",
    "cockroachlabs", "materialize", "singlestore", "neon", "supabase",
    "railway", "render", "fly", "modal", "replicate",
]


class LeverAdapter(JobPlatformAdapter):
    """
    Lever job board adapter.
    Uses public JSON API - no browser needed.
    """
    
    platform = PlatformType.LEVER
    tier = "api"
    
    def __init__(self, browser_manager=None, companies: List[str] = None):
        super().__init__(browser_manager)
        self.companies = companies or DEFAULT_LEVER_COMPANIES
        self._session = None
    
    async def _get_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"}
            )
        return self._session
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search Lever job boards across multiple companies."""
        session = await self._get_session()
        all_jobs = []
        
        for company in self.companies:
            try:
                url = f"https://api.lever.co/v0/postings/{company}?mode=json"
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        continue
                    
                    jobs = await resp.json()
                    
                    for job in jobs:
                        title = job.get("text", "").lower()
                        location = job.get("categories", {}).get("location", "").lower()
                        
                        # Filter by role keywords
                        if not any(kw.lower() in title for kw in criteria.roles):
                            continue
                        
                        # Filter by location if specified
                        if criteria.locations:
                            if not any(loc.lower() in location or "remote" in location 
                                      for loc in criteria.locations):
                                continue
                        
                        all_jobs.append(JobPosting(
                            id=f"lever_{job['id']}",
                            platform=self.platform,
                            title=job.get("text", ""),
                            company=company.replace("-", " ").title(),
                            location=job.get("categories", {}).get("location", ""),
                            url=job.get("hostedUrl", job.get("applyUrl", "")),
                            description=job.get("descriptionPlain", ""),
                            easy_apply=True,
                            remote="remote" in location
                        ))
                
                await asyncio.sleep(0.2)
                
            except Exception as e:
                print(f"[Lever] Error fetching {company}: {e}")
                continue
        
        print(f"[Lever] Found {len(all_jobs)} jobs across {len(self.companies)} companies")
        return all_jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details from Lever."""
        session = await self._get_session()
        
        # Extract job ID from URL
        # Format: https://jobs.lever.co/{company}/{id}
        parts = job_url.rstrip("/").split("/")
        job_id = parts[-1]
        company = parts[-2] if len(parts) >= 2 else "unknown"
        
        url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
        
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Job not found: {job_url}")
            
            data = await resp.json()
            
            return JobPosting(
                id=f"lever_{job_id}",
                platform=self.platform,
                title=data.get("text", ""),
                company=company.replace("-", " ").title(),
                location=data.get("categories", {}).get("location", ""),
                url=data.get("hostedUrl", job_url),
                description=data.get("descriptionPlain", ""),
                easy_apply=True,
                remote="remote" in data.get("categories", {}).get("location", "").lower()
            )
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """Apply to Lever job."""
        return ApplicationResult(
            status=ApplicationStatus.EXTERNAL_APPLICATION,
            message=f"Apply at: {job.url}",
            external_url=job.url
        )


async def test_lever():
    """Test Lever adapter."""
    from .base import SearchConfig
    
    adapter = LeverAdapter()
    
    criteria = SearchConfig(
        roles=["software engineer", "backend", "platform"],
        locations=["Remote"],
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
    asyncio.run(test_lever())
