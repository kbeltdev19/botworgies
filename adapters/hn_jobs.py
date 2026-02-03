"""
Hacker News Jobs Adapter - Tier 4 (Easy)
Uses Algolia API - completely bot-friendly, just JSON.
Parses monthly "Who is Hiring" threads.
"""

import aiohttp
import asyncio
import re
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting,
    SearchConfig
)


class HNJobsAdapter(JobPlatformAdapter):
    """
    Hacker News "Who is Hiring" thread parser.
    Uses Algolia's HN API - completely free and bot-friendly.
    """
    
    platform = PlatformType.EXTERNAL
    tier = "api"
    
    ALGOLIA_URL = "https://hn.algolia.com/api/v1"
    
    def __init__(self, browser_manager=None):
        super().__init__(browser_manager)
        self._session = None
    
    async def _get_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search HN Who is Hiring threads."""
        session = await self._get_session()
        
        # Find the most recent "Who is Hiring" thread
        thread_id = await self._find_latest_hiring_thread(session)
        if not thread_id:
            print("[HN Jobs] No hiring thread found")
            return []
        
        # Get all comments from that thread
        comments = await self._get_thread_comments(session, thread_id)
        
        # Parse job postings from comments
        jobs = []
        query_lower = " ".join(criteria.roles).lower()
        location_lower = " ".join(criteria.locations).lower() if criteria.locations else ""
        
        for comment in comments:
            job = self._parse_job_comment(comment, query_lower, location_lower)
            if job:
                jobs.append(job)
        
        print(f"[HN Jobs] Found {len(jobs)} matching jobs from {len(comments)} postings")
        return jobs
    
    async def _find_latest_hiring_thread(self, session) -> Optional[int]:
        """Find the most recent 'Who is Hiring' thread."""
        url = f"{self.ALGOLIA_URL}/search_by_date"
        params = {
            "query": "Ask HN: Who is hiring",
            "tags": "story",
            "hitsPerPage": 20
        }
        
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return None
            
            data = await resp.json()
            hits = data.get("hits", [])
            
            # Find the most recent "Who is hiring" (monthly)
            for hit in hits:
                title = hit.get("title", "").lower()
                # Match patterns like "Who is hiring? (February 2026)"
                if "who is hiring" in title and "who wants to be hired" not in title:
                    print(f"[HN Jobs] Using thread: {hit.get('title')}")
                    return hit.get("objectID")
        
        return None
    
    async def _get_thread_comments(self, session, thread_id: int) -> List[dict]:
        """Get all top-level comments from a thread."""
        url = f"{self.ALGOLIA_URL}/items/{thread_id}"
        
        async with session.get(url) as resp:
            if resp.status != 200:
                return []
            
            data = await resp.json()
            return data.get("children", [])
    
    def _parse_job_comment(self, comment: dict, query: str, location: str) -> Optional[JobPosting]:
        """Parse a job posting from a HN comment."""
        text = comment.get("text", "")
        if not text:
            return None
        
        # Decode HTML entities
        text = text.replace("&#x27;", "'").replace("&amp;", "&").replace("&#x2F;", "/")
        
        # HN job posts usually start with: "Company Name | Role | Location | ..."
        # Parse the first line
        first_line = text.split("<p>")[0] if "<p>" in text else text.split("\n")[0]
        first_line = re.sub(r'<[^>]+>', '', first_line)  # Strip HTML
        
        # Split by | or -
        parts = re.split(r'\s*[\|–-]\s*', first_line)
        
        if len(parts) < 1:
            return None
        
        company = parts[0].strip()
        if not company or len(company) < 2:
            return None
        
        # Try to extract title and location from remaining parts
        title = ""
        job_location = ""
        remote = False
        url = ""
        
        text_lower = text.lower()
        
        # Check for remote anywhere in the text
        remote = 'remote' in text_lower
        
        for part in parts[1:]:
            part_lower = part.lower().strip()
            if any(word in part_lower for word in ['remote', 'onsite', 'hybrid', 'sf', 'nyc', 'usa', 'eu', 'london', 'berlin', 'worldwide']):
                job_location = part.strip()
            elif any(word in part_lower for word in ['engineer', 'developer', 'manager', 'designer', 'analyst', 'lead', 'senior', 'junior', 'full', 'stack', 'backend', 'frontend']):
                title = part.strip()
            elif 'http' in part_lower:
                url = part.strip()
        
        if not title:
            title = parts[1].strip() if len(parts) > 1 else "Multiple roles"
        
        # Less strict filtering - just check if any query word appears
        if query:
            query_words = query.lower().split()
            if not any(word in text_lower for word in query_words):
                return None
        
        # Location filter - if specified, check for remote or location match
        if location:
            location_lower = location.lower()
            if location_lower != 'remote':
                if location_lower not in text_lower and 'remote' not in text_lower:
                    return None
        
        # Extract URL from comment text
        if not url:
            url_match = re.search(r'https?://[^\s<>"\']+', text)
            if url_match:
                url = url_match.group(0).rstrip('.')
            else:
                url = f"https://news.ycombinator.com/item?id={comment.get('id', '')}"
        
        return JobPosting(
            id=f"hn_{comment.get('id', '')}",
            platform=self.platform,
            title=title[:100],
            company=company[:50],
            location=job_location or ("Remote" if remote else "See posting"),
            url=url,
            description=re.sub(r'<[^>]+>', ' ', text)[:500],
            remote=remote,
            easy_apply=False
        )
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get job details - for HN, return the comment."""
        return JobPosting(
            id=f"hn_{hash(job_url)}",
            platform=self.platform,
            title="See HN posting",
            company="",
            location="",
            url=job_url,
            easy_apply=False
        )
    
    async def apply_to_job(self, job, resume, profile, cover_letter=None, auto_submit=False):
        """HN jobs require visiting the company site."""
        from .base import ApplicationResult, ApplicationStatus
        return ApplicationResult(
            status=ApplicationStatus.EXTERNAL_APPLICATION,
            message=f"Apply at: {job.url}",
            external_url=job.url
        )


async def test_hn_jobs():
    """Test HN Jobs adapter."""
    from .base import SearchConfig
    
    adapter = HNJobsAdapter()
    
    criteria = SearchConfig(
        roles=["software engineer", "backend", "full stack"],
        locations=["Remote"],
        posted_within_days=30
    )
    
    try:
        jobs = await adapter.search_jobs(criteria)
        print(f"\nFound {len(jobs)} jobs:")
        for job in jobs[:10]:
            print(f"  - {job.title} at {job.company} ({job.location})")
            print(f"    {job.url[:60]}...")
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(test_hn_jobs())
