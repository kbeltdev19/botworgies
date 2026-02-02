"""
LinkedIn Jobs Platform Adapter
Handles search, job details, and Easy Apply automation.
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


class LinkedInAdapter(JobPlatformAdapter):
    """
    LinkedIn Jobs adapter with Easy Apply support.
    """
    
    platform = PlatformType.LINKEDIN
    BASE_URL = "https://www.linkedin.com/jobs/search"
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """
        Search LinkedIn for jobs matching criteria.
        """
        session = await self.get_session()
        page = session.page
        
        # Build search URL
        location = criteria.locations[0] if criteria.locations else "United States"
        params = {
            "keywords": " ".join(criteria.roles),
            "location": location,
        }
        
        # Country/GeoId filter for more accurate results
        # LinkedIn geoIds: US=103644278, CA=101174742, GB=101165590, DE=101282230
        country = getattr(criteria, 'country', 'US')
        if country == 'US' or 'united states' in location.lower():
            params["geoId"] = "103644278"
        elif country == 'CA' or 'canada' in location.lower():
            params["geoId"] = "101174742"
        elif country == 'GB' or 'united kingdom' in location.lower():
            params["geoId"] = "101165590"
        elif country == 'DE' or 'germany' in location.lower():
            params["geoId"] = "101282230"
        
        # Time posted filter
        if criteria.posted_within_days <= 1:
            params["f_TPR"] = "r86400"  # Past 24 hours
        elif criteria.posted_within_days <= 7:
            params["f_TPR"] = "r604800"  # Past week
        elif criteria.posted_within_days <= 30:
            params["f_TPR"] = "r2592000"  # Past month
        
        # Remote filter
        if "remote" in [loc.lower() for loc in criteria.locations]:
            params["f_WT"] = "2"
        
        # Easy apply filter
        if criteria.easy_apply_only:
            params["f_AL"] = "true"
        
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        print(f"📄 Searching LinkedIn: {url}")
        
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.wait_for_cloudflare(page)
        await self.browser_manager.human_like_delay(2, 4)
        
        jobs = []
        pages_scraped = 0
        max_pages = 5
        
        while pages_scraped < max_pages:
            # Scroll to load lazy content
            for _ in range(3):
                await self.browser_manager.human_like_scroll(page, "down")
            
            # Extract job cards
            new_jobs = await self._extract_job_cards(page)
            jobs.extend(new_jobs)
            print(f"   Found {len(new_jobs)} jobs on page {pages_scraped + 1}")
            
            # Try to go to next page
            next_btn = page.locator("button[aria-label='View next page']").first
            if await next_btn.count() > 0 and await next_btn.is_visible():
                await self.browser_manager.human_like_click(page, "button[aria-label='View next page']")
                await self.browser_manager.human_like_delay(2, 4)
                pages_scraped += 1
            else:
                break
        
        # Score and filter jobs
        scored_jobs = []
        for job in jobs:
            score = self._score_job_fit(job, criteria)
            if score >= 0.5:  # Only keep decent matches
                scored_jobs.append((job, score))
        
        # Sort by score
        scored_jobs.sort(key=lambda x: x[1], reverse=True)
        
        return [job for job, _ in scored_jobs]
    
    async def _extract_job_cards(self, page) -> List[JobPosting]:
        """Extract job postings from the current page."""
        jobs = []
        
        # LinkedIn uses various selectors depending on logged-in state
        selectors = [
            ".base-card",
            ".job-search-card",
            "[data-job-id]",
            ".jobs-search-results__list-item"
        ]
        
        cards = []
        for selector in selectors:
            found = await page.locator(selector).all()
            if found:
                cards = found
                break
        
        for card in cards:
            try:
                # Extract job details
                title_el = await card.locator("h3, .base-search-card__title").first.inner_text()
                company_el = await card.locator("h4, .base-search-card__subtitle").first.inner_text()
                location_el = await card.locator(".job-search-card__location, .base-search-card__metadata").first.inner_text()
                
                # Get job URL
                link = card.locator("a").first
                href = await link.get_attribute("href") if await link.count() > 0 else ""
                
                # Check for Easy Apply badge
                easy_apply = await card.locator("span:has-text('Easy Apply')").count() > 0
                
                # Generate unique ID from URL or content
                job_id = href.split("?")[0].split("/")[-1] if href else f"{title_el}-{company_el}"[:50]
                
                jobs.append(JobPosting(
                    id=job_id,
                    platform=self.platform,
                    title=title_el.strip(),
                    company=company_el.strip(),
                    location=location_el.strip(),
                    url=href,
                    easy_apply=easy_apply,
                    remote="remote" in location_el.lower()
                ))
                
            except Exception as e:
                # Skip cards that don't have expected structure
                continue
        
        return jobs
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full job details from the job page."""
        session = await self.get_session()
        page = session.page
        
        await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 4)
        
        # Extract details
        title = await page.locator("h1, .job-details-jobs-unified-top-card__job-title").first.inner_text()
        company = await page.locator(".job-details-jobs-unified-top-card__company-name, h4").first.inner_text()
        
        # Get job description
        description_el = page.locator(".jobs-description__content, .description__text").first
        description = await description_el.inner_text() if await description_el.count() > 0 else ""
        
        # Check for Easy Apply
        easy_apply = await page.locator("button:has-text('Easy Apply')").count() > 0
        
        return JobPosting(
            id=job_url.split("/")[-1].split("?")[0],
            platform=self.platform,
            title=title.strip(),
            company=company.strip(),
            location="",  # Would need to extract from page
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
        """
        Apply to job via LinkedIn Easy Apply.
        """
        session = await self.get_session()
        page = session.page
        
        # Navigate to job
        await page.goto(job.url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)
        
        # Check for Easy Apply button
        easy_apply_btn = page.locator("button:has-text('Easy Apply'), button:has-text('Apply')").first
        
        if await easy_apply_btn.count() == 0:
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message="No Easy Apply available - requires external application"
            )
        
        # Check button text to confirm it's Easy Apply
        btn_text = await easy_apply_btn.inner_text()
        if "easy" not in btn_text.lower():
            # Get external link
            apply_link = page.locator("a:has-text('Apply')").first
            external_url = await apply_link.get_attribute("href") if await apply_link.count() > 0 else None
            
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message="External application required",
                external_url=external_url
            )
        
        # Click Easy Apply
        await self.browser_manager.human_like_click(page, "button:has-text('Easy Apply')")
        await self.browser_manager.human_like_delay(1, 2)
        
        # Handle multi-step form
        max_steps = 10
        current_step = 0
        
        while current_step < max_steps:
            step_type = await self._detect_form_step(page)
            print(f"   Step {current_step + 1}: {step_type}")
            
            if step_type == "contact_info":
                await self._fill_contact_info(page, profile)
                
            elif step_type == "resume":
                await self._handle_resume_step(page, resume)
                
            elif step_type == "cover_letter":
                if cover_letter:
                    await self._fill_cover_letter(page, cover_letter)
                    
            elif step_type == "questions":
                await self._answer_questions(page, profile)
                
            elif step_type == "review":
                if not auto_submit:
                    # Take screenshot for review
                    screenshot_path = f"/tmp/application_review_{job.id}.png"
                    await page.screenshot(path=screenshot_path)
                    
                    return ApplicationResult(
                        status=ApplicationStatus.PENDING_REVIEW,
                        message="Application ready for review",
                        screenshot_path=screenshot_path
                    )
                
                # Auto submit
                submit_btn = page.locator("button[aria-label='Submit application'], button:has-text('Submit')").first
                if await submit_btn.count() > 0:
                    await self.browser_manager.human_like_click(page, "button:has-text('Submit')")
                    await self.browser_manager.human_like_delay(2, 3)
                    
                    return ApplicationResult(
                        status=ApplicationStatus.SUBMITTED,
                        message="Application submitted successfully",
                        submitted_at=datetime.now()
                    )
            
            elif step_type == "done":
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message="Application submitted",
                    submitted_at=datetime.now()
                )
            
            # Click Next/Continue
            next_btn = page.locator("button[aria-label='Continue to next step'], button:has-text('Next'), button:has-text('Review')").first
            if await next_btn.count() > 0:
                await self.browser_manager.human_like_click(page, "button:has-text('Next'), button:has-text('Continue'), button:has-text('Review')")
                await self.browser_manager.human_like_delay(1, 2)
            else:
                break
            
            current_step += 1
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Max steps exceeded or form navigation failed"
        )
    
    async def _detect_form_step(self, page) -> str:
        """Detect what type of form step we're on."""
        content = await page.content()
        content_lower = content.lower()
        
        if "submitted" in content_lower or "thank you" in content_lower:
            return "done"
        if "review" in content_lower and "submit" in content_lower:
            return "review"
        if "resume" in content_lower or "cv" in content_lower:
            return "resume"
        if "cover letter" in content_lower:
            return "cover_letter"
        if "phone" in content_lower or "email" in content_lower or "contact" in content_lower:
            return "contact_info"
        if "question" in content_lower or "?" in content_lower:
            return "questions"
        
        return "unknown"
    
    async def _fill_contact_info(self, page, profile: UserProfile):
        """Fill contact information fields."""
        fields = {
            "input[name*='firstName'], input[id*='firstName']": profile.first_name,
            "input[name*='lastName'], input[id*='lastName']": profile.last_name,
            "input[name*='email'], input[type='email']": profile.email,
            "input[name*='phone'], input[type='tel']": profile.phone,
        }
        
        for selector, value in fields.items():
            input_el = page.locator(selector).first
            if await input_el.count() > 0:
                await input_el.clear()
                await self.browser_manager.human_like_type(page, selector, value)
    
    async def _handle_resume_step(self, page, resume: Resume):
        """Handle resume upload step."""
        file_input = page.locator("input[type='file']").first
        if await file_input.count() > 0:
            await file_input.set_input_files(resume.file_path)
            await self.browser_manager.human_like_delay(1, 2)
    
    async def _fill_cover_letter(self, page, cover_letter: str):
        """Fill cover letter text area."""
        textarea = page.locator("textarea[name*='coverLetter'], textarea[id*='coverLetter']").first
        if await textarea.count() > 0:
            await textarea.fill(cover_letter)
    
    async def _answer_questions(self, page, profile: UserProfile):
        """Answer screening questions."""
        # Common yes/no questions
        yes_no_questions = {
            "authorized": profile.work_authorization,
            "sponsorship": profile.sponsorship_required,
            "background check": "Yes",
            "drug test": "Yes",
        }
        
        # Find radio buttons or selects
        for keyword, answer in yes_no_questions.items():
            label = page.locator(f"label:has-text('{keyword}')").first
            if await label.count() > 0:
                # Try to find associated input
                radio = page.locator(f"input[type='radio'][value='{answer}']").first
                if await radio.count() > 0:
                    await radio.click()
        
        # Handle text inputs for years of experience, etc.
        exp_input = page.locator("input[name*='experience'], input[id*='years']").first
        if await exp_input.count() > 0 and profile.years_experience:
            await exp_input.fill(str(profile.years_experience))
