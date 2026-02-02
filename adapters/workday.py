"""
Workday ATS Adapter
Handles applications on Workday-powered career sites.
Workday is complex - heavy JavaScript, multi-step wizards, anti-bot measures.
"""

import asyncio
import re
from typing import List, Optional
from datetime import datetime

from .base import (
    JobPlatformAdapter, PlatformType, JobPosting, ApplicationResult,
    ApplicationStatus, SearchConfig, UserProfile, Resume
)


class WorkdayAdapter(JobPlatformAdapter):
    """
    Workday ATS adapter.
    Workday powers career sites for many large enterprises.
    URLs typically look like: https://company.wd5.myworkdayjobs.com/en-US/External/job/...
    
    Workday is challenging because:
    - Heavy React/JavaScript rendering
    - Account creation often required
    - Multi-page wizard with nested forms
    - Date pickers and complex inputs
    - EEO/voluntary self-identification questions
    """
    
    platform = PlatformType.WORKDAY
    
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """
        Workday doesn't have central search.
        Each company has their own Workday instance.
        Use Brave Search to find Workday job postings.
        """
        return []
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get job details from a Workday job page."""
        session = await self.get_session()
        page = session.page
        
        await page.goto(job_url, wait_until="networkidle", timeout=60000)
        await self.browser_manager.human_like_delay(3, 5)
        
        # Workday pages are heavily JS-rendered, need to wait
        await page.wait_for_selector('[data-automation-id="jobTitle"], h1, .css-1q2dra3', timeout=10000)
        
        title = ""
        company = ""
        location = ""
        description = ""
        
        # Job title - Workday uses data-automation-id
        title_el = page.locator('[data-automation-id="jobTitle"], h1').first
        if await title_el.count() > 0:
            title = await title_el.inner_text()
        
        # Company - extract from URL or page
        # URL format: company.wd5.myworkdayjobs.com
        match = re.search(r'([\w-]+)\.wd\d+\.myworkdayjobs\.com', job_url)
        if match:
            company = match.group(1).replace('-', ' ').title()
        
        # Location
        loc_el = page.locator('[data-automation-id="locations"], [data-automation-id="location"]').first
        if await loc_el.count() > 0:
            location = await loc_el.inner_text()
        
        # Description
        desc_el = page.locator('[data-automation-id="jobDescription"], .css-cygeeu').first
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
            easy_apply=False  # Workday usually requires account
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
        Apply to a Workday job posting.
        This is a complex multi-step process.
        """
        session = await self.get_session()
        page = session.page
        
        await page.goto(job.url, wait_until="networkidle", timeout=60000)
        await self.browser_manager.human_like_delay(3, 5)
        
        # Find Apply button
        apply_btn = page.locator('[data-automation-id="jobApplyButton"], button:has-text("Apply")').first
        
        if await apply_btn.count() == 0:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Apply button not found"
            )
        
        await self.browser_manager.human_like_click(page, '[data-automation-id="jobApplyButton"]')
        await self.browser_manager.human_like_delay(2, 4)
        
        # Check if login/signup required
        login_form = page.locator('[data-automation-id="signInLink"], [data-automation-id="createAccountLink"]').first
        if await login_form.count() > 0:
            # Need to create account or login
            return ApplicationResult(
                status=ApplicationStatus.EXTERNAL_APPLICATION,
                message="Workday requires account creation/login. Please apply manually.",
                external_url=job.url
            )
        
        # Process application wizard steps
        max_steps = 15  # Workday can have many steps
        current_step = 0
        
        while current_step < max_steps:
            await self.browser_manager.human_like_delay(1, 2)
            
            # Detect current step
            step_type = await self._detect_step_type(page)
            print(f"   Workday step {current_step + 1}: {step_type}")
            
            if step_type == "source":
                # "How did you hear about us" - skip or select
                await self._handle_source_step(page)
            
            elif step_type == "my_information":
                await self._handle_personal_info(page, profile)
            
            elif step_type == "my_experience":
                await self._handle_experience(page, resume, profile)
            
            elif step_type == "resume":
                await self._handle_resume_upload(page, resume)
            
            elif step_type == "voluntary_disclosures":
                await self._handle_eeo_questions(page)
            
            elif step_type == "review":
                if not auto_submit:
                    screenshot_path = f"/tmp/workday_review_{job.id}.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    return ApplicationResult(
                        status=ApplicationStatus.PENDING_REVIEW,
                        message="Workday application ready for review",
                        screenshot_path=screenshot_path
                    )
                
                # Submit
                submit_btn = page.locator('[data-automation-id="bottom-navigation-next-button"]:has-text("Submit")').first
                if await submit_btn.count() > 0:
                    await submit_btn.click()
                    await self.browser_manager.human_like_delay(3, 5)
                    
                    return ApplicationResult(
                        status=ApplicationStatus.SUBMITTED,
                        submitted_at=datetime.now()
                    )
            
            elif step_type == "confirmation":
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message="Application submitted",
                    submitted_at=datetime.now()
                )
            
            # Try to advance to next step
            next_btn = page.locator('[data-automation-id="bottom-navigation-next-button"]').first
            if await next_btn.count() > 0 and await next_btn.is_enabled():
                await next_btn.click()
                await self.browser_manager.human_like_delay(2, 4)
            else:
                # Check for errors
                error = page.locator('[data-automation-id="errorMessage"], .error-message').first
                if await error.count() > 0:
                    error_text = await error.inner_text()
                    return ApplicationResult(
                        status=ApplicationStatus.ERROR,
                        message=f"Form validation error: {error_text}"
                    )
                break
            
            current_step += 1
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Max steps exceeded or navigation failed"
        )
    
    async def _detect_step_type(self, page) -> str:
        """Detect what type of Workday wizard step we're on."""
        content = (await page.content()).lower()
        
        # Check data-automation-id attributes
        if await page.locator('[data-automation-id="sourceSection"]').count() > 0:
            return "source"
        if await page.locator('[data-automation-id="myInformationSection"]').count() > 0:
            return "my_information"
        if await page.locator('[data-automation-id="myExperienceSection"]').count() > 0:
            return "my_experience"
        if await page.locator('[data-automation-id="resumeSection"]').count() > 0:
            return "resume"
        if await page.locator('[data-automation-id="voluntaryDisclosuresSection"]').count() > 0:
            return "voluntary_disclosures"
        if await page.locator('[data-automation-id="reviewSection"]').count() > 0:
            return "review"
        if "thank you" in content or "confirmation" in content:
            return "confirmation"
        
        return "unknown"
    
    async def _handle_source_step(self, page):
        """Handle 'How did you hear about us' dropdown."""
        dropdown = page.locator('[data-automation-id="sourceDropdown"], select').first
        if await dropdown.count() > 0:
            try:
                # Try to select "Job Board" or similar
                await dropdown.select_option(index=1)  # Usually first non-empty option
            except:
                pass
    
    async def _handle_personal_info(self, page, profile: UserProfile):
        """Fill personal information fields."""
        fields = {
            'legalNameSection_firstName': profile.first_name,
            'legalNameSection_lastName': profile.last_name,
            'email': profile.email,
            'phone-device-type': profile.phone,
            'addressSection_addressLine1': profile.location,
        }
        
        for field_id, value in fields.items():
            if value:
                input_el = page.locator(f'[data-automation-id="{field_id}"], input[id*="{field_id}"]').first
                if await input_el.count() > 0:
                    await input_el.fill(value)
                    await self.browser_manager.human_like_delay(0.3, 0.7)
    
    async def _handle_experience(self, page, resume: Resume, profile: UserProfile):
        """Handle work experience section - often can skip if resume uploaded."""
        # Check for "Use resume" or "Parse resume" option
        use_resume = page.locator('button:has-text("Use Resume"), button:has-text("Import")').first
        if await use_resume.count() > 0:
            await use_resume.click()
            await self.browser_manager.human_like_delay(2, 3)
    
    async def _handle_resume_upload(self, page, resume: Resume):
        """Upload resume file."""
        file_input = page.locator('[data-automation-id="file-upload-input-ref"], input[type="file"]').first
        if await file_input.count() > 0:
            await file_input.set_input_files(resume.file_path)
            await self.browser_manager.human_like_delay(2, 4)
    
    async def _handle_eeo_questions(self, page):
        """Handle voluntary EEO/self-identification questions."""
        # These are optional - select "Decline to self-identify" when available
        decline_options = await page.locator('input[value*="decline"], input[value*="prefer not"]').all()
        for option in decline_options:
            try:
                await option.click()
            except:
                pass
