"""
Greenhouse Adapter - Tier 1 (API-Based)
Direct JSON endpoints, no browser needed.
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
        Greenhouse applications are typically a public web form.

        Implementation notes:
        - Fill core fields (name/email/phone) + resume upload.
        - If CAPTCHA is present, do not attempt to bypass it; return PENDING_REVIEW.
        - If auto_submit is False, stop at review with a screenshot.
        """
        if not self.browser_manager:
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message=f"Apply at: {job.url}",
                external_url=job.url,
            )

        session = await self.browser_manager.create_session(self.platform.value)
        page = session.page

        async def try_fill(selectors: List[str], value: str) -> bool:
            value = (value or "").strip()
            if not value:
                return False
            for sel in selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.fill(value)
                        await asyncio.sleep(0.2)
                        return True
                except Exception:
                    continue
            return False

        async def try_upload(selectors: List[str], file_path: str) -> bool:
            if not file_path or not Path(file_path).exists():
                return False
            for sel in selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0:
                        await loc.set_input_files(file_path)
                        await asyncio.sleep(0.5)
                        return True
                except Exception:
                    continue
            return False

        async def detect_captcha() -> bool:
            selectors = [
                'iframe[src*="recaptcha"]',
                'iframe[src*="captcha"]',
                ".g-recaptcha",
                "[data-sitekey]",
            ]
            for sel in selectors:
                try:
                    if await page.locator(sel).count() > 0:
                        return True
                except Exception:
                    continue
            return False

        screenshot_path = None
        try:
            await page.goto(job.url, wait_until="domcontentloaded", timeout=60000)
            await self.browser_manager.human_like_delay(2, 4)

            # Some Greenhouse postings require clicking "Apply" to reveal the form.
            for sel in [
                'a:has-text("Apply")',
                'button:has-text("Apply")',
                'a#apply_button',
                'a[href*="#application"]',
            ]:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(1)
                        break
                except Exception:
                    continue

            # Core fields
            await try_fill(
                [
                    "input#first_name",
                    "input[name='job_application[first_name]']",
                    "input[name*='first_name' i]",
                ],
                profile.first_name,
            )
            await try_fill(
                [
                    "input#last_name",
                    "input[name='job_application[last_name]']",
                    "input[name*='last_name' i]",
                ],
                profile.last_name,
            )
            await try_fill(
                [
                    "input#email",
                    "input[name='job_application[email]']",
                    "input[type='email']",
                ],
                profile.email,
            )
            await try_fill(
                [
                    "input#phone",
                    "input[name='job_application[phone]']",
                    "input[type='tel']",
                ],
                profile.phone,
            )

            # Resume upload
            await try_upload(
                [
                    "input#resume",
                    "input[name='job_application[resume]']",
                    "input[type='file']",
                ],
                resume.file_path,
            )

            # Optional cover letter (some forms accept text)
            if cover_letter:
                await try_fill(
                    [
                        "textarea#cover_letter_text",
                        "textarea[name='job_application[cover_letter]']",
                        "textarea[name*='cover' i]",
                    ],
                    cover_letter,
                )

            if await detect_captcha():
                screenshot_path = f"/tmp/greenhouse_captcha_{job.id}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message="CAPTCHA detected; manual completion required.",
                    screenshot_path=screenshot_path,
                    external_url=job.url,
                )

            if not auto_submit:
                screenshot_path = f"/tmp/greenhouse_review_{job.id}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message="Greenhouse application filled; ready for review.",
                    screenshot_path=screenshot_path,
                    external_url=job.url,
                )

            # Submit
            submitted = False
            for sel in [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text(\"Submit\")",
                "button:has-text(\"Apply\")",
            ]:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible() and await btn.is_enabled():
                        await btn.click()
                        await asyncio.sleep(3)
                        submitted = True
                        break
                except Exception:
                    continue

            if not submitted:
                screenshot_path = f"/tmp/greenhouse_submit_missing_{job.id}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message="Submit button not found/clickable.",
                    screenshot_path=screenshot_path,
                    external_url=job.url,
                )

            # Verify submission (best-effort)
            content = (await page.content()).lower()
            if "thank you" in content or "application submitted" in content:
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message="Application submitted",
                    submitted_at=datetime.now(),
                )

            screenshot_path = f"/tmp/greenhouse_post_submit_{job.id}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Submitted, but confirmation not detected. Please verify.",
                screenshot_path=screenshot_path,
                external_url=job.url,
            )
        except Exception as e:
            screenshot_path = screenshot_path or f"/tmp/greenhouse_error_{job.id}.png"
            try:
                await page.screenshot(path=screenshot_path, full_page=True)
            except Exception:
                pass
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Greenhouse apply failed: {e}",
                screenshot_path=screenshot_path,
                external_url=job.url,
                error=str(e),
            )
        finally:
            try:
                await self.browser_manager.close_session(session.session_id)
            except Exception:
                pass


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
