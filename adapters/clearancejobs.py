"""
ClearanceJobs Platform Adapter
Handles job search and applications on ClearanceJobs.com
Many jobs link to external application sites (Workday, iCIMS, Taleo, etc.)
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


class ClearanceJobsAdapter(JobPlatformAdapter):
    """
    ClearanceJobs adapter for security-cleared job positions.
    Supports search and handles external application redirects.
    """

    platform = PlatformType.CLEARANCEJOBS
    BASE_URL = "https://www.clearancejobs.com"
    SEARCH_URL = "https://www.clearancejobs.com/jobs"

    # Clearance level mappings
    CLEARANCE_LEVELS = {
        "none": "",
        "public_trust": "public-trust",
        "secret": "secret",
        "top_secret": "top-secret",
        "ts_sci": "ts-sci",
        "polygraph": "polygraph",
    }

    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search ClearanceJobs for positions matching criteria."""
        session = await self.get_session()
        page = session.page

        # Build search URL with parameters
        params = {}

        # Keywords/roles
        if criteria.roles:
            params["q"] = " ".join(criteria.roles)

        # Location
        if criteria.locations:
            location = criteria.locations[0]
            if location.lower() != "remote":
                params["location"] = location

        # Remote filter
        if "remote" in [loc.lower() for loc in criteria.locations]:
            params["remote"] = "true"

        # Clearance level (if specified in required_keywords)
        for keyword in criteria.required_keywords:
            keyword_lower = keyword.lower().replace(" ", "_").replace("-", "_")
            if keyword_lower in self.CLEARANCE_LEVELS:
                params["clearance"] = self.CLEARANCE_LEVELS[keyword_lower]
                break

        # Date posted filter
        if criteria.posted_within_days <= 1:
            params["posted"] = "1"
        elif criteria.posted_within_days <= 7:
            params["posted"] = "7"
        elif criteria.posted_within_days <= 30:
            params["posted"] = "30"

        url = f"{self.SEARCH_URL}?{urllib.parse.urlencode(params)}" if params else self.SEARCH_URL

        self._log(f"Searching ClearanceJobs: {url}")

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.wait_for_cloudflare(page)
        await self.browser_manager.human_like_delay(2, 4)

        jobs = []
        pages_scraped = 0
        max_pages = min(getattr(criteria, 'max_pages', 3), 5)

        while pages_scraped < max_pages:
            # Scroll to load content
            for _ in range(3):
                await self.browser_manager.human_like_scroll(page, "down")

            # Extract job cards
            new_jobs = await self._extract_job_cards(page)
            jobs.extend(new_jobs)
            self._log(f"Found {len(new_jobs)} jobs on page {pages_scraped + 1}")

            # Try next page
            next_btn = page.locator('a.pagination-next, a[rel="next"], button:has-text("Next")').first
            if await next_btn.count() > 0 and await next_btn.is_visible():
                try:
                    await self.browser_manager.human_like_click(page, 'a.pagination-next, a[rel="next"]')
                    await self.browser_manager.human_like_delay(2, 4)
                    pages_scraped += 1
                except Exception:
                    break
            else:
                break

        # Score and filter jobs
        scored_jobs = [(job, self._score_job_fit(job, criteria)) for job in jobs]
        scored_jobs = [(j, s) for j, s in scored_jobs if s >= 0.4]  # Lower threshold for clearance jobs
        scored_jobs.sort(key=lambda x: x[1], reverse=True)

        return [job for job, _ in scored_jobs]

    async def _extract_job_cards(self, page) -> List[JobPosting]:
        """Extract job postings from ClearanceJobs search results."""
        jobs = []

        # ClearanceJobs job card selectors
        cards = await page.locator('.job-listing, .job-card, [data-job-id], article.job').all()

        for card in cards:
            try:
                # Job title
                title_el = card.locator('h2 a, .job-title a, .job-title, h3 a').first
                title = await title_el.inner_text() if await title_el.count() > 0 else ""

                # Company
                company_el = card.locator('.company-name, .employer-name, .job-company').first
                company = await company_el.inner_text() if await company_el.count() > 0 else ""

                # Location
                loc_el = card.locator('.job-location, .location, [class*="location"]').first
                location = await loc_el.inner_text() if await loc_el.count() > 0 else ""

                # URL
                link = card.locator('a[href*="/job/"], h2 a, .job-title a').first
                href = await link.get_attribute('href') if await link.count() > 0 else ""
                if href and not href.startswith('http'):
                    href = f"{self.BASE_URL}{href}"

                # Clearance level
                clearance_el = card.locator('.clearance, .clearance-level, [class*="clearance"]').first
                clearance = await clearance_el.inner_text() if await clearance_el.count() > 0 else ""

                # Check for external application
                external_indicator = await card.locator('text=External, text=Apply on company site').count() > 0

                # Remote check
                is_remote = "remote" in location.lower() or await card.locator('text=Remote, .remote-badge').count() > 0

                if title and company:
                    job_id = href.split('/job/')[-1].split('/')[0] if '/job/' in href else f"{title}-{company}"[:50]

                    jobs.append(JobPosting(
                        id=job_id,
                        platform=self.platform,
                        title=title.strip(),
                        company=company.strip(),
                        location=location.strip(),
                        url=href,
                        easy_apply=not external_indicator,  # True if NOT external
                        remote=is_remote,
                        requirements=clearance if clearance else None,
                    ))
            except Exception as e:
                self._log(f"Error extracting job card: {e}", level="debug")
                continue

        return jobs

    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details from ClearanceJobs job page."""
        session = await self.get_session()
        page = session.page

        await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)

        # Extract details
        title = ""
        company = ""
        location = ""
        description = ""
        clearance = ""
        external_url = None

        # Title
        title_el = page.locator('h1.job-title, h1, .job-header h1').first
        if await title_el.count() > 0:
            title = await title_el.inner_text()

        # Company
        company_el = page.locator('.company-name, .employer-name, [class*="company"]').first
        if await company_el.count() > 0:
            company = await company_el.inner_text()

        # Location
        loc_el = page.locator('.job-location, .location').first
        if await loc_el.count() > 0:
            location = await loc_el.inner_text()

        # Description
        desc_el = page.locator('.job-description, .description, #job-description').first
        if await desc_el.count() > 0:
            description = await desc_el.inner_text()

        # Clearance requirement
        clearance_el = page.locator('.clearance-required, .clearance-level, [class*="clearance"]').first
        if await clearance_el.count() > 0:
            clearance = await clearance_el.inner_text()

        # Check for external application link
        external_link = page.locator('a:has-text("Apply on company site"), a:has-text("External Apply"), a[href*="redirect"], a.external-apply').first
        if await external_link.count() > 0:
            external_url = await external_link.get_attribute('href')

        # Check for direct apply button
        easy_apply = await page.locator('button:has-text("Quick Apply"), button:has-text("Easy Apply"), form.apply-form').count() > 0

        return JobPosting(
            id=job_url.split('/job/')[-1].split('/')[0] if '/job/' in job_url else "unknown",
            platform=self.platform,
            title=title.strip(),
            company=company.strip(),
            location=location.strip(),
            url=job_url,
            description=description,
            requirements=clearance,
            easy_apply=easy_apply,
            external_apply_url=external_url,
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
        """Apply to job via ClearanceJobs or redirect to external site."""
        session = await self.get_session()
        page = session.page

        await page.goto(job.url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)

        # Check for external application redirect
        external_link = page.locator('a:has-text("Apply on company site"), a:has-text("External Apply"), a.external-apply').first

        if await external_link.count() > 0:
            external_url = await external_link.get_attribute('href')
            self._log(f"External application detected: {external_url}")

            # Navigate to external site
            await self.browser_manager.human_like_click(page, 'a:has-text("Apply on company site"), a:has-text("External Apply")')
            await self.browser_manager.human_like_delay(3, 5)

            # Get current URL after redirect
            current_url = page.url

            # Detect external platform
            external_platform = self._detect_external_platform(current_url)

            if external_platform:
                # Handle external platform application
                return await self._apply_on_external_platform(
                    page, external_platform, resume, profile, cover_letter, auto_submit, job
                )
            else:
                # Generic external form handling
                return await self._apply_on_generic_site(
                    page, resume, profile, cover_letter, auto_submit, job
                )

        # Direct ClearanceJobs application
        apply_btn = page.locator('button:has-text("Quick Apply"), button:has-text("Apply"), a:has-text("Apply Now")').first

        if await apply_btn.count() == 0:
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message="No direct apply option found",
                external_url=job.url
            )

        await self.browser_manager.human_like_click(page, 'button:has-text("Quick Apply"), button:has-text("Apply")')
        await self.browser_manager.human_like_delay(2, 3)

        # Fill ClearanceJobs application form
        return await self._fill_clearancejobs_form(page, resume, profile, cover_letter, auto_submit, job)

    def _detect_external_platform(self, url: str) -> Optional[str]:
        """Detect which external ATS platform the URL belongs to."""
        url_lower = url.lower()

        platform_patterns = {
            "workday": ["myworkday", "workday.com", "wd5.myworkdayjobs"],
            "icims": ["icims.com", "careers-"],
            "taleo": ["taleo.net", "taleo.com"],
            "greenhouse": ["greenhouse.io", "boards.greenhouse"],
            "lever": ["lever.co", "jobs.lever"],
            "smartrecruiters": ["smartrecruiters.com"],
            "jobvite": ["jobvite.com", "jobs.jobvite"],
            "ultipro": ["ultipro.com"],
            "successfactors": ["successfactors.com", "successfactors.eu"],
            "bamboohr": ["bamboohr.com"],
            "ashbyhq": ["ashbyhq.com", "jobs.ashby"],
            "brassring": ["brassring.com"],
        }

        for platform, patterns in platform_patterns.items():
            if any(pattern in url_lower for pattern in patterns):
                return platform

        return None

    async def _apply_on_external_platform(
        self,
        page,
        platform: str,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str],
        auto_submit: bool,
        job: JobPosting
    ) -> ApplicationResult:
        """Handle application on known external platforms."""
        self._log(f"Applying on external platform: {platform}")

        # Import platform-specific adapters
        try:
            if platform == "workday":
                from .workday import WorkdayAdapter
                adapter = WorkdayAdapter(self.browser_manager, self.session_cookie)
                adapter._session = self._session
                return await adapter.apply_to_job(job, resume, profile, cover_letter, auto_submit)

            elif platform == "greenhouse":
                from .greenhouse import GreenhouseAdapter
                adapter = GreenhouseAdapter(self.browser_manager, self.session_cookie)
                adapter._session = self._session
                return await adapter.apply_to_job(job, resume, profile, cover_letter, auto_submit)

            elif platform == "lever":
                from .lever import LeverAdapter
                adapter = LeverAdapter(self.browser_manager, self.session_cookie)
                adapter._session = self._session
                return await adapter.apply_to_job(job, resume, profile, cover_letter, auto_submit)

            else:
                # Use generic form filler for other platforms
                return await self._apply_on_generic_site(page, resume, profile, cover_letter, auto_submit, job)

        except Exception as e:
            self._log(f"External platform application failed: {e}", level="error")
            return await self._apply_on_generic_site(page, resume, profile, cover_letter, auto_submit, job)

    async def _apply_on_generic_site(
        self,
        page,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str],
        auto_submit: bool,
        job: JobPosting
    ) -> ApplicationResult:
        """Apply using generic form detection and filling."""
        self._log("Using generic form filler for external site")

        max_steps = 10
        current_step = 0

        while current_step < max_steps:
            await self.browser_manager.human_like_delay(1, 2)

            # Look for common form fields and fill them
            filled_any = False

            # Name fields
            for selector in ['input[name*="name" i]', 'input[id*="name" i]', 'input[placeholder*="name" i]']:
                elements = await page.locator(selector).all()
                for el in elements:
                    try:
                        if await el.is_visible() and await el.is_enabled():
                            placeholder = (await el.get_attribute('placeholder') or '').lower()
                            name_attr = (await el.get_attribute('name') or '').lower()

                            if 'first' in placeholder or 'first' in name_attr:
                                await el.fill(profile.first_name)
                                filled_any = True
                            elif 'last' in placeholder or 'last' in name_attr:
                                await el.fill(profile.last_name)
                                filled_any = True
                            elif 'full' in placeholder or 'full' in name_attr:
                                await el.fill(f"{profile.first_name} {profile.last_name}")
                                filled_any = True
                    except Exception:
                        continue

            # Email field
            email_input = page.locator('input[type="email"], input[name*="email" i], input[id*="email" i]').first
            if await email_input.count() > 0:
                try:
                    await email_input.fill(profile.email)
                    filled_any = True
                except Exception:
                    pass

            # Phone field
            phone_input = page.locator('input[type="tel"], input[name*="phone" i], input[id*="phone" i]').first
            if await phone_input.count() > 0:
                try:
                    await phone_input.fill(profile.phone)
                    filled_any = True
                except Exception:
                    pass

            # Resume upload
            file_input = page.locator('input[type="file"]').first
            if await file_input.count() > 0:
                try:
                    await file_input.set_input_files(resume.file_path)
                    filled_any = True
                    await self.browser_manager.human_like_delay(1, 2)
                except Exception:
                    pass

            # Cover letter textarea
            if cover_letter:
                cover_textarea = page.locator('textarea[name*="cover" i], textarea[id*="cover" i], textarea[placeholder*="cover" i]').first
                if await cover_textarea.count() > 0:
                    try:
                        await cover_textarea.fill(cover_letter)
                        filled_any = True
                    except Exception:
                        pass

            # LinkedIn URL
            if profile.linkedin_url:
                linkedin_input = page.locator('input[name*="linkedin" i], input[id*="linkedin" i]').first
                if await linkedin_input.count() > 0:
                    try:
                        await linkedin_input.fill(profile.linkedin_url)
                        filled_any = True
                    except Exception:
                        pass

            # Check if we've reached a review/submit page
            content = await page.content()
            content_lower = content.lower()

            if 'review' in content_lower or 'confirm' in content_lower or 'submit' in content_lower:
                if not auto_submit:
                    screenshot_path = f"/tmp/external_review_{job.id}.png"
                    await page.screenshot(path=screenshot_path)
                    return ApplicationResult(
                        status=ApplicationStatus.PENDING_REVIEW,
                        message="External application ready for review",
                        screenshot_path=screenshot_path,
                        external_url=page.url
                    )

                # Auto submit
                submit_btn = page.locator('button:has-text("Submit"), button[type="submit"], input[type="submit"]').first
                if await submit_btn.count() > 0:
                    await self.browser_manager.human_like_click(page, 'button:has-text("Submit")')
                    await self.browser_manager.human_like_delay(2, 3)

                    return ApplicationResult(
                        status=ApplicationStatus.SUBMITTED,
                        message="Application submitted on external site",
                        submitted_at=datetime.now()
                    )

            # Look for continue/next button
            next_btn = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Save"), a:has-text("Next")').first
            if await next_btn.count() > 0:
                try:
                    await self.browser_manager.human_like_click(page, 'button:has-text("Continue"), button:has-text("Next")')
                    await self.browser_manager.human_like_delay(2, 3)
                    current_step += 1
                    continue
                except Exception:
                    pass

            if not filled_any:
                # No fields filled and no next button - we might be stuck
                break

            current_step += 1

        # Take screenshot of final state
        screenshot_path = f"/tmp/external_final_{job.id}.png"
        await page.screenshot(path=screenshot_path)

        return ApplicationResult(
            status=ApplicationStatus.PENDING_REVIEW,
            message="External application form partially completed - manual review required",
            screenshot_path=screenshot_path,
            external_url=page.url
        )

    async def _fill_clearancejobs_form(
        self,
        page,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str],
        auto_submit: bool,
        job: JobPosting
    ) -> ApplicationResult:
        """Fill ClearanceJobs' native application form."""
        max_steps = 8
        current_step = 0

        while current_step < max_steps:
            await self.browser_manager.human_like_delay(1, 2)

            # Name fields
            first_name = page.locator('input[name*="first" i], input[id*="first" i]').first
            if await first_name.count() > 0:
                await first_name.fill(profile.first_name)

            last_name = page.locator('input[name*="last" i], input[id*="last" i]').first
            if await last_name.count() > 0:
                await last_name.fill(profile.last_name)

            # Email
            email_input = page.locator('input[type="email"], input[name*="email" i]').first
            if await email_input.count() > 0:
                await email_input.fill(profile.email)

            # Phone
            phone_input = page.locator('input[type="tel"], input[name*="phone" i]').first
            if await phone_input.count() > 0:
                await phone_input.fill(profile.phone)

            # Resume upload
            file_input = page.locator('input[type="file"]').first
            if await file_input.count() > 0:
                await file_input.set_input_files(resume.file_path)
                await self.browser_manager.human_like_delay(1, 2)

            # Cover letter
            if cover_letter:
                cover_textarea = page.locator('textarea[name*="cover" i], textarea').first
                if await cover_textarea.count() > 0:
                    await cover_textarea.fill(cover_letter)

            # Clearance-specific questions
            # These often appear on ClearanceJobs
            clearance_select = page.locator('select[name*="clearance" i]').first
            if await clearance_select.count() > 0:
                # Select highest clearance if user has one
                options = await clearance_select.locator('option').all()
                for opt in options:
                    text = await opt.inner_text()
                    if any(level in text.lower() for level in ['ts/sci', 'top secret', 'secret']):
                        await clearance_select.select_option(label=text)
                        break

            # Check for submit
            content = await page.content()
            if 'submit' in content.lower() or 'review' in content.lower():
                if not auto_submit:
                    screenshot_path = f"/tmp/clearancejobs_review_{job.id}.png"
                    await page.screenshot(path=screenshot_path)
                    return ApplicationResult(
                        status=ApplicationStatus.PENDING_REVIEW,
                        message="Ready for review on ClearanceJobs",
                        screenshot_path=screenshot_path
                    )

                submit_btn = page.locator('button:has-text("Submit"), button[type="submit"]').first
                if await submit_btn.count() > 0:
                    await self.browser_manager.human_like_click(page, 'button:has-text("Submit")')
                    return ApplicationResult(
                        status=ApplicationStatus.SUBMITTED,
                        message="Application submitted on ClearanceJobs",
                        submitted_at=datetime.now()
                    )

            # Next/continue button
            next_btn = page.locator('button:has-text("Continue"), button:has-text("Next")').first
            if await next_btn.count() > 0:
                await self.browser_manager.human_like_click(page, 'button:has-text("Continue")')
                await self.browser_manager.human_like_delay(1, 2)
            else:
                break

            current_step += 1

        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Could not complete ClearanceJobs application flow"
        )

    def _log(self, message: str, level: str = "info"):
        """Log a message."""
        prefix = "ClearanceJobs"
        print(f"[{prefix}] {message}")
