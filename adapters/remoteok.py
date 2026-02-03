"""
RemoteOK Adapter - Tier 3 (API-Based)
Simple JSON API for remote tech jobs.
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


class RemoteOKAdapter(JobPlatformAdapter):
    """
    RemoteOK.com job board adapter.
    Simple JSON API, no auth required.
    Remote-only jobs.
    """
    
    platform = PlatformType.REMOTEOK
    tier = "api"
    
    API_URL = "https://remoteok.com/api"
    
    def __init__(self, browser_manager=None):
        super().__init__(browser_manager)
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
        """Search RemoteOK for remote jobs."""
        session = await self._get_session()
        all_jobs = []
        
        query_lower = " ".join(criteria.roles).lower()
        
        try:
            # RemoteOK API returns all jobs, we filter client-side
            async with session.get(
                self.API_URL,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    print(f"[RemoteOK] API error: {resp.status}")
                    return []
                
                # First element is usually a legal/ad disclaimer
                data = await resp.json()
                
                for job in data[1:] if len(data) > 1 else data:  # Skip first element if it's an ad
                    if not isinstance(job, dict):
                        continue
                    
                    title = html.unescape(job.get("position", ""))
                    title_lower = title.lower()
                    
                    # Filter by role keywords
                    if not any(kw.lower() in title_lower for kw in criteria.roles):
                        continue
                    
                    # Get tags/keywords
                    tags = job.get("tags", [])
                    tags_str = ", ".join(tags) if tags else ""
                    
                    # Build description from tags and other info
                    description_parts = []
                    if job.get("description"):
                        description_parts.append(html.unescape(job.get("description", "")))
                    if tags:
                        description_parts.append(f"Tags: {tags_str}")
                    
                    description = "\n".join(description_parts)
                    
                    all_jobs.append(JobPosting(
                        id=f"remoteok_{job.get('id', job.get('slug', hash(title)))}",
                        platform=self.platform,
                        title=title,
                        company=html.unescape(job.get("company", "")),
                        location="Remote",
                        url=job.get("apply_url", job.get("url", "")),
                        description=description,
                        easy_apply=True,
                        remote=True,
                        salary_range=job.get("salary", ""),
                        posted_date=datetime.fromtimestamp(job.get("epoch", 0)) if job.get("epoch") else None,
                        job_type=job.get("type", "full-time").lower()
                    ))
        
        except Exception as e:
            print(f"[RemoteOK] Error: {e}")
        
        print(f"[RemoteOK] Found {len(all_jobs)} jobs")
        return all_jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get job details - API already returns full details."""
        # RemoteOK API returns full details, so we can just return what we have
        # If needed, we could fetch by slug
        return JobPosting(
            id=f"remoteok_{hash(job_url)}",
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
        """Apply to RemoteOK job."""
        return ApplicationResult(
            status=ApplicationStatus.EXTERNAL_APPLICATION,
            message=f"Apply at: {job.url}",
            external_url=job.url
        )


async def test_remoteok():
    """Test RemoteOK adapter."""
    from .base import SearchConfig
    
    adapter = RemoteOKAdapter()
    
    criteria = SearchConfig(
        roles=["software engineer", "developer", "backend"],
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
    asyncio.run(test_remoteok())
