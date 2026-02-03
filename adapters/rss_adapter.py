"""
RSS Feed Adapter - Tier 4 (Legacy but reliable)
Works for Indeed RSS, Dice, Craigslist, etc.
No anti-bot issues since it's public XML.
"""

import aiohttp
import asyncio
import xml.etree.ElementTree as ET
from typing import List, Optional
from datetime import datetime
from urllib.parse import quote_plus

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


class RSSAdapter(JobPlatformAdapter):
    """
    RSS Feed adapter for job boards with XML feeds.
    Works with Indeed RSS, Dice, Craigslist, etc.
    """
    
    platform = PlatformType.RSS
    tier = "rss"
    
    # RSS feed URL templates
    FEEDS = {
        "indeed": "https://www.indeed.com/rss?q={query}&l={location}&fromage={days}",
        "dice": "https://www.dice.com/jobs/rss?q={query}&location={location}",
        "craigslist": "https://{city}.craigslist.org/search/sof?format=rss&query={query}",
    }
    
    def __init__(self, browser_manager=None, sources: List[str] = None):
        super().__init__(browser_manager)
        self.sources = sources or ["indeed"]
        self._session = None
    
    async def _get_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0 (compatible; JobRSSReader/1.0)"}
            )
        return self._session
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search job boards via RSS feeds."""
        session = await self._get_session()
        all_jobs = []
        
        query = quote_plus(" ".join(criteria.roles))
        location = quote_plus(criteria.locations[0] if criteria.locations else "Remote")
        days = criteria.posted_within_days
        
        for source in self.sources:
            try:
                if source == "indeed":
                    url = self.FEEDS["indeed"].format(query=query, location=location, days=days)
                    jobs = await self._parse_indeed_rss(session, url)
                    all_jobs.extend(jobs)
                    
                elif source == "dice":
                    url = self.FEEDS["dice"].format(query=query, location=location)
                    jobs = await self._parse_dice_rss(session, url)
                    all_jobs.extend(jobs)
                    
            except Exception as e:
                print(f"[RSS] Error fetching {source}: {e}")
                continue
        
        print(f"[RSS] Found {len(all_jobs)} jobs from {len(self.sources)} sources")
        return all_jobs
    
    async def _parse_indeed_rss(self, session, url: str) -> List[JobPosting]:
        """Parse Indeed RSS feed."""
        jobs = []
        
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return jobs
            
            text = await resp.text()
            root = ET.fromstring(text)
            
            for item in root.findall(".//item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                description = item.findtext("description", "")
                pub_date = item.findtext("pubDate", "")
                
                # Indeed includes company and location in title
                # Format: "Job Title - Company - Location"
                parts = title.split(" - ")
                job_title = parts[0] if parts else title
                company = parts[1] if len(parts) > 1 else ""
                location = parts[2] if len(parts) > 2 else ""
                
                jobs.append(JobPosting(
                    id=f"rss_indeed_{hash(link)}",
                    platform=PlatformType.INDEED,
                    title=job_title.strip(),
                    company=company.strip(),
                    location=location.strip(),
                    url=link,
                    description=description,
                    easy_apply=False,
                    remote="remote" in location.lower()
                ))
        
        return jobs
    
    async def _parse_dice_rss(self, session, url: str) -> List[JobPosting]:
        """Parse Dice RSS feed."""
        jobs = []
        
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return jobs
            
            text = await resp.text()
            root = ET.fromstring(text)
            
            for item in root.findall(".//item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                description = item.findtext("description", "")
                company = item.findtext("{http://www.dice.com/}company", "")
                location = item.findtext("{http://www.dice.com/}location", "")
                
                jobs.append(JobPosting(
                    id=f"rss_dice_{hash(link)}",
                    platform=PlatformType.DICE,
                    title=title.strip(),
                    company=company.strip(),
                    location=location.strip(),
                    url=link,
                    description=description,
                    easy_apply=False,
                    remote="remote" in location.lower()
                ))
        
        return jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get job details - for RSS, we just return the URL."""
        return JobPosting(
            id=f"rss_{hash(job_url)}",
            platform=self.platform,
            title="See job posting",
            company="",
            location="",
            url=job_url,
            easy_apply=False
        )
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """RSS jobs require visiting the site to apply."""
        return ApplicationResult(
            status=ApplicationStatus.EXTERNAL_APPLICATION,
            message=f"Apply at: {job.url}",
            external_url=job.url
        )


async def test_rss():
    """Test RSS adapter."""
    from .base import SearchConfig
    
    adapter = RSSAdapter(sources=["indeed"])
    
    criteria = SearchConfig(
        roles=["software engineer"],
        locations=["San Francisco"],
        posted_within_days=7
    )
    
    try:
        jobs = await adapter.search_jobs(criteria)
        print(f"\nFound {len(jobs)} jobs:")
        for job in jobs[:10]:
            print(f"  - {job.title} at {job.company} ({job.location})")
            print(f"    URL: {job.url}")
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(test_rss())
