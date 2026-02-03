"""
WeWorkRemotely Adapter - Tier 4 (Easy)
Simple Rails app, easy to scrape. No anti-bot.
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


class WeWorkRemotelyAdapter(JobPlatformAdapter):
    """
    WeWorkRemotely.com adapter.
    Remote-only jobs, simple HTML scraping.
    """
    
    platform = PlatformType.EXTERNAL
    tier = "scrape"
    
    BASE_URL = "https://weworkremotely.com"
    
    # Categories to search
    CATEGORIES = [
        "remote-jobs/programming",
        "remote-jobs/design",
        "remote-jobs/devops-sysadmin",
        "remote-jobs/product",
        "remote-jobs/data",
    ]
    
    def __init__(self, browser_manager=None):
        super().__init__(browser_manager)
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
        """Search WeWorkRemotely for jobs."""
        session = await self._get_session()
        all_jobs = []
        
        query_lower = " ".join(criteria.roles).lower()
        
        for category in self.CATEGORIES:
            try:
                url = f"{self.BASE_URL}/{category}"
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        continue
                    
                    html = await resp.text()
                    jobs = self._parse_job_listings(html, query_lower)
                    all_jobs.extend(jobs)
                
                # Small delay between categories
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"[WWR] Error fetching {category}: {e}")
                continue
        
        print(f"[WWR] Found {len(all_jobs)} jobs from {len(self.CATEGORIES)} categories")
        return all_jobs
    
    def _parse_job_listings(self, html: str, query: str) -> List[JobPosting]:
        """Parse job listings from HTML."""
        jobs = []
        
        # Find all job listing sections
        # WWR uses <li class="feature"> or <li> within <ul class="jobs">
        job_pattern = re.compile(
            r'<li[^>]*class="[^"]*feature[^"]*"[^>]*>.*?</li>|'
            r'<section[^>]*class="[^"]*jobs[^"]*"[^>]*>.*?</section>',
            re.DOTALL
        )
        
        # Simpler pattern: find job links
        link_pattern = re.compile(
            r'<a[^>]*href="(/remote-jobs/[^"]+)"[^>]*>.*?'
            r'<span[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</span>.*?'
            r'<span[^>]*class="[^"]*company[^"]*"[^>]*>(.*?)</span>',
            re.DOTALL
        )
        
        for match in link_pattern.finditer(html):
            try:
                href = match.group(1)
                title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                company = re.sub(r'<[^>]+>', '', match.group(3)).strip()
                
                # Filter by query
                if query and query not in title.lower() and query not in company.lower():
                    continue
                
                jobs.append(JobPosting(
                    id=f"wwr_{hash(href)}",
                    platform=self.platform,
                    title=title,
                    company=company,
                    location="Remote",
                    url=f"{self.BASE_URL}{href}",
                    remote=True,
                    easy_apply=False
                ))
            except Exception:
                continue
        
        # Alternative simpler pattern if the above doesn't match
        if not jobs:
            # Look for any job-related links
            simple_pattern = re.compile(
                r'<a[^>]*href="(/remote-jobs/[^"]+)"[^>]*>(.*?)</a>',
                re.DOTALL
            )
            
            for match in simple_pattern.finditer(html):
                href = match.group(1)
                text = re.sub(r'<[^>]+>', ' ', match.group(2)).strip()
                
                if not text or len(text) < 5:
                    continue
                
                # Skip navigation links
                if any(skip in href for skip in ['/categories', '/search', '/companies']):
                    continue
                
                if query and query not in text.lower():
                    continue
                
                jobs.append(JobPosting(
                    id=f"wwr_{hash(href)}",
                    platform=self.platform,
                    title=text[:100],
                    company="(see listing)",
                    location="Remote",
                    url=f"{self.BASE_URL}{href}",
                    remote=True,
                    easy_apply=False
                ))
        
        return jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details."""
        session = await self._get_session()
        
        async with session.get(job_url) as resp:
            if resp.status != 200:
                raise Exception(f"Job not found: {job_url}")
            
            html = await resp.text()
            
            # Extract title
            title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html)
            title = re.sub(r'<[^>]+>', '', title_match.group(1)) if title_match else ""
            
            # Extract company
            company_match = re.search(r'<h2[^>]*class="[^"]*company[^"]*"[^>]*>(.*?)</h2>', html)
            company = re.sub(r'<[^>]+>', '', company_match.group(1)) if company_match else ""
            
            # Extract description
            desc_match = re.search(r'<div[^>]*class="[^"]*listing-container[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            description = re.sub(r'<[^>]+>', ' ', desc_match.group(1))[:500] if desc_match else ""
            
            return JobPosting(
                id=f"wwr_{hash(job_url)}",
                platform=self.platform,
                title=title.strip(),
                company=company.strip(),
                location="Remote",
                url=job_url,
                description=description.strip(),
                remote=True,
                easy_apply=False
            )
    
    async def apply_to_job(self, job, resume, profile, cover_letter=None, auto_submit=False):
        """WWR jobs require visiting the company site."""
        from .base import ApplicationResult, ApplicationStatus
        return ApplicationResult(
            status=ApplicationStatus.EXTERNAL_APPLICATION,
            message=f"Apply at: {job.url}",
            external_url=job.url
        )


async def test_wwr():
    """Test WeWorkRemotely adapter."""
    from .base import SearchConfig
    
    adapter = WeWorkRemotelyAdapter()
    
    criteria = SearchConfig(
        roles=["engineer", "developer"],
        locations=["Remote"],
        posted_within_days=30
    )
    
    try:
        jobs = await adapter.search_jobs(criteria)
        print(f"\nFound {len(jobs)} jobs:")
        for job in jobs[:10]:
            print(f"  - {job.title} at {job.company}")
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(test_wwr())
