"""
Lever Adapter - Unified Version

Uses API for search, UnifiedJobAdapter for application.
This is the migrated version using the new architecture.
"""

import aiohttp
import asyncio
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)
from core.adapter_base import UnifiedJobAdapter, AdapterConfig

# Popular companies using Lever
DEFAULT_LEVER_COMPANIES = [
    "netflix", "twitch", "lyft", "spotify", "cloudflare",
    "databricks", "dbt-labs", "hashicorp", "pulumi", "temporal",
    "cockroachlabs", "materialize", "singlestore", "neon", "supabase",
    "railway", "render", "fly", "modal", "replicate",
]


class LeverUnifiedAdapter(UnifiedJobAdapter):
    """
    Lever adapter using UnifiedJobAdapter base.
    
    Search: API-based (no browser)
    Apply: Browser-based with unified form filling
    """
    
    PLATFORM = "lever"
    PLATFORM_TYPE = PlatformType.LEVER
    
    # Standard Lever form selectors
    SELECTORS = {
        'first_name': ['input[name="name[first]"]', '#first_name', 'input[name="firstName"]'],
        'last_name': ['input[name="name[last]"]', '#last_name', 'input[name="lastName"]'],
        'email': ['input[name="email"]', 'input[type="email"]', '#email'],
        'phone': ['input[name="phone"]', 'input[type="tel"]', '#phone'],
        'location': ['input[name="location"]', '#location', 'input[placeholder*="Location"]'],
        'linkedin': ['input[name="urls[LinkedIn]"]', 'input[placeholder*="LinkedIn"]', '#linkedin'],
        'github': ['input[name="urls[GitHub]"]', 'input[placeholder*="GitHub"]', '#github'],
        'portfolio': ['input[name="urls[Portfolio]"]', 'input[placeholder*="Portfolio"]', '#portfolio'],
        'resume': ['input[type="file"]', '.resume-upload input', '#resume'],
        'cover_letter': ['textarea[name="comments"]', '#cover_letter', 'textarea[placeholder*="cover letter" i]'],
        'submit': ['button[type="submit"]', '.application-form button:last-child', '[data-qa="submit-button"]'],
        'success': ['.postings-nav', '.thank-you', '[class*="success"]', '#application_confirmation'],
        'error': ['.error-message', '.field-error', '[class*="error" i]'],
        'apply_button': ['.posting-btn', 'a:has-text("Apply")', '[data-qa="apply-button"]'],
    }
    
    CONFIG = AdapterConfig(
        auto_submit=False,
        capture_screenshots=True,
        max_form_steps=3,
        navigation_timeout=30000,
        element_timeout=10000
    )
    
    def __init__(self, browser_manager, companies: List[str] = None, session_cookie: str = None):
        super().__init__(browser_manager, session_cookie, self.CONFIG)
        self.companies = companies or DEFAULT_LEVER_COMPANIES
        self._api_session = None
    
    async def _get_api_session(self):
        """Get aiohttp session for API calls."""
        if not self._api_session:
            self._api_session = aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"}
            )
        return self._api_session
    
    async def close(self):
        """Close API session."""
        if self._api_session:
            await self._api_session.close()
            self._api_session = None
        await super()._cleanup()
    
    # ========================================================================
    # Search (API-based)
    # ========================================================================
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search Lever job boards across multiple companies."""
        session = await self._get_api_session()
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
                        
                        # Filter by location
                        if criteria.locations:
                            if not any(loc.lower() in location or "remote" in location 
                                      for loc in criteria.locations):
                                continue
                        
                        all_jobs.append(JobPosting(
                            id=f"lever_{job['id']}",
                            platform=self.PLATFORM_TYPE,
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
                print(f"[LeverUnified] Error fetching {company}: {e}")
                continue
        
        print(f"[LeverUnified] Found {len(all_jobs)} jobs across {len(self.companies)} companies")
        return all_jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details from Lever."""
        session = await self._get_api_session()
        
        # Extract job ID from URL
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
                platform=self.PLATFORM_TYPE,
                title=data.get("text", ""),
                company=company.replace("-", " ").title(),
                location=data.get("categories", {}).get("location", ""),
                url=data.get("hostedUrl", job_url),
                description=data.get("descriptionPlain", ""),
                easy_apply=True,
                remote="remote" in data.get("categories", {}).get("location", "").lower()
            )
    
    # ========================================================================
    # Application (Browser-based)
    # ========================================================================
    
    async def _navigate_to_application(self, job: JobPosting):
        """Navigate to Lever application form."""
        await self.page.goto(job.url, timeout=self.config.navigation_timeout)
        await self.page.wait_for_load_state('networkidle')
        
        # Lever sometimes shows apply button
        for selector in self.SELECTORS['apply_button']:
            try:
                apply_btn = self.page.locator(selector).first
                if await apply_btn.count() > 0 and await apply_btn.is_visible():
                    await apply_btn.click()
                    await self.page.wait_for_load_state('networkidle')
                    break
            except:
                continue
        
        # Wait for form
        await self.page.wait_for_selector(
            'input[name="name[first]"], input[name="email"], input[type="email"]',
            timeout=self.config.element_timeout
        )


# Keep old adapter for backward compatibility
LeverAdapter = LeverUnifiedAdapter


async def test_lever_unified():
    """Test the unified Lever adapter."""
    from browser.stealth_manager import StealthBrowserManager
    from adapters.base import SearchConfig
    
    print("=" * 70)
    print("TESTING LEVER UNIFIED ADAPTER")
    print("=" * 70)
    
    browser = StealthBrowserManager()
    adapter = LeverUnifiedAdapter(browser, companies=["netflix", "spotify"])
    
    # Test search
    print("\n1. Testing search...")
    criteria = SearchConfig(
        roles=["software engineer", "backend"],
        locations=["Remote"],
    )
    
    jobs = await adapter.search_jobs(criteria)
    print(f"   Found {len(jobs)} jobs")
    
    if jobs:
        job = jobs[0]
        print(f"\n2. Sample job: {job.title} at {job.company}")
        print(f"   URL: {job.url}")
    
    await adapter.close()
    print("\n✅ Test complete")


if __name__ == "__main__":
    asyncio.run(test_lever_unified())
