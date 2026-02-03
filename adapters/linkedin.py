"""
LinkedIn Adapter - High risk, high reward.

LinkedIn has the most jobs but best anti-bot detection.
Requires li_at session cookie from browser.

WARNING: Use sparingly. High ban risk.
- Max 5 applications per day per account
- Rotate sessions
- Human-like delays
"""

import aiohttp
import asyncio
import random
import json
from typing import List, Optional, Dict
from datetime import datetime
from urllib.parse import quote

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


class LinkedInAdapter(JobPlatformAdapter):
    """
    LinkedIn job search and Easy Apply automation.
    
    Requires authentication via li_at cookie.
    
    Usage:
        adapter = LinkedInAdapter(browser_manager, session_cookie="your_li_at_cookie")
        jobs = await adapter.search_jobs(criteria)
    """
    
    platform = PlatformType.LINKEDIN
    tier = "aggressive"
    
    # Rate limits (conservative to avoid bans)
    MAX_DAILY_APPLICATIONS = 5
    MAX_SEARCHES_PER_HOUR = 10
    COOLDOWN_BETWEEN_ACTIONS = (3, 8)  # seconds
    
    BASE_URL = "https://www.linkedin.com"
    
    def __init__(self, browser_manager=None, session_cookie: str = None):
        super().__init__(browser_manager)
        self.session_cookie = session_cookie
        self._session = None
        self._search_count = 0
        self._application_count = 0
        self._last_action = None
    
    async def _get_session(self):
        """Get authenticated aiohttp session."""
        if not self._session and self.session_cookie:
            cookies = {
                "li_at": self.session_cookie,
                "JSESSIONID": f"ajax:{random.randint(1000000000, 9999999999)}"
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/vnd.linkedin.normalized+json+2.1",
                "X-Restli-Protocol-Version": "2.0.0",
                "X-Li-Lang": "en_US",
                "X-Li-Track": json.dumps({
                    "clientVersion": "1.13.1795",
                    "mpVersion": "1.13.1795",
                    "osName": "web",
                    "timezoneOffset": -8,
                    "deviceFormFactor": "DESKTOP"
                })
            }
            self._session = aiohttp.ClientSession(cookies=cookies, headers=headers)
        return self._session
    
    async def close(self):
        """Close session."""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _human_delay(self):
        """Add human-like delay between actions."""
        delay = random.uniform(*self.COOLDOWN_BETWEEN_ACTIONS)
        await asyncio.sleep(delay)
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """
        Search LinkedIn for jobs.
        
        Note: This uses the Voyager API (private, may break).
        For more reliability, use browser automation.
        """
        if not self.session_cookie:
            raise ValueError("LinkedIn requires li_at session cookie")
        
        session = await self._get_session()
        
        await self._human_delay()
        
        # Build search query
        keywords = quote(" ".join(criteria.roles))
        location = quote(criteria.locations[0] if criteria.locations else "")
        
        # LinkedIn Voyager API (private, reverse-engineered)
        url = f"{self.BASE_URL}/voyager/api/search/dash/clusters"
        params = {
            "decorationId": "com.linkedin.voyager.dash.deco.search.SearchClusterCollection-175",
            "origin": "SWITCH_SEARCH_VERTICAL",
            "q": "all",
            "query": f"(keywords:{keywords},locationUnion:(geoId:103644278))",
            "start": 0,
            "count": 25,
        }
        
        # Add Easy Apply filter
        if criteria.easy_apply_only:
            params["query"] += ",f_AL:true"
        
        jobs = []
        
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 429:
                    print("[LinkedIn] Rate limited!")
                    return []
                
                if resp.status == 401:
                    print("[LinkedIn] Session expired - need new li_at cookie")
                    return []
                
                if resp.status != 200:
                    print(f"[LinkedIn] Search failed: {resp.status}")
                    return []
                
                data = await resp.json()
                
                # Parse response (LinkedIn's API is complex)
                jobs = self._parse_search_results(data)
                
        except Exception as e:
            print(f"[LinkedIn] Search error: {e}")
        
        self._search_count += 1
        print(f"[LinkedIn] Found {len(jobs)} jobs")
        
        return jobs
    
    def _parse_search_results(self, data: dict) -> List[JobPosting]:
        """Parse LinkedIn Voyager API search results."""
        jobs = []
        
        try:
            # Navigate the complex response structure
            included = data.get("included", [])
            
            for item in included:
                # Look for job posting entities
                if item.get("$type") == "com.linkedin.voyager.dash.jobs.JobPosting":
                    try:
                        job_id = item.get("dashEntityUrn", "").split(":")[-1]
                        title = item.get("title", "")
                        company_name = ""
                        location = ""
                        
                        # Extract company from nested structure
                        company_ref = item.get("primaryDescription", {})
                        if company_ref:
                            company_name = company_ref.get("text", "")
                        
                        # Extract location
                        location_ref = item.get("secondaryDescription", {})
                        if location_ref:
                            location = location_ref.get("text", "")
                        
                        # Check for Easy Apply
                        easy_apply = item.get("applyMethod", {}).get("$type", "").endswith("EasyApplyOnlineApplyMethod")
                        
                        if title:
                            jobs.append(JobPosting(
                                id=f"linkedin_{job_id}",
                                platform=self.platform,
                                title=title,
                                company=company_name or "(see posting)",
                                location=location,
                                url=f"{self.BASE_URL}/jobs/view/{job_id}",
                                easy_apply=easy_apply,
                                remote="remote" in location.lower()
                            ))
                    except Exception:
                        continue
                        
        except Exception as e:
            print(f"[LinkedIn] Parse error: {e}")
        
        return jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details (requires browser)."""
        # LinkedIn job details require browser automation
        # The API responses are heavily obfuscated
        
        if not self.browser_manager:
            raise ValueError("Job details require browser_manager")
        
        session = await self.browser_manager.create_stealth_session("linkedin")
        page = session.page
        
        try:
            # Set cookie
            await page.context.add_cookies([{
                "name": "li_at",
                "value": self.session_cookie,
                "domain": ".linkedin.com",
                "path": "/"
            }])
            
            await page.goto(job_url, wait_until="domcontentloaded")
            await self._human_delay()
            
            # Extract details
            title = await page.locator(".job-details-jobs-unified-top-card__job-title").inner_text()
            company = await page.locator(".job-details-jobs-unified-top-card__company-name").inner_text()
            location_el = page.locator(".job-details-jobs-unified-top-card__primary-description-container")
            location = await location_el.inner_text() if await location_el.count() > 0 else ""
            
            desc_el = page.locator(".jobs-description__content")
            description = await desc_el.inner_text() if await desc_el.count() > 0 else ""
            
            # Check for Easy Apply button
            easy_apply = await page.locator(".jobs-apply-button--top-card").count() > 0
            
            return JobPosting(
                id=job_url.split("/")[-1],
                platform=self.platform,
                title=title.strip(),
                company=company.strip(),
                location=location.strip(),
                url=job_url,
                description=description,
                easy_apply=easy_apply,
                remote="remote" in location.lower()
            )
            
        finally:
            await self.browser_manager.close_session(session.session_id)
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        Apply via LinkedIn Easy Apply.
        
        WARNING: High ban risk. Use sparingly.
        """
        if self._application_count >= self.MAX_DAILY_APPLICATIONS:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Daily application limit reached"
            )
        
        if not job.easy_apply:
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message="Not Easy Apply - requires external application",
                external_url=job.url
            )
        
        if not self.browser_manager:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Browser automation required for Easy Apply"
            )
        
        session = await self.browser_manager.create_stealth_session("linkedin")
        page = session.page
        
        try:
            # Set cookie
            await page.context.add_cookies([{
                "name": "li_at",
                "value": self.session_cookie,
                "domain": ".linkedin.com",
                "path": "/"
            }])
            
            await page.goto(job.url, wait_until="networkidle")
            await self._human_delay()
            
            # Click Easy Apply button
            easy_apply_btn = page.locator(".jobs-apply-button--top-card, button:has-text('Easy Apply')")
            if await easy_apply_btn.count() == 0:
                return ApplicationResult(
                    status=ApplicationStatus.EXTERNAL_APPLICATION,
                    message="Easy Apply not available"
                )
            
            await self.browser_manager.human_like_click(page, ".jobs-apply-button--top-card")
            await self._human_delay()
            
            # Handle multi-step form
            max_steps = 10
            for step in range(max_steps):
                # Check for completion
                success = page.locator('[data-test-modal-close-btn], .artdeco-modal__dismiss')
                if await success.count() > 0:
                    self._application_count += 1
                    return ApplicationResult(
                        status=ApplicationStatus.SUBMITTED,
                        message="Application submitted!",
                        submitted_at=datetime.now()
                    )
                
                # Fill contact info if requested
                phone_input = page.locator('input[name="phoneNumber"]')
                if await phone_input.count() > 0:
                    await phone_input.fill(profile.phone)
                
                email_input = page.locator('input[name="email"]')
                if await email_input.count() > 0:
                    await email_input.fill(profile.email)
                
                # Handle resume upload
                file_input = page.locator('input[type="file"]')
                if await file_input.count() > 0:
                    await file_input.set_input_files(resume.file_path)
                    await asyncio.sleep(2)
                
                # Handle additional questions (basic text inputs)
                text_inputs = await page.locator('input[type="text"]:not([name="phoneNumber"]):not([name="email"])').all()
                for inp in text_inputs:
                    if await inp.input_value() == "":
                        # Try to auto-fill based on label
                        await inp.fill(profile.years_experience or "5")
                
                # Check for review/submit vs next
                submit_btn = page.locator('button[aria-label*="Submit"], button:has-text("Submit application")')
                if await submit_btn.count() > 0:
                    if auto_submit:
                        await self.browser_manager.human_like_click(page, 'button[aria-label*="Submit"]')
                        await asyncio.sleep(3)
                        self._application_count += 1
                        return ApplicationResult(
                            status=ApplicationStatus.SUBMITTED,
                            message="Application submitted!",
                            submitted_at=datetime.now()
                        )
                    else:
                        # Screenshot for review
                        screenshot_path = f"/tmp/linkedin_review_{job.id}.png"
                        await page.screenshot(path=screenshot_path)
                        return ApplicationResult(
                            status=ApplicationStatus.PENDING_REVIEW,
                            message="Ready for review",
                            screenshot_path=screenshot_path
                        )
                
                # Click Next
                next_btn = page.locator('button[aria-label*="Continue"], button:has-text("Next")')
                if await next_btn.count() > 0:
                    await self.browser_manager.human_like_click(page, 'button[aria-label*="Continue"]')
                    await self._human_delay()
                else:
                    break
            
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Could not complete application flow"
            )
            
        except Exception as e:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=str(e)
            )
            
        finally:
            await self.browser_manager.close_session(session.session_id)


async def test_linkedin():
    """Test LinkedIn adapter (requires li_at cookie)."""
    import os
    
    li_at = os.environ.get("LINKEDIN_LI_AT")
    if not li_at:
        print("Set LINKEDIN_LI_AT environment variable")
        return
    
    adapter = LinkedInAdapter(session_cookie=li_at)
    
    from .base import SearchConfig
    criteria = SearchConfig(
        roles=["software engineer"],
        locations=["San Francisco"],
        easy_apply_only=True,
        posted_within_days=7
    )
    
    try:
        jobs = await adapter.search_jobs(criteria)
        print(f"Found {len(jobs)} Easy Apply jobs")
        for job in jobs[:5]:
            print(f"  - {job.title} at {job.company}")
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(test_linkedin())
