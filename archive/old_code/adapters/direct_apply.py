"""
Direct Apply Handler - Production-Ready Form Automation

Handles job applications on platforms with direct application URLs:
- Greenhouse (boards.greenhouse.io)
- Lever (jobs.lever.co)
- Ashby (jobs.ashbyhq.com)
- SmartRecruiters
- BambooHR

Features:
- Direct navigation to application forms
- Complete form filling with all fields
- Resume and cover letter upload
- AI-powered question answering
- Real submission with confirmation extraction
- Screenshot capture at each step
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .base import JobPosting, ApplicationResult, ApplicationStatus, UserProfile, Resume

# Import AI service
try:
    from ai.kimi_service import KimiResumeOptimizer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    KimiResumeOptimizer = None

logger = logging.getLogger(__name__)


class DirectApplyHandler:
    """
    Handler for direct-apply platforms.
    Navigates directly to application URL and fills form with real submission.
    """
    
    def __init__(self, browser_manager):
        self.browser_manager = browser_manager
        self.ai_service = KimiResumeOptimizer() if AI_AVAILABLE else None
        
        # Screenshot directory
        self.screenshot_dir = Path("/tmp/direct_apply_screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        
        # Platform-specific selectors
        self.selectors = {
            'greenhouse': {
                'first_name': ['#first_name', 'input[name="first_name"]', 'input[autocomplete="given-name"]'],
                'last_name': ['#last_name', 'input[name="last_name"]', 'input[autocomplete="family-name"]'],
                'email': ['#email', 'input[name="email"]', 'input[type="email"]', 'input[autocomplete="email"]'],
                'phone': ['#phone', 'input[name="phone"]', 'input[type="tel"]', 'input[autocomplete="tel"]'],
                'linkedin': ['input[name="job_application[answers_attributes][0][text_value]"]', 
                           'input[placeholder*="LinkedIn"]', 'input[name*="linkedin"]'],
                'website': ['input[name="job_application[answers_attributes][1][text_value]"]', 
                          'input[name*="website"]', 'input[name*="portfolio"]'],
                'resume': ['input[type="file"][name*="resume"]', '#resume', 'input[accept*="pdf"]'],
                'cover_letter': ['textarea[name*="cover_letter"]', 'textarea[placeholder*="cover"]'],
                'submit': ['input[type="submit"]', '#submit_app', 'button[type="submit"]', 
                         'button:has-text("Submit Application")'],
                'success': ['#application_confirmation', '.thank-you', '.confirmation', 
                          'text=Application submitted', 'text=Thank you for applying'],
                'error': ['.error-message', '.field-error', '.flash-error']
            },
            'lever': {
                'first_name': ['input[name="name[first]"]', 'input[placeholder*="First"]'],
                'last_name': ['input[name="name[last]"]', 'input[placeholder*="Last"]'],
                'email': ['input[name="email"]', 'input[type="email"]'],
                'phone': ['input[name="phone"]', 'input[type="tel"]'],
                'linkedin': ['input[name="urls[LinkedIn]"]', 'input[placeholder*="LinkedIn"]'],
                'resume': ['input[name="resume"]', 'input[type="file"][data-qa="resume-input"]'],
                'cover_letter': ['textarea[name="coverLetter"]', 'textarea[placeholder*="cover"]'],
                'submit': ['button[type="submit"]', 'button:has-text("Submit Application")'],
                'success': ['.thank-you', '.confirmation', 'text=Application submitted'],
                'error': ['.error', '[data-qa="error-message"]']
            },
            'ashby': {
                'first_name': ['input[name="firstName"]', 'input[placeholder*="First"]'],
                'last_name': ['input[name="lastName"]', 'input[placeholder*="Last"]'],
                'email': ['input[name="email"]', 'input[type="email"]'],
                'phone': ['input[name="phone"]', 'input[type="tel"]'],
                'linkedin': ['input[name="linkedin"]', 'input[placeholder*="LinkedIn"]'],
                'resume': ['input[type="file"]', 'input[name="resume"]'],
                'submit': ['button[type="submit"]', 'button:has-text("Submit")'],
                'success': ['text=Application submitted', '.confirmation', '.thank-you'],
                'error': ['.error-message', '[class*="error"]']
            },
            'generic': {
                'first_name': ['input[name*="first"]', 'input[id*="first"]'],
                'last_name': ['input[name*="last"]', 'input[id*="last"]'],
                'email': ['input[type="email"]', 'input[name*="email"]'],
                'phone': ['input[type="tel"]', 'input[name*="phone"]'],
                'resume': ['input[type="file"]', 'input[name*="resume"]'],
                'submit': ['button[type="submit"]', 'input[type="submit"]'],
                'success': ['text=Thank you', 'text=submitted', 'text=success'],
                'error': ['.error', '[class*="error"]']
            }
        }
    
    async def apply(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        Apply to a job on a direct-apply platform with REAL submission.
        
        Args:
            job: Job posting with direct apply URL
            resume: Resume to upload
            profile: User profile
            auto_submit: If True, actually submits the application
        
        Returns:
            ApplicationResult with status and confirmation
        """
        platform = self._detect_platform(job.url)
        logger.info(f"📝 Direct apply: {job.title} at {job.company} ({platform})")
        
        # Create browser session
        session = await self.browser_manager.create_stealth_session(platform=platform)
        page = session.page
        
        screenshots = []
        step = 0
        
        try:
            # Navigate to job
            logger.info(f"  Navigating to {job.url[:60]}...")
            await page.goto(job.url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)
            
            step += 1
            screenshots.append(await self._capture_screenshot(page, job.id, step, "initial", platform))
            
            # Route to platform-specific handler
            if platform == 'greenhouse':
                result = await self._apply_greenhouse(page, job, resume, profile, auto_submit, screenshots)
            elif platform == 'lever':
                result = await self._apply_lever(page, job, resume, profile, auto_submit, screenshots)
            elif platform == 'ashby':
                result = await self._apply_ashby(page, job, resume, profile, auto_submit, screenshots)
            else:
                result = await self._apply_generic(page, job, resume, profile, auto_submit, screenshots)
            
            # Add screenshots to result
            if screenshots and not result.screenshot_path:
                result.screenshot_path = screenshots[-1]
            
            return result
            
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")
            if screenshots:
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=str(e)[:200],
                    screenshot_path=screenshots[-1],
                    error=str(e)
                )
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=str(e)[:200],
                error=str(e)
            )
        finally:
            await self.browser_manager.close_session(session.session_id)
    
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
        return 'generic'
    
    async def _capture_screenshot(self, page, job_id: str, step: int, label: str, platform: str) -> str:
        """Capture screenshot."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{platform}_{job_id}_step{step:02d}_{label}_{timestamp}.png"
        filepath = self.screenshot_dir / filename
        
        try:
            await page.screenshot(path=str(filepath), full_page=True)
            logger.debug(f"  Screenshot: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"  Screenshot failed: {e}")
            return ""
    
    async def _apply_greenhouse(
        self, page, job: JobPosting, resume: Resume, profile: UserProfile, 
        auto_submit: bool, screenshots: List[str]
    ) -> ApplicationResult:
        """Apply to a Greenhouse job with real submission."""
        logger.info("  Filling Greenhouse form...")
        
        step = len(screenshots)
        
        # Click apply button if present
        apply_btn = page.locator('#apply_button, .apply-button, a:has-text("Apply")').first
        if await apply_btn.count() > 0 and await apply_btn.is_visible():
            await apply_btn.click()
            await asyncio.sleep(2)
            step += 1
            screenshots.append(await self._capture_screenshot(page, job.id, step, "after_apply_click", "greenhouse"))
        
        # Fill all fields
        fields_filled = await self._fill_platform_fields(page, 'greenhouse', profile)
        logger.info(f"    Filled {len(fields_filled)} fields: {fields_filled}")
        
        # Resume upload
        if resume.file_path and Path(resume.file_path).exists():
            uploaded = await self._upload_file(page, 'greenhouse', 'resume', resume.file_path)
            if uploaded:
                logger.info("    Resume uploaded")
                await asyncio.sleep(2)
        
        # LinkedIn and website
        await self._fill_field(page, 'greenhouse', 'linkedin', profile.linkedin_url or '')
        if hasattr(profile, 'website'):
            await self._fill_field(page, 'greenhouse', 'website', profile.website or '')
        
        # Answer custom questions
        questions_answered = await self._answer_custom_questions(page, resume, profile)
        if questions_answered:
            logger.info(f"    Answered {len(questions_answered)} custom questions")
        
        step += 1
        review_screenshot = await self._capture_screenshot(page, job.id, step, "review", "greenhouse")
        screenshots.append(review_screenshot)
        
        if not auto_submit:
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message=f"Greenhouse form filled, ready for submission. Review: {review_screenshot}",
                screenshot_path=review_screenshot
            )
        
        # Submit
        logger.info("  Submitting application...")
        submit_clicked = await self._click_submit(page, 'greenhouse')
        
        if submit_clicked:
            await asyncio.sleep(3)
            
            step += 1
            screenshots.append(await self._capture_screenshot(page, job.id, step, "after_submit", "greenhouse"))
            
            # Check for success
            if await self._check_success(page, 'greenhouse'):
                confirmation_id = await self._extract_confirmation(page)
                
                step += 1
                success_screenshot = await self._capture_screenshot(page, job.id, step, "success", "greenhouse")
                screenshots.append(success_screenshot)
                
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message="Application submitted successfully via Greenhouse",
                    confirmation_id=confirmation_id,
                    screenshot_path=success_screenshot,
                    submitted_at=datetime.now()
                )
            else:
                # Check for errors
                error_msg = await self._get_error_message(page, 'greenhouse')
                return ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=f"Submission failed: {error_msg or 'Unknown error'}",
                    screenshot_path=screenshots[-1]
                )
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Could not submit application - submit button not found or not clickable",
            screenshot_path=screenshots[-1]
        )
    
    async def _apply_lever(
        self, page, job: JobPosting, resume: Resume, profile: UserProfile,
        auto_submit: bool, screenshots: List[str]
    ) -> ApplicationResult:
        """Apply to a Lever job with real submission."""
        logger.info("  Filling Lever form...")
        
        step = len(screenshots)
        
        # Fill fields
        fields_filled = await self._fill_platform_fields(page, 'lever', profile)
        logger.info(f"    Filled {len(fields_filled)} fields")
        
        # Resume upload
        if resume.file_path and Path(resume.file_path).exists():
            uploaded = await self._upload_file(page, 'lever', 'resume', resume.file_path)
            if uploaded:
                logger.info("    Resume uploaded")
        
        # LinkedIn
        await self._fill_field(page, 'lever', 'linkedin', profile.linkedin_url or '')
        
        # Answer custom questions
        await self._answer_custom_questions(page, resume, profile)
        
        step += 1
        review_screenshot = await self._capture_screenshot(page, job.id, step, "review", "lever")
        screenshots.append(review_screenshot)
        
        if not auto_submit:
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message=f"Lever form filled, ready for submission. Review: {review_screenshot}",
                screenshot_path=review_screenshot
            )
        
        # Submit
        submit_clicked = await self._click_submit(page, 'lever')
        
        if submit_clicked:
            await asyncio.sleep(3)
            
            if await self._check_success(page, 'lever'):
                confirmation_id = await self._extract_confirmation(page)
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message="Application submitted via Lever",
                    confirmation_id=confirmation_id,
                    screenshot_path=screenshots[-1],
                    submitted_at=datetime.now()
                )
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Could not submit Lever application",
            screenshot_path=screenshots[-1]
        )
    
    async def _apply_ashby(
        self, page, job: JobPosting, resume: Resume, profile: UserProfile,
        auto_submit: bool, screenshots: List[str]
    ) -> ApplicationResult:
        """Apply to an Ashby job with real submission."""
        logger.info("  Filling Ashby form...")
        
        step = len(screenshots)
        
        fields_filled = await self._fill_platform_fields(page, 'ashby', profile)
        logger.info(f"    Filled {len(fields_filled)} fields")
        
        if resume.file_path and Path(resume.file_path).exists():
            await self._upload_file(page, 'ashby', 'resume', resume.file_path)
        
        await self._answer_custom_questions(page, resume, profile)
        
        step += 1
        review_screenshot = await self._capture_screenshot(page, job.id, step, "review", "ashby")
        screenshots.append(review_screenshot)
        
        if not auto_submit:
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message=f"Ashby form filled, ready for submission",
                screenshot_path=review_screenshot
            )
        
        submit_clicked = await self._click_submit(page, 'ashby')
        
        if submit_clicked:
            await asyncio.sleep(3)
            
            if await self._check_success(page, 'ashby'):
                confirmation_id = await self._extract_confirmation(page)
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message="Application submitted via Ashby",
                    confirmation_id=confirmation_id,
                    screenshot_path=screenshots[-1],
                    submitted_at=datetime.now()
                )
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Could not submit Ashby application",
            screenshot_path=screenshots[-1]
        )
    
    async def _apply_generic(
        self, page, job: JobPosting, resume: Resume, profile: UserProfile,
        auto_submit: bool, screenshots: List[str]
    ) -> ApplicationResult:
        """Generic fallback for unknown platforms."""
        logger.info("  Attempting generic application...")
        
        step = len(screenshots)
        
        # Try common field names
        await self._fill_platform_fields(page, 'generic', profile)
        
        if resume.file_path and Path(resume.file_path).exists():
            await self._upload_file(page, 'generic', 'resume', resume.file_path)
        
        step += 1
        screenshots.append(await self._capture_screenshot(page, job.id, step, "filled", "generic"))
        
        return ApplicationResult(
            status=ApplicationStatus.PENDING_REVIEW,
            message="Generic form fill attempted - manual review required",
            screenshot_path=screenshots[-1]
        )
    
    async def _fill_platform_fields(self, page, platform: str, profile: UserProfile) -> List[str]:
        """Fill all standard fields for a platform."""
        filled = []
        
        field_mapping = {
            'first_name': profile.first_name,
            'last_name': profile.last_name,
            'email': profile.email,
            'phone': profile.phone,
            'linkedin': profile.linkedin_url or ''
        }
        
        for field_name, value in field_mapping.items():
            if await self._fill_field(page, platform, field_name, value):
                filled.append(field_name)
                await asyncio.sleep(0.3)
        
        return filled
    
    async def _fill_field(self, page, platform: str, field_type: str, value: str) -> bool:
        """Fill a specific field using platform selectors."""
        if not value:
            return False
        
        selectors = self.selectors.get(platform, {}).get(field_type, [])
        
        for selector in selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.fill(str(value))
                    return True
            except:
                continue
        
        return False
    
    async def _upload_file(self, page, platform: str, file_type: str, file_path: str) -> bool:
        """Upload a file."""
        selectors = self.selectors.get(platform, {}).get(file_type, [])
        
        for selector in selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0:
                    await loc.set_input_files(file_path)
                    return True
            except:
                continue
        
        return False
    
    async def _click_submit(self, page, platform: str) -> bool:
        """Click submit button."""
        selectors = self.selectors.get(platform, {}).get('submit', [])
        
        for selector in selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible() and await loc.is_enabled():
                    await loc.click()
                    return True
            except:
                continue
        
        return False
    
    async def _check_success(self, page, platform: str) -> bool:
        """Check for success indicators."""
        indicators = self.selectors.get(platform, {}).get('success', [])
        
        for indicator in indicators:
            try:
                if indicator.startswith('text='):
                    text = indicator.replace('text=', '')
                    loc = page.locator(f"text={text}").first
                else:
                    loc = page.locator(indicator).first
                
                if await loc.count() > 0 and await loc.is_visible():
                    return True
            except:
                continue
        
        return False
    
    async def _get_error_message(self, page, platform: str) -> Optional[str]:
        """Get error message."""
        selectors = self.selectors.get(platform, {}).get('error', [])
        
        for selector in selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    return await loc.inner_text()
            except:
                continue
        
        return None
    
    async def _extract_confirmation(self, page) -> Optional[str]:
        """Extract confirmation ID."""
        try:
            text = await page.inner_text('body')
            
            patterns = [
                r'confirmation\s*[#:]?\s*([A-Z0-9\-]+)',
                r'reference\s*[#:]?\s*([A-Z0-9\-]+)',
                r'application\s*[#:]?\s*([A-Z0-9\-]{5,})',
                r'id[\s#:]+([A-Z0-9\-]{5,})'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    return matches[0].strip()
                    
        except Exception as e:
            logger.error(f"    Confirmation extraction error: {e}")
        
        return None
    
    async def _answer_custom_questions(self, page, resume: Resume, profile: UserProfile) -> List[Dict]:
        """Answer custom questions using AI."""
        answered = []
        
        if not self.ai_service:
            return answered
        
        try:
            # Find question containers
            question_selectors = [
                '.form-group',
                '.field-container',
                '[class*="question"]',
                '.custom-question'
            ]
            
            for selector in question_selectors:
                questions = await page.locator(selector).all()
                
                for question_el in questions:
                    try:
                        # Get question text
                        label = await question_el.locator('label, .field-label').inner_text()
                        
                        if not label:
                            continue
                        
                        # Get input
                        input_el = question_el.locator('input, textarea, select').first
                        if await input_el.count() == 0:
                            continue
                        
                        # Check if already filled
                        current = await input_el.input_value()
                        if current:
                            continue
                        
                        # Answer with AI
                        answer = await self.ai_service.answer_application_question(
                            question=label,
                            resume_context=resume.raw_text[:2000],
                            existing_answers=profile.custom_answers
                        )
                        
                        # Fill
                        input_type = await input_el.get_attribute('type') or 'text'
                        if input_type in ['text', 'email', 'tel', 'textarea']:
                            await input_el.fill(answer)
                        
                        answered.append({'question': label, 'answer': answer})
                        await asyncio.sleep(0.5)
                        
                    except:
                        continue
                        
        except Exception as e:
            logger.error(f"    Question answering error: {e}")
        
        return answered
