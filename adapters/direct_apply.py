"""
Direct Apply Handler

Handles job applications on platforms with direct application URLs:
- Greenhouse (boards.greenhouse.io)
- Lever (jobs.lever.co)
- Ashby (jobs.ashbyhq.com)
- SmartRecruiters
- BambooHR

These platforms allow direct navigation to application forms.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from .base import JobPosting, ApplicationResult, ApplicationStatus, UserProfile, Resume

logger = logging.getLogger(__name__)


class DirectApplyHandler:
    """
    Handler for direct-apply platforms.
    Navigates directly to application URL and fills form.
    """
    
    def __init__(self, browser_manager):
        self.browser_manager = browser_manager
        
    async def apply(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        Apply to a job on a direct-apply platform.
        
        Args:
            job: Job posting with direct apply URL
            resume: Resume to upload
            profile: User profile
            auto_submit: Whether to submit or stop for review
            
        Returns:
            ApplicationResult
        """
        platform = self._detect_platform(job.url)
        logger.info(f"📝 Direct apply: {job.title} at {job.company} ({platform})")
        
        # Create browser session
        session = await self.browser_manager.create_stealth_session(platform=platform)
        page = session.page
        
        try:
            # Navigate to job
            logger.info(f"  Navigating to {job.url[:60]}...")
            await page.goto(job.url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)
            
            # Route to platform-specific handler
            if platform == 'greenhouse':
                result = await self._apply_greenhouse(page, job, resume, profile, auto_submit)
            elif platform == 'lever':
                result = await self._apply_lever(page, job, resume, profile, auto_submit)
            elif platform == 'ashby':
                result = await self._apply_ashby(page, job, resume, profile, auto_submit)
            else:
                result = await self._apply_generic(page, job, resume, profile, auto_submit)
                
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")
            result = ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=str(e)[:200]
            )
        finally:
            await self.browser_manager.close_session(session.session_id)
            
        return result
        
    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        url_lower = url.lower()
        if 'greenhouse' in url_lower:
            return 'greenhouse'
        elif 'lever' in url_lower:
            return 'lever'
        elif 'ashby' in url_lower:
            return 'ashby'
        elif 'smartrecruiters' in url_lower:
            return 'smartrecruiters'
        elif 'bamboohr' in url_lower:
            return 'bamboohr'
        return 'unknown'
        
    async def _apply_greenhouse(
        self, page, job: JobPosting, resume: Resume, profile: UserProfile, auto_submit: bool
    ) -> ApplicationResult:
        """Apply to a Greenhouse job."""
        logger.info("  Filling Greenhouse form...")
        
        # Click apply button if present
        apply_btn = page.locator('#apply_button, .apply-button, a:has-text("Apply")').first
        if await apply_btn.count() > 0 and await apply_btn.is_visible():
            await apply_btn.click()
            await asyncio.sleep(2)
        
        # Fill fields
        fields_filled = 0
        if await self._fill_field(page, '#first_name', profile.first_name):
            fields_filled += 1
        if await self._fill_field(page, '#last_name', profile.last_name):
            fields_filled += 1
        if await self._fill_field(page, '#email', profile.email):
            fields_filled += 1
        if await self._fill_field(page, '#phone', profile.phone):
            fields_filled += 1
            
        logger.info(f"    Filled {fields_filled}/4 fields")
        
        # Resume upload
        if resume.file_path and os.path.exists(resume.file_path):
            file_input = page.locator('input[type="file"]').first
            if await file_input.count() > 0:
                await file_input.set_input_files(resume.file_path)
                logger.info("    Resume uploaded")
                await asyncio.sleep(1)
        
        # LinkedIn and portfolio
        await self._fill_field(page, 'input[name*="linkedin"]', profile.linkedin or '')
        await self._fill_field(page, 'input[name*="website"]', profile.portfolio or '')
        
        if not auto_submit:
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Form filled, ready for review"
            )
        
        # Submit
        submit = page.locator('input[type="submit"], #submit_app, button:has-text("Submit")').first
        if await submit.count() > 0 and await submit.is_enabled():
            await submit.click()
            await asyncio.sleep(3)
            
            # Check for success
            success = await self._check_success(page)
            if success:
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    submitted_at=datetime.now(),
                    message="Application submitted successfully",
                    confirmation_id=f"GH_{job.id}"
                )
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Could not submit application"
        )
        
    async def _apply_lever(
        self, page, job: JobPosting, resume: Resume, profile: UserProfile, auto_submit: bool
    ) -> ApplicationResult:
        """Apply to a Lever job."""
        logger.info("  Filling Lever form...")
        
        fields_filled = 0
        if await self._fill_field(page, 'input[name="name[first]"]', profile.first_name):
            fields_filled += 1
        if await self._fill_field(page, 'input[name="name[last]"]', profile.last_name):
            fields_filled += 1
        if await self._fill_field(page, 'input[name="email"]', profile.email):
            fields_filled += 1
            
        logger.info(f"    Filled {fields_filled}/3 fields")
        
        # Resume
        if resume.file_path and os.path.exists(resume.file_path):
            resume_input = page.locator('input[name="resume"]').first
            if await resume_input.count() > 0:
                await resume_input.set_input_files(resume.file_path)
                logger.info("    Resume uploaded")
        
        # LinkedIn
        await self._fill_field(page, 'input[name="urls[LinkedIn]"]', profile.linkedin or '')
        
        if not auto_submit:
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Form filled, ready for review"
            )
        
        # Submit
        submit = page.locator('button[type="submit"]').first
        if await submit.count() > 0:
            await submit.click()
            await asyncio.sleep(3)
            return ApplicationResult(
                status=ApplicationStatus.SUBMITTED,
                submitted_at=datetime.now(),
                confirmation_id=f"LV_{job.id}"
            )
            
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Submit button not found"
        )
        
    async def _apply_ashby(
        self, page, job: JobPosting, resume: Resume, profile: UserProfile, auto_submit: bool
    ) -> ApplicationResult:
        """Apply to an Ashby job."""
        logger.info("  Filling Ashby form...")
        
        fields_filled = 0
        if await self._fill_field(page, 'input[name="firstName"]', profile.first_name):
            fields_filled += 1
        if await self._fill_field(page, 'input[name="lastName"]', profile.last_name):
            fields_filled += 1
        if await self._fill_field(page, 'input[name="email"]', profile.email):
            fields_filled += 1
            
        logger.info(f"    Filled {fields_filled}/3 fields")
        
        if resume.file_path and os.path.exists(resume.file_path):
            file_input = page.locator('input[type="file"]').first
            if await file_input.count() > 0:
                await file_input.set_input_files(resume.file_path)
        
        if not auto_submit:
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Form filled, ready for review"
            )
        
        submit = page.locator('button[type="submit"]').first
        if await submit.count() > 0:
            await submit.click()
            await asyncio.sleep(3)
            return ApplicationResult(
                status=ApplicationStatus.SUBMITTED,
                submitted_at=datetime.now(),
                confirmation_id=f"ASH_{job.id}"
            )
            
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Submit button not found"
        )
        
    async def _apply_generic(
        self, page, job: JobPosting, resume: Resume, profile: UserProfile, auto_submit: bool
    ) -> ApplicationResult:
        """Generic fallback for unknown platforms."""
        logger.info("  Attempting generic application...")
        
        # Try common field names
        await self._fill_field(page, 'input[name*="first"]', profile.first_name)
        await self._fill_field(page, 'input[name*="last"]', profile.last_name)
        await self._fill_field(page, 'input[type="email"]', profile.email)
        
        if resume.file_path and os.path.exists(resume.file_path):
            file_input = page.locator('input[type="file"]').first
            if await file_input.count() > 0:
                await file_input.set_input_files(resume.file_path)
        
        if not auto_submit:
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Generic form fill attempted"
            )
        
        submit = page.locator('button[type="submit"]').first
        if await submit.count() > 0:
            await submit.click()
            await asyncio.sleep(3)
            return ApplicationResult(
                status=ApplicationStatus.SUBMITTED,
                submitted_at=datetime.now(),
                confirmation_id=f"GEN_{job.id}"
            )
            
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Could not identify form elements"
        )
        
    async def _fill_field(self, page, selector: str, value: str) -> bool:
        """Fill a form field if it exists."""
        if not value:
            return False
            
        try:
            field = page.locator(selector).first
            if await field.count() > 0 and await field.is_visible():
                await field.fill(value)
                return True
        except:
            pass
        return False
        
    async def _check_success(self, page) -> bool:
        """Check if application was successful."""
        success_indicators = [
            '.thank-you',
            '.confirmation',
            'text=Application submitted',
            'text=Thank you for applying',
            'h1:has-text("Thank")',
        ]
        
        for indicator in success_indicators:
            if await page.locator(indicator).count() > 0:
                return True
        return False
