"""
Greenhouse ATS Adapter
Handles applications on Greenhouse-powered job pages (used by Stripe, Airbnb, etc.)
"""

import asyncio
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


class GreenhouseAdapter(JobPlatformAdapter):
    """
    Greenhouse ATS adapter.
    Greenhouse powers careers pages for many tech companies.
    URLs typically look like: https://boards.greenhouse.io/company/jobs/12345
    """
    
    platform = PlatformType.GREENHOUSE
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """
        Greenhouse doesn't have a central job board.
        Search is done via company-specific boards or external search.
        """
        # This adapter is primarily for applying, not searching
        # Use Brave Search to find Greenhouse job postings
        return []
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get job details from a Greenhouse job page."""
        session = await self.get_session()
        page = session.page
        
        await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)
        
        # Extract job details
        title = ""
        company = ""
        location = ""
        description = ""
        
        # Job title
        title_el = page.locator('h1.app-title, .job-title, h1').first
        if await title_el.count() > 0:
            title = await title_el.inner_text()
        
        # Company (usually in URL or page header)
        company_el = page.locator('.company-name, .employer-name').first
        if await company_el.count() > 0:
            company = await company_el.inner_text()
        else:
            # Extract from URL: boards.greenhouse.io/COMPANY/jobs/...
            if 'greenhouse.io/' in job_url:
                parts = job_url.split('greenhouse.io/')[1].split('/')
                company = parts[0].replace('-', ' ').title()
        
        # Location
        loc_el = page.locator('.location, [class*="location"]').first
        if await loc_el.count() > 0:
            location = await loc_el.inner_text()
        
        # Description
        desc_el = page.locator('#content, .job-description, [class*="description"]').first
        if await desc_el.count() > 0:
            description = await desc_el.inner_text()
        
        return JobPosting(
            id=job_url.split('/')[-1],
            platform=self.platform,
            title=title.strip(),
            company=company.strip(),
            location=location.strip(),
            url=job_url,
            description=description[:5000],
            easy_apply=True  # Greenhouse has built-in apply
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
        Apply to a Greenhouse job posting.
        Greenhouse typically has a single-page application form.
        """
        session = await self.get_session()
        page = session.page
        
        await page.goto(job.url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)
        
        # Find apply button if not already on form
        apply_btn = page.locator('a:has-text("Apply"), button:has-text("Apply")').first
        if await apply_btn.count() > 0:
            await self.browser_manager.human_like_click(page, 'a:has-text("Apply")')
            await self.browser_manager.human_like_delay(2, 3)
        
        # Standard Greenhouse form fields
        form_fields = {
            "first_name": ["#first_name", "input[name='first_name']", "input[autocomplete='given-name']"],
            "last_name": ["#last_name", "input[name='last_name']", "input[autocomplete='family-name']"],
            "email": ["#email", "input[name='email']", "input[type='email']"],
            "phone": ["#phone", "input[name='phone']", "input[type='tel']"],
            "resume": ["#resume", "input[name='resume']", "input[type='file'][accept*='pdf']"],
            "cover_letter": ["#cover_letter", "textarea[name*='cover']", "#cover_letter_text"],
            "linkedin": ["input[name*='linkedin']", "input[placeholder*='LinkedIn']"],
        }
        
        # Fill contact info
        for selector in form_fields["first_name"]:
            el = page.locator(selector).first
            if await el.count() > 0:
                await el.fill(profile.first_name)
                break
        
        for selector in form_fields["last_name"]:
            el = page.locator(selector).first
            if await el.count() > 0:
                await el.fill(profile.last_name)
                break
        
        for selector in form_fields["email"]:
            el = page.locator(selector).first
            if await el.count() > 0:
                await el.fill(profile.email)
                break
        
        for selector in form_fields["phone"]:
            el = page.locator(selector).first
            if await el.count() > 0:
                await el.fill(profile.phone)
                break
        
        # LinkedIn URL
        if profile.linkedin_url:
            for selector in form_fields["linkedin"]:
                el = page.locator(selector).first
                if await el.count() > 0:
                    await el.fill(profile.linkedin_url)
                    break
        
        # Resume upload
        for selector in form_fields["resume"]:
            el = page.locator(selector).first
            if await el.count() > 0:
                await el.set_input_files(resume.file_path)
                await self.browser_manager.human_like_delay(1, 2)
                break
        
        # Cover letter
        if cover_letter:
            for selector in form_fields["cover_letter"]:
                el = page.locator(selector).first
                if await el.count() > 0:
                    await el.fill(cover_letter)
                    break
        
        # Handle custom questions (Greenhouse uses data-qa attributes)
        await self._handle_custom_questions(page, resume, profile)
        
        # Review before submit
        if not auto_submit:
            screenshot_path = f"/tmp/greenhouse_review_{job.id}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Application form filled, ready for review",
                screenshot_path=screenshot_path
            )
        
        # Submit
        submit_btn = page.locator('#submit_app, button[type="submit"], input[type="submit"]').first
        if await submit_btn.count() > 0:
            await self.browser_manager.human_like_click(page, '#submit_app, button[type="submit"]')
            await self.browser_manager.human_like_delay(3, 5)
            
            # Check for success
            success_indicators = ['thank you', 'submitted', 'received', 'confirmation']
            content = (await page.content()).lower()
            
            if any(indicator in content for indicator in success_indicators):
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message="Application submitted successfully",
                    submitted_at=datetime.now()
                )
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Could not confirm submission"
        )
    
    async def _handle_custom_questions(self, page, resume: Resume, profile: UserProfile):
        """Handle Greenhouse custom screening questions."""
        
        # Find all question containers
        questions = await page.locator('[data-qa="question"], .field, .application-question').all()
        
        for q in questions:
            try:
                # Get question text
                label = q.locator('label, .field-label').first
                question_text = await label.inner_text() if await label.count() > 0 else ""
                question_lower = question_text.lower()
                
                # Skip if already filled (contact info)
                if any(skip in question_lower for skip in ['first name', 'last name', 'email', 'phone']):
                    continue
                
                # Find input element
                input_el = q.locator('input, textarea, select').first
                if await input_el.count() == 0:
                    continue
                
                tag = await input_el.evaluate('el => el.tagName.toLowerCase()')
                
                # Handle different input types
                if tag == 'select':
                    # Try to select appropriate option
                    if 'authorized' in question_lower or 'legally' in question_lower:
                        await input_el.select_option(label='Yes')
                    elif 'sponsor' in question_lower:
                        await input_el.select_option(label='No')
                    elif 'experience' in question_lower or 'years' in question_lower:
                        if profile.years_experience:
                            # Try to match years
                            options = await input_el.locator('option').all_inner_texts()
                            for opt in options:
                                if str(profile.years_experience) in opt:
                                    await input_el.select_option(label=opt)
                                    break
                
                elif tag == 'input':
                    input_type = await input_el.get_attribute('type') or 'text'
                    
                    if input_type == 'radio' or input_type == 'checkbox':
                        # Yes/No questions
                        if 'authorized' in question_lower:
                            yes_option = q.locator('input[value="Yes"], input[value="true"]').first
                            if await yes_option.count() > 0:
                                await yes_option.click()
                        elif 'sponsor' in question_lower:
                            no_option = q.locator('input[value="No"], input[value="false"]').first
                            if await no_option.count() > 0:
                                await no_option.click()
                    
                    elif input_type == 'text' or input_type == 'number':
                        # Check for pre-configured answers
                        if profile.custom_answers:
                            for key, answer in profile.custom_answers.items():
                                if key.lower() in question_lower:
                                    await input_el.fill(str(answer))
                                    break
                
                elif tag == 'textarea':
                    # Longer text responses - would use AI here
                    pass
                    
            except Exception as e:
                continue
