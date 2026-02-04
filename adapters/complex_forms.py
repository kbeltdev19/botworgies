"""
Complex Form Handler

Handles job applications on platforms with complex multi-step forms:
- Workday (apply.workday.com)
- Taleo (taleo.net)
- SAP SuccessFactors
- iCIMS

These platforms often have:
- Multi-step application processes
- CAPTCHA challenges
- iFrames
- Complex validation
- Long forms (5-10 pages)

Strategy: Queue for last, high timeout, multiple retries
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from .base import JobPosting, ApplicationResult, ApplicationStatus, UserProfile, Resume

logger = logging.getLogger(__name__)


class ComplexFormHandler:
    """
    Handler for complex form platforms.
    Uses extended timeouts and retry logic.
    """
    
    def __init__(self, browser_manager):
        self.browser_manager = browser_manager
        self.max_retries = 3
        self.timeout = 120  # 2 minutes for complex forms
        
    async def apply(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        Apply to a job on a complex form platform.
        
        Args:
            job: Job posting
            resume: Resume
            profile: User profile
            auto_submit: Whether to auto-submit
            
        Returns:
            ApplicationResult
        """
        platform = self._detect_platform(job.url)
        logger.info(f"📝 Complex form: {job.title} at {job.company} ({platform})")
        
        # Try with retries
        for attempt in range(1, self.max_retries + 1):
            logger.info(f"  Attempt {attempt}/{self.max_retries}")
            
            try:
                if platform == 'workday':
                    result = await self._apply_workday(job, resume, profile, auto_submit)
                elif platform == 'taleo':
                    result = await self._apply_taleo(job, resume, profile, auto_submit)
                elif platform == 'sap':
                    result = await self._apply_sap(job, resume, profile, auto_submit)
                else:
                    result = await self._apply_generic(job, resume, profile, auto_submit)
                
                # If successful, return
                if result.status == ApplicationStatus.SUBMITTED:
                    return result
                    
                # If failed but can retry, wait and try again
                if attempt < self.max_retries:
                    logger.warning(f"  Failed, retrying in 10s...")
                    await asyncio.sleep(10)
                    
            except Exception as e:
                logger.error(f"  Attempt {attempt} error: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(10)
        
        # All retries failed
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message=f"Failed after {self.max_retries} attempts"
        )
        
    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        url_lower = url.lower()
        if 'workday' in url_lower:
            return 'workday'
        elif 'taleo' in url_lower:
            return 'taleo'
        elif 'sap' in url_lower or 'successfactors' in url_lower:
            return 'sap'
        elif 'icims' in url_lower:
            return 'icims'
        return 'unknown'
        
    async def _apply_workday(
        self, job: JobPosting, resume: Resume, profile: UserProfile, auto_submit: bool
    ) -> ApplicationResult:
        """Apply to a Workday job."""
        logger.info("  Filling Workday form...")
        
        session = await self.browser_manager.create_stealth_session(platform='workday')
        page = session.page
        
        try:
            # Navigate to job
            await page.goto(job.url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
            
            # Click apply button
            apply_btn = page.locator('button[data-automation-id="applyButton"], a:has-text("Apply")').first
            if await apply_btn.count() > 0:
                await apply_btn.click()
                await asyncio.sleep(3)
            
            # Fill basic info
            await self._fill_field(page, 'input[data-automation-id="firstName"]', profile.first_name)
            await self._fill_field(page, 'input[data-automation-id="lastName"]', profile.last_name)
            await self._fill_field(page, 'input[data-automation-id="email"]', profile.email)
            
            # Resume upload (may be in iframe)
            if resume.file_path:
                file_input = page.locator('input[type="file"]').first
                if await file_input.count() > 0:
                    await file_input.set_input_files(resume.file_path)
                    await asyncio.sleep(2)
            
            if not auto_submit:
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message="Workday form partially filled"
                )
            
            # Try to submit
            submit = page.locator('button[data-automation-id="submit"], button:has-text("Submit")').first
            if await submit.count() > 0 and await submit.is_enabled():
                await submit.click()
                await asyncio.sleep(5)
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    submitted_at=datetime.now(),
                    confirmation_id=f"WD_{job.id}"
                )
            else:
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message="Workday submit button not enabled"
                )
                
        except Exception as e:
            logger.error(f"  Workday error: {e}")
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Workday error: {str(e)[:100]}"
            )
        finally:
            await self.browser_manager.close_session(session.session_id)
            
    async def _apply_taleo(
        self, job: JobPosting, resume: Resume, profile: UserProfile, auto_submit: bool
    ) -> ApplicationResult:
        """Apply to a Taleo job."""
        logger.info("  Filling Taleo form...")
        
        session = await self.browser_manager.create_stealth_session(platform='taleo')
        page = session.page
        
        try:
            await page.goto(job.url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
            
            # Taleo often has "Apply to this job" link
            apply_link = page.locator('a:has-text("Apply"), button:has-text("Apply")').first
            if await apply_link.count() > 0:
                await apply_link.click()
                await asyncio.sleep(3)
            
            # Fill form
            await self._fill_field(page, 'input[name*="first"]', profile.first_name)
            await self._fill_field(page, 'input[name*="last"]', profile.last_name)
            await self._fill_field(page, 'input[type="email"]', profile.email)
            
            if not auto_submit:
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message="Taleo form partially filled"
                )
            
            submit = page.locator('button[type="submit"]').first
            if await submit.count() > 0:
                await submit.click()
                await asyncio.sleep(5)
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    submitted_at=datetime.now(),
                    confirmation_id=f"TL_{job.id}"
                )
                
        except Exception as e:
            logger.error(f"  Taleo error: {e}")
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Taleo error: {str(e)[:100]}"
            )
        finally:
            await self.browser_manager.close_session(session.session_id)
            
    async def _apply_sap(
        self, job: JobPosting, resume: Resume, profile: UserProfile, auto_submit: bool
    ) -> ApplicationResult:
        """Apply to a SAP SuccessFactors job."""
        logger.info("  Filling SAP form...")
        
        # SAP is very complex, often requires account
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="SAP SuccessFactors requires manual application"
        )
        
    async def _apply_generic(
        self, job: JobPosting, resume: Resume, profile: UserProfile, auto_submit: bool
    ) -> ApplicationResult:
        """Generic fallback for unknown complex forms."""
        logger.info("  Attempting generic complex form fill...")
        
        session = await self.browser_manager.create_stealth_session(platform='unknown')
        page = session.page
        
        try:
            await page.goto(job.url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
            
            # Try to fill any fields we can find
            await self._fill_field(page, 'input[name*="first"]', profile.first_name)
            await self._fill_field(page, 'input[name*="last"]', profile.last_name)
            await self._fill_field(page, 'input[type="email"]', profile.email)
            
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Generic form fill attempted - manual review required"
            )
            
        except Exception as e:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Generic error: {str(e)[:100]}"
            )
        finally:
            await self.browser_manager.close_session(session.session_id)
            
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
