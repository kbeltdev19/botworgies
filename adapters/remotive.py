"""
Remotive Adapter - Tier 3 (API-Based)
Simple JSON API for remote jobs.
"""

import aiohttp
import asyncio
import html
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


class RemotiveAdapter(JobPlatformAdapter):
    """
    Remotive.com job board adapter.
    Simple JSON API with category filtering.
    Remote-only jobs.
    """
    
    platform = PlatformType.REMOTIVE
    tier = "api"
    
    API_URL = "https://remotive.com/api/remote-jobs"
    
    # Category mapping
    CATEGORIES = {
        "software": "software-dev",
        "developer": "software-dev",
        "engineering": "software-dev",
        "design": "design",
        "marketing": "marketing",
        "sales": "sales",
        "support": "customer-support",
        "product": "product",
        "data": "data",
        "devops": "devops",
        "sysadmin": "sysadmin",
        "finance": "finance",
        "hr": "hr",
        "writing": "writing",
    }
    
    def __init__(self, browser_manager=None, category: str = None):
        super().__init__(browser_manager)
        self.category = category
        self._session = None
    
    async def _get_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)",
                    "Accept": "application/json",
                }
            )
        return self._session
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search Remotive for remote jobs."""
        session = await self._get_session()
        all_jobs = []
        
        query_lower = " ".join(criteria.roles).lower()
        
        # Determine category from roles
        category = None
        for role in criteria.roles:
            role_lower = role.lower()
            for keyword, cat in self.CATEGORIES.items():
                if keyword in role_lower:
                    category = cat
                    break
            if category:
                break
        
        try:
            # Build URL with optional category
            url = self.API_URL
            if category:
                url = f"{self.API_URL}?category={category}"
            
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    print(f"[Remotive] API error: {resp.status}")
                    return []
                
                data = await resp.json()
                jobs = data.get("jobs", [])
                
                for job in jobs:
                    title = html.unescape(job.get("title", ""))
                    title_lower = title.lower()
                    
                    # Filter by role keywords
                    if not any(kw.lower() in title_lower for kw in criteria.roles):
                        continue
                    
                    # Parse publication date
                    pub_date = None
                    pub_date_str = job.get("publication_date", "")
                    if pub_date_str:
                        try:
                            pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                        except ValueError:
                            pass
                    
                    # Check if within date range
                    if criteria.posted_within_days and pub_date:
                        days_ago = (datetime.now(pub_date.tzinfo) - pub_date).days
                        if days_ago > criteria.posted_within_days:
                            continue
                    
                    # Build description
                    description_parts = []
                    if job.get("description"):
                        description_parts.append(html.unescape(job.get("description", "")))
                    if job.get("tags"):
                        description_parts.append(f"Tags: {', '.join(job['tags'])}")
                    if job.get("job_type"):
                        description_parts.append(f"Type: {job['job_type']}")
                    
                    description = "\n".join(description_parts)
                    
                    all_jobs.append(JobPosting(
                        id=f"remotive_{job.get('id', hash(title))}",
                        platform=self.platform,
                        title=title,
                        company=html.unescape(job.get("company_name", "")),
                        location=job.get("candidate_required_location", "Remote"),
                        url=job.get("url", ""),
                        description=description,
                        easy_apply=True,
                        remote=True,
                        salary_range=job.get("salary", ""),
                        posted_date=pub_date,
                        job_type=job.get("job_type", "full-time").lower()
                    ))
        
        except Exception as e:
            print(f"[Remotive] Error: {e}")
        
        print(f"[Remotive] Found {len(all_jobs)} jobs")
        return all_jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get job details - API already returns full details."""
        return JobPosting(
            id=f"remotive_{hash(job_url)}",
            platform=self.platform,
            title="See job posting",
            company="",
            location="Remote",
            url=job_url,
            remote=True,
            easy_apply=True
        )
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """Apply to Remotive job."""
        return ApplicationResult(
            status=ApplicationStatus.EXTERNAL_APPLICATION,
            message=f"Apply at: {job.url}",
            external_url=job.url
        )


async def test_remotive():
    """Test Remotive adapter."""
    from .base import SearchConfig
    
    adapter = RemotiveAdapter()
    
    criteria = SearchConfig(
        roles=["software engineer", "developer", "full stack"],
        locations=["Remote"],
        posted_within_days=30
    )
    
    try:
        jobs = await adapter.search_jobs(criteria)
        print(f"\nFound {len(jobs)} jobs:")
        for job in jobs[:10]:
            print(f"  - {job.title} at {job.company}")
            if job.salary_range:
                print(f"    Salary: {job.salary_range}")
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(test_remotive())
