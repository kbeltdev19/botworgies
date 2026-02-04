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
        """Apply to job via Indeed with CAPTCHA handling."""
        session = await self.get_session()
        page = session.page
        
        # Navigate to job page with timeout handling
        try:
            await page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            # Try with shorter timeout and less strict wait
            await page.goto(job.url, wait_until="commit", timeout=20000)
        
        await self.browser_manager.human_like_delay(3, 5)
        
        # Handle CAPTCHA if present
        if hasattr(self.browser_manager, 'solve_captcha'):
            captcha_solved = await self.browser_manager.solve_captcha(page)
            if captcha_solved:
                await self.browser_manager.human_like_delay(2, 3)
        
        # Find apply button - try multiple selectors
        apply_selectors = [
            'button#indeedApplyButton',
            'button:has-text("Apply now")',
            'button:has-text("Apply")',
            '.ia-ApplyButton',
            '[data-testid="apply-button"]',
            'button:has-text("Apply Now")',
            '.jobsearch-IndeedApplyButton',
        ]
        
        apply_btn = None
        for selector in apply_selectors:
            btn = page.locator(selector).first
            if await btn.count() > 0 and await btn.is_visible():
                apply_btn = btn
                break
        
        if not apply_btn:
            # Check for external apply link
            external_selectors = [
                'a:has-text("Apply on company site")',
                'a:has-text("Apply on external site")',
                'a[href*="apply"]:not([href*="indeed"])',
                '.jobsearch-ExternalJobLink',
            ]
            
            for selector in external_selectors:
                external_link = page.locator(selector).first
                if await external_link.count() > 0:
                    external_url = await external_link.get_attribute("href")
                    if external_url:
                        # Use external adapter for company site application
                        from .external import ExternalApplicationAdapter
                        external_adapter = ExternalApplicationAdapter(self.browser_manager)
                        job.external_apply_url = external_url
                        
                        return await external_adapter.apply_to_job(
                            job=job,
                            resume=resume,
                            profile=profile,
                            cover_letter=cover_letter,
                            auto_submit=auto_submit
                        )
            
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message="No direct apply available"
            )
        
        # Click apply button
        await apply_btn.click()
        await self.browser_manager.human_like_delay(3, 5)
        
        # Handle CAPTCHA in apply modal if present
        if hasattr(self.browser_manager, 'solve_captcha'):
            captcha_solved = await self.browser_manager.solve_captcha(page)
            if captcha_solved:
                await self.browser_manager.human_like_delay(2, 3)
        
        # Wait for apply modal/iframe to load
        await asyncio.sleep(2)
        
        # Handle application form
        max_steps = 8
        current_step = 0
        
        while current_step < max_steps:
            # Check for CAPTCHA at each step
            if hasattr(self.browser_manager, 'solve_captcha'):
                captcha_solved = await self.browser_manager.solve_captcha(page)
                if captcha_solved:
                    await self.browser_manager.human_like_delay(2, 3)
            
            # Detect form step
            content = await page.content()
            
            # Contact info - try multiple selectors
            name_selectors = [
                'input[name="name"]',
                'input[id*="name" i]',
                'input[placeholder*="name" i]',
                'input[aria-label*="name" i]',
            ]
            for selector in name_selectors:
                name_input = page.locator(selector).first
                if await name_input.count() > 0 and await name_input.is_visible():
                    await name_input.fill(f"{profile.first_name} {profile.last_name}")
                    break
            
            email_selectors = [
                'input[name="email"]',
                'input[type="email"]',
                'input[id*="email" i]',
                'input[placeholder*="email" i]',
            ]
            for selector in email_selectors:
                email_input = page.locator(selector).first
                if await email_input.count() > 0 and await email_input.is_visible():
                    await email_input.fill(profile.email)
                    break
            
            phone_selectors = [
                'input[name="phone"]',
                'input[type="tel"]',
                'input[id*="phone" i]',
                'input[placeholder*="phone" i]',
            ]
            for selector in phone_selectors:
                phone_input = page.locator(selector).first
                if await phone_input.count() > 0 and await phone_input.is_visible():
                    await phone_input.fill(profile.phone)
                    break
            
            # Resume upload
            file_selectors = [
                'input[type="file"]',
                'input[accept*="pdf"]',
                'input[id*="resume" i]',
            ]
            for selector in file_selectors:
                file_input = page.locator(selector).first
                if await file_input.count() > 0 and await file_input.is_visible():
                    await file_input.set_input_files(resume.file_path)
                    await self.browser_manager.human_like_delay(1, 2)
                    break
            
            # Cover letter
            cover_selectors = [
                'textarea[name*="cover" i]',
                'textarea[id*="cover" i]',
                'textarea[placeholder*="cover" i]',
            ]
            for selector in cover_selectors:
                cover_textarea = page.locator(selector).first
                if await cover_textarea.count() > 0 and await cover_textarea.is_visible() and cover_letter:
                    await cover_textarea.fill(cover_letter)
                    break
            
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
                
                # Try multiple submit button patterns
                submit_patterns = [
                    'button:has-text("Submit")',
                    'button:has-text("Submit application")',
                    'button:has-text("Send")',
                    'button:has-text("Apply")',
                    'button[type="submit"]',
                    '[data-testid="apply-button"]',
                    'button:has-text("Done")',
                    '.ia-SubmitButton',
                    'button:has-text("Complete")',
                ]
                
                for pattern in submit_patterns:
                    btn = page.locator(pattern).first
                    try:
                        if await btn.count() > 0 and await btn.is_visible():
                            await btn.click(timeout=10000)
                            await self.browser_manager.human_like_delay(3, 5)
                            
                            # VALIDATION: Check if submission was successful
                            from .validation import SubmissionValidator
                            validation_result = await SubmissionValidator.validate(
                                page, job.id, platform="indeed"
                            )
                            if validation_result['success']:
                                return ApplicationResult(
                                    status=ApplicationStatus.SUBMITTED,
                                    submitted_at=datetime.now(),
                                    confirmation_id=validation_result.get('confirmation_id'),
                                    screenshot_path=validation_result.get('screenshot_path'),
                                    message=validation_result.get('message', 'Application submitted successfully')
                                )
                            else:
                                return ApplicationResult(
                                    status=ApplicationStatus.ERROR,
                                    message=f"Submission validation failed: {validation_result.get('message')}",
                                    screenshot_path=validation_result.get('screenshot_path')
                                )
                    except Exception as e:
                        continue
            
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
