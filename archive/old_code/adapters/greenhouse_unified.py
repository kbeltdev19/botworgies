"""
Greenhouse Adapter - Unified Version

Uses API for search, UnifiedJobAdapter for application.
This is the migrated version using the new architecture.
"""

import aiohttp
import asyncio
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)
from core.adapter_base import UnifiedJobAdapter, AdapterConfig

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
    "doordash", "instacart", "pinterest", "twitch", "lyft",
    "dropbox", "cloudflare", "datadog", "mongodb", "elastic",
    "confluent", "hashicorp", "snowflake", "databricks", "palantir",
    "webflow", "loom", "miro", "zapier", "deel",
    "replit", "railway", "render", "fly", "supabase",
]


class GreenhouseUnifiedAdapter(UnifiedJobAdapter):
    """
    Greenhouse adapter using UnifiedJobAdapter base.
    
    Search: API-based (no browser)
    Apply: Browser-based with unified form filling
    """
    
    PLATFORM = "greenhouse"
    PLATFORM_TYPE = PlatformType.GREENHOUSE
    
    # Standard Greenhouse form selectors
    SELECTORS = {
        'first_name': ['#first_name', 'input[name="first_name"]', 'input[name="firstName"]'],
        'last_name': ['#last_name', 'input[name="last_name"]', 'input[name="lastName"]'],
        'email': ['#email', 'input[type="email"]', 'input[name="email"]'],
        'phone': ['#phone', 'input[name="phone"]', 'input[type="tel"]'],
        'location': ['#job_application_location', 'input[name="location"]', '#location'],
        'linkedin': ['#job_application_answers_attributes_0_text_value', 'input[name="linkedin"]', 'input[placeholder*="LinkedIn"]'],
        'website': ['#job_application_answers_attributes_1_text_value', 'input[name="website"]', 'input[placeholder*="portfolio"]'],
        'resume': ['input[type="file"]', '#resume', 'input[name="resume"]'],
        'cover_letter': ['textarea[name="cover_letter"]', '#cover_letter', 'textarea[placeholder*="cover letter" i]'],
        'submit': ['#submit_app', 'input[type="submit"]', 'button[type="submit"]', '[data-qa="submit-button"]'],
        'success': ['.thank-you', '.confirmation', '[class*="success"]', '#application_confirmation'],
        'error': ['.error-message', '.field-error', '[class*="error" i]'],
        'apply_button': ['#apply_button', '.apply-button', 'a:has-text("Apply")', '[data-qa="apply-button"]'],
    }
    
    CONFIG = AdapterConfig(
        auto_submit=False,
        capture_screenshots=True,
        max_form_steps=5,
        navigation_timeout=30000,
        element_timeout=10000
    )
    
    def __init__(self, browser_manager, companies: List[str] = None, 
                 industries: List[str] = None, sizes: List[str] = None,
                 max_companies: int = 50, session_cookie: str = None):
        super().__init__(browser_manager, session_cookie, self.CONFIG)
        
        # API search setup
        if companies:
            self.companies = companies
        elif DISCOVERY_AVAILABLE:
            discovery = CompanyDiscovery()
            self.companies = discovery.get_companies(
                "greenhouse", industries=industries, sizes=sizes, limit=max_companies
            )
        else:
            self.companies = DEFAULT_GREENHOUSE_COMPANIES[:max_companies]
        
        self._api_session = None
        print(f"[GreenhouseUnified] Initialized with {len(self.companies)} companies")
    
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
    # Search (API-based, no browser needed)
    # ========================================================================
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search Greenhouse job boards across multiple companies."""
        session = await self._get_api_session()
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
                        
                        # Filter by location
                        if criteria.locations and location_lower:
                            if not any(loc.lower() in location or "remote" in location 
                                      for loc in criteria.locations):
                                continue
                        
                        all_jobs.append(JobPosting(
                            id=f"gh_{company}_{job['id']}",
                            platform=self.PLATFORM_TYPE,
                            title=job.get("title", ""),
                            company=company.replace("-", " ").title(),
                            location=job.get("location", {}).get("name", ""),
                            url=job.get("absolute_url", f"https://boards.greenhouse.io/{company}/jobs/{job['id']}"),
                            description=job.get("content", ""),
                            easy_apply=True,
                            remote="remote" in location
                        ))
                
                await asyncio.sleep(0.2)  # Be nice to the API
                
            except Exception as e:
                print(f"[GreenhouseUnified] Error fetching {company}: {e}")
                continue
        
        print(f"[GreenhouseUnified] Found {len(all_jobs)} jobs across {len(self.companies)} companies")
        return all_jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details from Greenhouse API."""
        session = await self._get_api_session()
        
        # Extract company and job ID from URL
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
                platform=self.PLATFORM_TYPE,
                title=data.get("title", ""),
                company=company.replace("-", " ").title(),
                location=data.get("location", {}).get("name", ""),
                url=data.get("absolute_url", job_url),
                description=data.get("content", ""),
                easy_apply=True,
                remote="remote" in data.get("location", {}).get("name", "").lower()
            )
    
    # ========================================================================
    # Application (Browser-based with unified form filling)
    # ========================================================================
    
    async def _navigate_to_application(self, job: JobPosting):
        """Navigate to Greenhouse application form."""
        await self.page.goto(job.url, timeout=self.config.navigation_timeout)
        
        # Wait for page to load
        await self.page.wait_for_load_state('networkidle')
        
        # Click apply button if present
        for selector in self.SELECTORS['apply_button']:
            try:
                apply_btn = self.page.locator(selector).first
                if await apply_btn.count() > 0 and await apply_btn.is_visible():
                    await apply_btn.click()
                    await self.page.wait_for_load_state('networkidle')
                    break
            except:
                continue
        
        # Wait for form to appear
        await self.page.wait_for_selector(
            '#application_form, #first_name, input[type="email"]',
            timeout=self.config.element_timeout
        )
    
    async def _extract_confirmation_id(self) -> Optional[str]:
        """Extract confirmation ID from Greenhouse success page."""
        # Greenhouse typically shows confirmation in URL or page
        try:
            # Check URL for confirmation ID
            current_url = self.page.url
            if 'application_confirmation' in current_url:
                parts = current_url.split('/')
                for part in reversed(parts):
                    if part and part.isdigit():
                        return f"GH-{part}"
            
            # Check page content
            text = await self.page.inner_text('body')
            import re
            patterns = [
                r'application\s*[#:]?\s*([A-Z0-9\-]+)',
                r'confirmation\s*[#:]?\s*([A-Z0-9\-]+)',
                r'reference\s*[#:]?\s*([A-Z0-9\-]+)',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    return matches[0]
        except:
            pass
        
        return None


# Keep old adapter for backward compatibility
GreenhouseAdapter = GreenhouseUnifiedAdapter


async def test_greenhouse_unified():
    """Test the unified Greenhouse adapter."""
    from browser.stealth_manager import StealthBrowserManager
    from adapters.base import SearchConfig
    
    print("=" * 70)
    print("TESTING GREENHOUSE UNIFIED ADAPTER")
    print("=" * 70)
    
    browser = StealthBrowserManager()
    adapter = GreenhouseUnifiedAdapter(browser, max_companies=5)
    
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
    asyncio.run(test_greenhouse_unified())
