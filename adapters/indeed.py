"""
Indeed Platform Adapter
Handles job search and Easy Apply on Indeed.
"""

import asyncio
import random
import urllib.parse
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


class IndeedAdapter(JobPlatformAdapter):
    """
    Indeed job platform adapter with Easy Apply support.
    Uses BrowserBase for stealth browsing.
    """
    
    platform = PlatformType.INDEED
    BASE_URL = "https://www.indeed.com/jobs"
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search Indeed for jobs matching criteria."""
        session = await self.get_session()
        page = session.page
        
        # Build search URL
        params = {
            "q": " ".join(criteria.roles),
            "l": criteria.locations[0] if criteria.locations else "United States",
        }
        
        # Date posted filter
        if criteria.posted_within_days <= 1:
            params["fromage"] = "1"
        elif criteria.posted_within_days <= 3:
            params["fromage"] = "3"
        elif criteria.posted_within_days <= 7:
            params["fromage"] = "7"
        elif criteria.posted_within_days <= 14:
            params["fromage"] = "14"
        
        # Remote filter
        if "remote" in [loc.lower() for loc in criteria.locations]:
            params["remotejob"] = "032b3046-06a3-4876-8dfd-474eb5e7ed11"
        
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        print(f"📄 Searching Indeed: {url}")
        
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.wait_for_cloudflare(page)
        await self.browser_manager.human_like_delay(3, 5)
        
        jobs = []
        pages_scraped = 0
        max_pages = 3
        
        while pages_scraped < max_pages:
            # Scroll to load content
            for _ in range(3):
                await self.browser_manager.human_like_scroll(page, "down")
            
            # Extract job cards
            new_jobs = await self._extract_job_cards(page)
            jobs.extend(new_jobs)
            print(f"   Found {len(new_jobs)} jobs on page {pages_scraped + 1}")
            
            # Next page
            next_link = page.locator('a[data-testid="pagination-page-next"]').first
            if await next_link.count() > 0:
                await self.browser_manager.human_like_click(page, 'a[data-testid="pagination-page-next"]')
                await self.browser_manager.human_like_delay(2, 4)
                pages_scraped += 1
            else:
                break
        
        # Score and filter
        scored_jobs = [(job, self._score_job_fit(job, criteria)) for job in jobs]
        scored_jobs = [(j, s) for j, s in scored_jobs if s >= 0.5]
        scored_jobs.sort(key=lambda x: x[1], reverse=True)
        
        return [job for job, _ in scored_jobs]
    
    async def _extract_job_cards(self, page) -> List[JobPosting]:
        """Extract job postings from Indeed search results."""
        jobs = []
        
        # Try multiple card selectors - Indeed changes these frequently
        card_selectors = [
            '.mosaic-provider-jobcards .slider_item',
            '.job_seen_beacon',
            'div[data-testid="job-card"]',
            '.resultContent',
            'li[data-resultid]',
        ]
        
        cards = []
        for selector in card_selectors:
            cards = await page.locator(selector).all()
            if cards:
                print(f"   Using selector: {selector} ({len(cards)} cards)")
                break
        
        if not cards:
            # Fallback: try to find job links directly
            job_links = await page.locator('a[data-jk]').all()
            print(f"   Fallback: found {len(job_links)} job links")
            
            for link in job_links[:20]:  # Limit to 20
                try:
                    href = await link.get_attribute('href')
                    jk = await link.get_attribute('data-jk')
                    title = await link.inner_text()
                    
                    if href and title:
                        if not href.startswith('http'):
                            href = f"https://www.indeed.com{href}"
                        
                        jobs.append(JobPosting(
                            id=jk or f"indeed-{len(jobs)}",
                            platform=self.platform,
                            title=title.strip(),
                            company="(see details)",
                            location="",
                            url=href,
                            easy_apply=False,
                            remote=False
                        ))
                except Exception as e:
                    print(f"   Link extraction error: {e}")
                    continue
            
            return jobs
        
        for card in cards:
            try:
                # Job title - try multiple selectors
                title = ""
                title_selectors = [
                    'h2 span[title]',
                    'h2 a span',
                    'h2 span',
                    'h2 a',
                    '[data-testid="jobTitle"]',
                    '.jobTitle',
                    'a[data-jk] span',
                ]
                for sel in title_selectors:
                    title_el = card.locator(sel).first
                    if await title_el.count() > 0:
                        title = await title_el.inner_text()
                        if title:
                            break
                
                # Company - try multiple selectors
                company = ""
                company_selectors = [
                    '[data-testid="company-name"]',
                    '.companyName',
                    'span.css-63koeb',
                    'span[data-testid="company-name"]',
                ]
                for sel in company_selectors:
                    comp_el = card.locator(sel).first
                    if await comp_el.count() > 0:
                        company = await comp_el.inner_text()
                        if company:
                            break
                
                # Location
                location = ""
                loc_selectors = [
                    '[data-testid="text-location"]',
                    '.companyLocation',
                    'div[data-testid="text-location"]',
                ]
                for sel in loc_selectors:
                    loc_el = card.locator(sel).first
                    if await loc_el.count() > 0:
                        location = await loc_el.inner_text()
                        if location:
                            break
                
                # URL - find job link
                href = ""
                link = card.locator('a[data-jk], a[href*="/rc/clk"], a[href*="/viewjob"]').first
                if await link.count() > 0:
                    href = await link.get_attribute('href')
                else:
                    # Try any link in the card
                    link = card.locator('a').first
                    if await link.count() > 0:
                        href = await link.get_attribute('href')
                
                if href and not href.startswith('http'):
                    href = f"https://www.indeed.com{href}"
                
                # Easy Apply check
                easy_apply = await card.locator('span:has-text("Easily apply"), .iaLabel').count() > 0
                
                # Extract job key from URL or data attribute
                jk = ""
                jk_el = card.locator('a[data-jk]').first
                if await jk_el.count() > 0:
                    jk = await jk_el.get_attribute('data-jk') or ""
                if not jk and 'jk=' in href:
                    jk = href.split('jk=')[1].split('&')[0]
                
                if title:  # Only require title, company might be missing
                    jobs.append(JobPosting(
                        id=jk or f"{title}-{company}"[:50],
                        platform=self.platform,
                        title=title.strip(),
                        company=company.strip() if company else "(company hidden)",
                        location=location.strip() if location else "",
                        url=href,
                        easy_apply=easy_apply,
                        remote="remote" in location.lower() if location else False
                    ))
            except Exception as e:
                print(f"   Card extraction error: {e}")
                continue
        
        return jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details from Indeed job page."""
        session = await self.get_session()
        page = session.page
        
        await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)
        
        # Extract details
        title = ""
        company = ""
        description = ""
        
        title_el = page.locator('[data-testid="jobsearch-JobInfoHeader-title"], .jobsearch-JobInfoHeader-title').first
        if await title_el.count() > 0:
            title = await title_el.inner_text()
        
        company_el = page.locator('[data-testid="inlineHeader-companyName"], .jobsearch-InlineCompanyRating-companyHeader').first
        if await company_el.count() > 0:
            company = await company_el.inner_text()
        
        desc_el = page.locator('#jobDescriptionText, .jobsearch-jobDescriptionText').first
        if await desc_el.count() > 0:
            description = await desc_el.inner_text()
        
        easy_apply = await page.locator('#indeedApplyButton, button:has-text("Apply now")').count() > 0
        
        return JobPosting(
            id=job_url.split('jk=')[1].split('&')[0] if 'jk=' in job_url else "unknown",
            platform=self.platform,
            title=title.strip(),
            company=company.strip(),
            location="",
            url=job_url,
            description=description,
            easy_apply=easy_apply
        )
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """Apply to job via Indeed."""
        session = await self.get_session()
        page = session.page
        
        await page.goto(job.url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)
        
        # Find apply button
        apply_btn = page.locator('#indeedApplyButton, button:has-text("Apply now")').first
        
        if await apply_btn.count() == 0:
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message="No direct apply available"
            )
        
        await self.browser_manager.human_like_click(page, '#indeedApplyButton, button:has-text("Apply now")')
        await self.browser_manager.human_like_delay(2, 3)
        
        # Handle application form
        max_steps = 8
        current_step = 0
        
        while current_step < max_steps:
            # Detect form step
            content = await page.content()
            
            # Contact info
            name_input = page.locator('input[name="name"], input[id*="name"]').first
            if await name_input.count() > 0:
                await name_input.fill(f"{profile.first_name} {profile.last_name}")
            
            email_input = page.locator('input[name="email"], input[type="email"]').first
            if await email_input.count() > 0:
                await email_input.fill(profile.email)
            
            phone_input = page.locator('input[name="phone"], input[type="tel"]').first
            if await phone_input.count() > 0:
                await phone_input.fill(profile.phone)
            
            # Resume upload
            file_input = page.locator('input[type="file"]').first
            if await file_input.count() > 0:
                await file_input.set_input_files(resume.file_path)
                await self.browser_manager.human_like_delay(1, 2)
            
            # Cover letter
            cover_textarea = page.locator('textarea[name*="cover"], textarea[id*="cover"]').first
            if await cover_textarea.count() > 0 and cover_letter:
                await cover_textarea.fill(cover_letter)
            
            # Check for submit/review
            if "review" in content.lower() or "submit" in content.lower():
                if not auto_submit:
                    screenshot_path = f"/tmp/indeed_review_{job.id}.png"
                    await page.screenshot(path=screenshot_path)
                    return ApplicationResult(
                        status=ApplicationStatus.PENDING_REVIEW,
                        message="Ready for review",
                        screenshot_path=screenshot_path
                    )
                
                submit_btn = page.locator('button:has-text("Submit"), button[type="submit"]').first
                if await submit_btn.count() > 0:
                    await self.browser_manager.human_like_click(page, 'button:has-text("Submit")')
                    return ApplicationResult(
                        status=ApplicationStatus.SUBMITTED,
                        submitted_at=datetime.now()
                    )
            
            # Continue button
            continue_btn = page.locator('button:has-text("Continue"), button:has-text("Next")').first
            if await continue_btn.count() > 0:
                await self.browser_manager.human_like_click(page, 'button:has-text("Continue")')
                await self.browser_manager.human_like_delay(1, 2)
            else:
                break
            
            current_step += 1
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Could not complete application flow"
        )
