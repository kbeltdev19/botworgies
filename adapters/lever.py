"""
Lever ATS Adapter
Handles applications on Lever-powered job pages.
Lever is used by many startups and tech companies.
"""

import asyncio
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


class LeverAdapter(JobPlatformAdapter):
    """
    Lever ATS adapter.
    URLs typically look like: https://jobs.lever.co/company/job-id
    Lever has relatively simple single-page forms.
    """
    
    platform = PlatformType.LEVER
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """
        Lever doesn't have central search.
        Use company-specific URLs: https://jobs.lever.co/company
        """
        return []
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get job details from a Lever job page."""
        session = await self.get_session()
        page = session.page
        
        await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)
        
        title = ""
        company = ""
        location = ""
        description = ""
        
        # Job title
        title_el = page.locator('h2, .posting-headline h2').first
        if await title_el.count() > 0:
            title = await title_el.inner_text()
        
        # Company - from URL: jobs.lever.co/COMPANY/...
        if 'lever.co/' in job_url:
            parts = job_url.split('lever.co/')[1].split('/')
            company = parts[0].replace('-', ' ').title()
        
        # Location
        loc_el = page.locator('.location, .posting-categories .workplaceTypes, .commitment').first
        if await loc_el.count() > 0:
            location = await loc_el.inner_text()
        
        # Description
        desc_el = page.locator('.posting-content, [data-qa="job-description"]').first
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
            easy_apply=True
        )
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """Apply to a Lever job posting."""
        session = await self.get_session()
        page = session.page
        
        # Lever apply URLs are usually: job_url/apply
        apply_url = job.url if '/apply' in job.url else f"{job.url}/apply"
        
        await page.goto(apply_url, wait_until="domcontentloaded", timeout=60000)
        await self.browser_manager.human_like_delay(2, 3)
        
        # Fill the application form
        # Lever forms are typically straightforward
        
        # Full name (Lever sometimes uses single name field)
        name_input = page.locator('input[name="name"], input[name="full-name"]').first
        if await name_input.count() > 0:
            await name_input.fill(f"{profile.first_name} {profile.last_name}")
        
        # Email
        email_input = page.locator('input[name="email"], input[type="email"]').first
        if await email_input.count() > 0:
            await email_input.fill(profile.email)
        
        # Phone
        phone_input = page.locator('input[name="phone"], input[type="tel"]').first
        if await phone_input.count() > 0:
            await phone_input.fill(profile.phone)
        
        # Current company
        company_input = page.locator('input[name="org"], input[name="company"]').first
        if await company_input.count() > 0:
            # Get from resume if available
            if resume.parsed_data and resume.parsed_data.get('experience'):
                current_company = resume.parsed_data['experience'][0].get('company', '')
                await company_input.fill(current_company)
        
        # LinkedIn
        linkedin_input = page.locator('input[name*="linkedin"], input[placeholder*="LinkedIn"]').first
        if await linkedin_input.count() > 0 and profile.linkedin_url:
            await linkedin_input.fill(profile.linkedin_url)
        
        # Resume upload
        file_input = page.locator('input[name="resume"], input[type="file"]').first
        if await file_input.count() > 0:
            await file_input.set_input_files(resume.file_path)
            await self.browser_manager.human_like_delay(1, 2)
        
        # Cover letter
        cover_textarea = page.locator('textarea[name*="cover"], textarea[name="comments"]').first
        if await cover_textarea.count() > 0 and cover_letter:
            await cover_textarea.fill(cover_letter)
        
        # Handle any custom questions
        await self._handle_custom_questions(page, profile)
        
        # Review before submit
        if not auto_submit:
            screenshot_path = f"/tmp/lever_review_{job.id}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Lever application ready for review",
                screenshot_path=screenshot_path
            )
        
        # Submit
        submit_btn = page.locator('button[type="submit"], button:has-text("Submit"), .application-submit').first
        if await submit_btn.count() > 0:
            await self.browser_manager.human_like_click(page, 'button[type="submit"]')
            await self.browser_manager.human_like_delay(3, 5)
            
            # Check for success
            content = (await page.content()).lower()
            if 'thank you' in content or 'received' in content or 'submitted' in content:
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message="Application submitted",
                    submitted_at=datetime.now()
                )
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Could not confirm submission"
        )
    
    async def _handle_custom_questions(self, page, profile: UserProfile):
        """Handle Lever custom questions."""
        # Lever uses cards with custom questions
        questions = await page.locator('.application-question, .custom-question').all()
        
        for q in questions:
            try:
                label_el = q.locator('label').first
                if await label_el.count() == 0:
                    continue
                
                question_text = (await label_el.inner_text()).lower()
                
                # Work authorization
                if 'authorized' in question_text or 'legally' in question_text:
                    select = q.locator('select').first
                    if await select.count() > 0:
                        await select.select_option(label='Yes')
                    else:
                        yes_radio = q.locator('input[value="Yes"], input[value="yes"]').first
                        if await yes_radio.count() > 0:
                            await yes_radio.click()
                
                # Sponsorship
                elif 'sponsor' in question_text:
                    select = q.locator('select').first
                    if await select.count() > 0:
                        await select.select_option(label='No')
                    else:
                        no_radio = q.locator('input[value="No"], input[value="no"]').first
                        if await no_radio.count() > 0:
                            await no_radio.click()
                
                # Years of experience
                elif 'years' in question_text or 'experience' in question_text:
                    if profile.years_experience:
                        number_input = q.locator('input[type="number"], input[type="text"]').first
                        if await number_input.count() > 0:
                            await number_input.fill(str(profile.years_experience))
                
                # Use pre-configured answers
                if profile.custom_answers:
                    for key, answer in profile.custom_answers.items():
                        if key.lower() in question_text:
                            text_input = q.locator('input[type="text"], textarea').first
                            if await text_input.count() > 0:
                                await text_input.fill(str(answer))
                            break
                            
            except Exception as e:
                continue
