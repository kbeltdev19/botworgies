"""
Dice Adapter - Tier 4 (Browser Required)
Tech-focused job board. Requires browser automation due to anti-bot measures.
"""

import asyncio
import urllib.parse
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


class DiceAdapter(JobPlatformAdapter):
    """
    Dice.com job platform adapter.
    Tech-focused job board with good volume.
    Requires browser automation.
    """
    
    platform = PlatformType.DICE
    tier = "browser"  # Requires browser
    
    BASE_URL = "https://www.dice.com/jobs"
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search Dice for jobs matching criteria."""
        session = await self.get_session()
        page = session.page
        
        # Build search URL
        params = {
            "q": " ".join(criteria.roles),
            "countryCode": "US",
            "radius": "30",
            "radiusUnit": "mi",
            "page": "1",
            "pageSize": "100",
            "filters.postedDate": "ONE",  # Default to 1 day, adjust based on criteria
        }
        
        # Location handling
        if criteria.locations:
            location = criteria.locations[0]
            if location.lower() == "remote":
                params["filters.isRemote"] = "true"
            else:
                params["location"] = location
        
        # Date posted filter
        if criteria.posted_within_days <= 1:
            params["filters.postedDate"] = "ONE"
        elif criteria.posted_within_days <= 3:
            params["filters.postedDate"] = "THREE"
        elif criteria.posted_within_days <= 7:
            params["filters.postedDate"] = "SEVEN"
        elif criteria.posted_within_days <= 30:
            params["filters.postedDate"] = "THIRTY"
        
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        self._log(f"Searching Dice: {url}")
        
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.wait_for_cloudflare(page)
        await self.browser_manager.human_like_delay(3, 5)
        
        jobs = []
        pages_scraped = 0
        max_pages = min(getattr(criteria, 'max_pages', 5), 10)
        
        while pages_scraped < max_pages:
            # Scroll to load content
            for _ in range(3):
                await self.browser_manager.human_like_scroll(page, "down")
                await self.browser_manager.human_like_delay(0.5, 1)
            
            # Extract job cards
            new_jobs = await self._extract_job_cards(page)
            jobs.extend(new_jobs)
            self._log(f"Found {len(new_jobs)} jobs on page {pages_scraped + 1}")
            
            # Check for next page
            next_btn = page.locator('a[aria-label="next page"], button[aria-label="next page"]').first
            if await next_btn.count() > 0:
                try:
                    is_disabled = await next_btn.is_disabled()
                    if is_disabled:
                        break
                    
                    await self.browser_manager.human_like_click(page, 'a[aria-label="next page"]')
                    await self.browser_manager.human_like_delay(2, 4)
                    pages_scraped += 1
                except Exception:
                    break
            else:
                break
        
        # Score and filter
        scored_jobs = [(job, self._score_job_fit(job, criteria)) for job in jobs]
        scored_jobs = [(j, s) for j, s in scored_jobs if s >= 0.4]
        scored_jobs.sort(key=lambda x: x[1], reverse=True)
        
        return [job for job, _ in scored_jobs]
    
    async def _extract_job_cards(self, page) -> List[JobPosting]:
        """Extract job postings from Dice search results."""
        jobs = []
        
        # Try multiple card selectors
        card_selectors = [
            'dhi-search-card',
            '[data-cy="search-result"]',
            '.search-card',
            '.card',
        ]
        
        cards = []
        for selector in card_selectors:
            cards = await page.locator(selector).all()
            if cards:
                break
        
        if not cards:
            # Fallback: look for job links
            job_links = await page.locator('a[href*="/job-detail/"]').all()
            self._log(f"Fallback: found {len(job_links)} job links")
            
            for link in job_links[:50]:
                try:
                    href = await link.get_attribute('href')
                    title = await link.inner_text()
                    
                    if href and title:
                        if not href.startswith('http'):
                            href = f"https://www.dice.com{href}"
                        
                        jobs.append(JobPosting(
                            id=f"dice_{hash(href)}",
                            platform=self.platform,
                            title=title.strip(),
                            company="(see details)",
                            location="",
                            url=href,
                            easy_apply=False
                        ))
                except Exception as e:
                    self._log(f"Link extraction error: {e}")
                    continue
            
            return jobs
        
        for card in cards:
            try:
                # Job title
                title = ""
                title_selectors = [
                    'a[data-cy="card-title-link"]',
                    '.card-title a',
                    'h5 a',
                    'a[href*="/job-detail/"]',
                ]
                for sel in title_selectors:
                    title_el = card.locator(sel).first
                    if await title_el.count() > 0:
                        title = await title_el.inner_text()
                        if title:
                            break
                
                # Company
                company = ""
                company_selectors = [
                    '[data-cy="company-name"]',
                    '.company-name',
                    '.employer-name',
                ]
                for sel in company_selectors:
                    comp_el = card.locator(sel).first
                    if await comp_el.count() > 0:
                        company = await comp_el.inner_text()
                        if company:
                            break
                
                # Location
                location = ""
                location_selectors = [
                    '[data-cy="search-result-location"]',
                    '.location',
                    '.search-result-location',
                ]
                for sel in location_selectors:
                    loc_el = card.locator(sel).first
                    if await loc_el.count() > 0:
                        location = await loc_el.inner_text()
                        if location:
                            break
                
                # URL
                url = ""
                link = card.locator('a[href*="/job-detail/"]').first
                if await link.count() > 0:
                    href = await link.get_attribute('href')
                    if href:
                        url = href if href.startswith('http') else f"https://www.dice.com{href}"
                
                # Posted date
                posted = ""
                posted_selectors = [
                    '[data-cy="posted-date"]',
                    '.posted-date',
                    '.date-posted',
                ]
                for sel in posted_selectors:
                    posted_el = card.locator(sel).first
                    if await posted_el.count() > 0:
                        posted = await posted_el.inner_text()
                        if posted:
                            break
                
                # Employment type
                job_type = ""
                type_selectors = [
                    '[data-cy="employment-type"]',
                    '.employment-type',
                ]
                for sel in type_selectors:
                    type_el = card.locator(sel).first
                    if await type_el.count() > 0:
                        job_type = await type_el.inner_text()
                        if job_type:
                            break
                
                if title:
                    job_id = f"dice_{hash(url)}" if url else f"dice_{title[:30]}"
                    
                    jobs.append(JobPosting(
                        id=job_id,
                        platform=self.platform,
                        title=title.strip(),
                        company=company.strip() if company else "(see details)",
                        location=location.strip() if location else "",
                        url=url or self.BASE_URL,
                        description=posted,
                        easy_apply=False,
                        remote="remote" in location.lower() if location else False,
                        job_type=job_type.lower() if job_type else "full-time"
                    ))
            except Exception as e:
                self._log(f"Card extraction error: {e}")
                continue
        
        return jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details from Dice job page."""
        session = await self.get_session()
        page = session.page
        
        await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)
        
        # Extract details
        title = ""
        company = ""
        location = ""
        description = ""
        
        # Title
        title_el = page.locator('h1[data-cy="job-title"], h1.job-title, h1').first
        if await title_el.count() > 0:
            title = await title_el.inner_text()
        
        # Company
        company_el = page.locator('[data-cy="company-name"], .company-name, [class*="company"]').first
        if await company_el.count() > 0:
            company = await company_el.inner_text()
        
        # Location
        loc_el = page.locator('[data-cy="location"], .location').first
        if await loc_el.count() > 0:
            location = await loc_el.inner_text()
        
        # Description
        desc_el = page.locator('[data-cy="job-description"], .job-description, #job-description').first
        if await desc_el.count() > 0:
            description = await desc_el.inner_text()
        
        return JobPosting(
            id=f"dice_{hash(job_url)}",
            platform=self.platform,
            title=title.strip(),
            company=company.strip(),
            location=location.strip(),
            url=job_url,
            description=description,
            easy_apply=False,
            remote="remote" in location.lower()
        )
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """Apply to Dice job."""
        session = await self.get_session()
        page = session.page
        
        await page.goto(job.url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)
        
        # Look for apply button
        apply_btn = page.locator('button:has-text("Apply Now"), a:has-text("Apply"), button[data-cy="apply-button"]').first
        
        if await apply_btn.count() == 0:
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message="External application required",
                external_url=job.url
            )
        
        await self.browser_manager.human_like_click(page, 'button:has-text("Apply Now"), a:has-text("Apply")')
        await self.browser_manager.human_like_delay(2, 3)
        
        # Check if redirected to external site
        current_url = page.url
        if "dice.com" not in current_url:
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message=f"Redirected to external application: {current_url}",
                external_url=current_url
            )
        
        # Fill Dice application form (simplified)
        # Dice typically has a multi-step form
        max_steps = 5
        current_step = 0
        
        while current_step < max_steps:
            # Check for login required
            if await page.locator('input[type="email"], input[name="email"]').count() > 1:
                return ApplicationResult(
                    status=ApplicationStatus.EXTERNAL_APPLICATION,
                    message="Login required to apply on Dice",
                    external_url=job.url
                )
            
            # Fill visible form fields
            email_input = page.locator('input[type="email"]').first
            if await email_input.count() > 0:
                await email_input.fill(profile.email)
            
            # Resume upload
            file_input = page.locator('input[type="file"]').first
            if await file_input.count() > 0:
                await file_input.set_input_files(resume.file_path)
                await self.browser_manager.human_like_delay(1, 2)
            
            # Check for submit
            submit_btn = page.locator('button:has-text("Submit"), button[type="submit"]').first
            if await submit_btn.count() > 0:
                if not auto_submit:
                    screenshot_path = f"/tmp/dice_review_{job.id}.png"
                    await page.screenshot(path=screenshot_path)
                    return ApplicationResult(
                        status=ApplicationStatus.PENDING_REVIEW,
                        message="Dice application ready for review",
                        screenshot_path=screenshot_path
                    )
                
                await self.browser_manager.human_like_click(page, 'button:has-text("Submit")')
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message="Application submitted on Dice",
                    submitted_at=datetime.now()
                )
            
            # Next button
            next_btn = page.locator('button:has-text("Next"), button:has-text("Continue")').first
            if await next_btn.count() > 0:
                await self.browser_manager.human_like_click(page, 'button:has-text("Next")')
                await self.browser_manager.human_like_delay(1, 2)
            else:
                break
            
            current_step += 1
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Could not complete Dice application flow"
        )


async def test_dice():
    """Test Dice adapter."""
    from .base import SearchConfig
    from core import UnifiedBrowserManager
    
    browser_manager = UnifiedBrowserManager()
    adapter = DiceAdapter(browser_manager)
    
    criteria = SearchConfig(
        roles=["software engineer"],
        locations=["Remote"],
        posted_within_days=7
    )
    
    try:
        jobs = await adapter.search_jobs(criteria)
        print(f"\nFound {len(jobs)} jobs:")
        for job in jobs[:10]:
            print(f"  - {job.title} at {job.company} ({job.location})")
    finally:
        await adapter.close()
        await browser_manager.close_all()


if __name__ == "__main__":
    asyncio.run(test_dice())
