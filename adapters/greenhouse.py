"""
Greenhouse Adapter - Tier 1 (API-Based)
Direct JSON endpoints, no browser needed.
"""

import aiohttp
import asyncio
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


# Import dynamic company discovery
try:
    from .company_discovery import CompanyDiscovery
    DISCOVERY_AVAILABLE = True
except ImportError:
    DISCOVERY_AVAILABLE = False

# Fallback static list
DEFAULT_GREENHOUSE_COMPANIES = [
    "stripe", "airbnb", "netflix", "coinbase", "figma",
    "notion", "airtable", "plaid", "brex", "ramp",
    "gusto", "lattice", "retool", "vercel", "linear",
    "mercury", "rippling", "anduril", "scale", "anthropic",
    # Extended list
    "doordash", "instacart", "pinterest", "twitch", "lyft",
    "dropbox", "cloudflare", "datadog", "mongodb", "elastic",
    "confluent", "hashicorp", "snowflake", "databricks", "palantir",
    "webflow", "loom", "miro", "zapier", "deel",
    "remote", "oyster", "papaya", "velocity", "maven",
    "replit", "railway", "render", "fly", "supabase",
    "planetscale", "neon", "turso", "upstash", "raycast",
    "perplexity", "cursor", "cal", "dub", "resend",
    "anthropic", "openai", "cohere", "huggingface", "replicate",
    "modal", "anyscale", "labelbox", "together", "mistral",
]


class GreenhouseAdapter(JobPlatformAdapter):
    """
    Greenhouse job board adapter.
    Uses public JSON API - no browser needed, no anti-bot issues.
    """
    
    platform = PlatformType.GREENHOUSE
    tier = "api"  # Easy tier
    
    def __init__(
        self,
        browser_manager=None,
        companies: List[str] = None,
        industries: List[str] = None,
        sizes: List[str] = None,
        max_companies: int = 50,
        session_cookie: str = None
    ):
        super().__init__(browser_manager)
        
        # Use dynamic discovery if available
        if companies:
            self.companies = companies
        elif DISCOVERY_AVAILABLE:
            discovery = CompanyDiscovery()
            self.companies = discovery.get_companies(
                "greenhouse",
                industries=industries,
                sizes=sizes,
                limit=max_companies
            )
        else:
            self.companies = DEFAULT_GREENHOUSE_COMPANIES[:max_companies]
        
        self._session = None
        print(f"[Greenhouse] Initialized with {len(self.companies)} companies")
    
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
        """Search Greenhouse job boards across multiple companies."""
        session = await self._get_session()
        all_jobs = []
        
        query_lower = " ".join(criteria.roles).lower()
        location_lower = " ".join(criteria.locations).lower() if criteria.locations else ""
        
        for company in self.companies:
            try:
                url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        continue
                    
                    data = await resp.json()
                    jobs = data.get("jobs", [])
                    
                    for job in jobs:
                        title = job.get("title", "").lower()
                        location = job.get("location", {}).get("name", "").lower()
                        
                        # Filter by role keywords
                        if not any(kw.lower() in title for kw in criteria.roles):
                            continue
                        
                        # Filter by location if specified
                        if criteria.locations and location_lower:
                            if not any(loc.lower() in location or "remote" in location 
                                      for loc in criteria.locations):
                                continue
                        
                        all_jobs.append(JobPosting(
                            id=f"gh_{company}_{job['id']}",
                            platform=self.platform,
                            title=job.get("title", ""),
                            company=company.replace("-", " ").title(),
                            location=job.get("location", {}).get("name", ""),
                            url=job.get("absolute_url", f"https://boards.greenhouse.io/{company}/jobs/{job['id']}"),
                            description=job.get("content", ""),
                            easy_apply=True,  # Greenhouse has easy apply
                            remote="remote" in location
                        ))
                
                # Small delay between companies
                await asyncio.sleep(0.2)
                
            except Exception as e:
                print(f"[Greenhouse] Error fetching {company}: {e}")
                continue
        
        print(f"[Greenhouse] Found {len(all_jobs)} jobs across {len(self.companies)} companies")
        return all_jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details from Greenhouse."""
        session = await self._get_session()
        
        # Extract company and job ID from URL
        # Format: https://boards.greenhouse.io/{company}/jobs/{id}
        parts = job_url.rstrip("/").split("/")
        job_id = parts[-1]
        company = parts[-3] if len(parts) >= 3 else "unknown"
        
        url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}"
        
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Job not found: {job_url}")
            
            data = await resp.json()
            
            return JobPosting(
                id=f"gh_{company}_{job_id}",
                platform=self.platform,
                title=data.get("title", ""),
                company=company.replace("-", " ").title(),
                location=data.get("location", {}).get("name", ""),
                url=data.get("absolute_url", job_url),
                description=data.get("content", ""),
                easy_apply=True,
                remote="remote" in data.get("location", {}).get("name", "").lower()
            )
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        Apply to Greenhouse job.
        Note: Greenhouse requires form submission, can use API or browser.
        """
        # For now, return external application link
        # Full implementation would POST to the application form
        return ApplicationResult(
            status=ApplicationStatus.EXTERNAL_APPLICATION,
            message=f"Apply at: {job.url}",
            external_url=job.url
        )


async def test_greenhouse():
    """Test Greenhouse adapter."""
    from .base import SearchConfig
    
    adapter = GreenhouseAdapter()
    
    criteria = SearchConfig(
        roles=["software engineer", "backend", "full stack"],
        locations=["Remote", "San Francisco"],
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
    asyncio.run(test_greenhouse())
