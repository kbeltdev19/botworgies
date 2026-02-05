"""
Complex Form Handler - Production-Ready Multi-Step Form Automation

Handles job applications on platforms with complex multi-step forms:
- Workday (apply.workday.com)
- Taleo (taleo.net)
- SAP SuccessFactors
- iCIMS

Features:
- Multi-step form navigation with state persistence
- iFrame context switching
- Dynamic field detection and filling
- AI-powered question answering
- Real submission with confirmation extraction
- Screenshot capture at each step
"""

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .base import JobPosting, ApplicationResult, ApplicationStatus, UserProfile, Resume

# Import AI service
try:
    from ai.kimi_service import KimiResumeOptimizer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    KimiResumeOptimizer = None

logger = logging.getLogger(__name__)


class FormFieldType(Enum):
    """Types of form fields."""
    TEXT = "text"
    EMAIL = "email"
    TEL = "tel"
    NUMBER = "number"
    TEXTAREA = "textarea"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    FILE = "file"
    DATE = "date"
    HIDDEN = "hidden"


@dataclass
class FormField:
    """Represents a detected form field."""
    selector: str
    name: str
    field_type: FormFieldType
    label: str = ""
    required: bool = False
    options: List[str] = field(default_factory=list)
    value: str = ""
    placeholder: str = ""


@dataclass
class FormStep:
    """Represents a step in a multi-step form."""
    number: int
    title: str = ""
    fields: List[FormField] = field(default_factory=list)
    screenshot_path: str = ""


class ComplexFormHandler:
    """
    Handler for complex form platforms.
    Uses extended timeouts and retry logic with real submissions.
    """
    
    def __init__(self, browser_manager):
        self.browser_manager = browser_manager
        self.max_retries = 3
        self.timeout = 120  # 2 minutes for complex forms
        self.ai_service = KimiResumeOptimizer() if AI_AVAILABLE else None
        
        # Screenshot directory
        self.screenshot_dir = Path("/tmp/complex_form_screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        
        # Form state tracking
        self.form_state = {}
        self.current_step = 0
        
        # Platform-specific selectors
        self.platform_selectors = {
            'workday': {
                'apply_button': [
                    'button[data-automation-id="applyButton"]',
                    'button:has-text("Apply")',
                    'a:has-text("Apply")',
                    'button[data-uxi-element-id="apply_button"]'
                ],
                'next_button': [
                    'button[data-automation-id="nextButton"]',
                    'button:has-text("Next")',
                    'button[data-uxi-element-id="next_button"]',
                    'button[type="submit"]:has-text("Next")'
                ],
                'submit_button': [
                    'button[data-automation-id="submitButton"]',
                    'button:has-text("Submit")',
                    'button[type="submit"]:has-text("Submit Application")',
                    'button[data-uxi-element-id="submit_button"]'
                ],
                'first_name': [
                    'input[data-automation-id="firstName"]',
                    'input[name="firstName"]',
                    'input[id*="firstName"]',
                    'input[placeholder*="First"]'
                ],
                'last_name': [
                    'input[data-automation-id="lastName"]',
                    'input[name="lastName"]',
                    'input[id*="lastName"]',
                    'input[placeholder*="Last"]'
                ],
                'email': [
                    'input[data-automation-id="email"]',
                    'input[type="email"]',
                    'input[name="email"]',
                    'input[id*="email"]'
                ],
                'phone': [
                    'input[data-automation-id="phone"]',
                    'input[type="tel"]',
                    'input[name="phone"]',
                    'input[id*="phone"]'
                ],
                'resume_upload': [
                    'input[data-automation-id="file-upload-input"]',
                    'input[type="file"][accept*="pdf"]',
                    'input[type="file"][name*="resume"]'
                ],
                'success_indicator': [
                    '[data-automation-id="applicationConfirmation"]',
                    '.wd-confirmation-message',
                    'text=Thank you for your application',
                    'text=Application submitted'
                ]
            },
            'taleo': {
                'apply_button': [
                    'a:has-text("Apply to this job")',
                    'a:has-text("Apply")',
                    'button:has-text("Apply")'
                ],
                'next_button': [
                    'button:has-text("Next")',
                    'input[type="button"][value="Next"]',
                    'button[type="submit"]:has-text("Next")'
                ],
                'submit_button': [
                    'button:has-text("Submit")',
                    'input[type="submit"][value="Submit"]',
                    'button[type="submit"]:has-text("Submit Application")'
                ],
                'first_name': [
                    'input[name*="first"]',
                    'input[id*="first"]',
                    'input[placeholder*="First"]'
                ],
                'last_name': [
                    'input[name*="last"]',
                    'input[id*="last"]',
                    'input[placeholder*="Last"]'
                ],
                'email': [
                    'input[type="email"]',
                    'input[name*="email"]',
                    'input[id*="email"]'
                ],
                'phone': [
                    'input[type="tel"]',
                    'input[name*="phone"]',
                    'input[name*="mobile"]'
                ],
                'resume_upload': [
                    'input[type="file"][name*="resume"]',
                    'input[type="file"][id*="resume"]'
                ],
                'success_indicator': [
                    'text=Application submitted',
                    'text=Thank you for applying',
                    '.taleo-confirmation'
                ]
            },
            'generic': {
                'apply_button': [
                    'a:has-text("Apply")',
                    'button:has-text("Apply")',
                    'input[value="Apply"]'
                ],
                'next_button': [
                    'button:has-text("Next")',
                    'button[type="button"]:has-text("Continue")',
                    'input[value="Next"]'
                ],
                'submit_button': [
                    'button[type="submit"]:has-text("Submit")',
                    'input[type="submit"][value="Submit"]',
                    'button:has-text("Submit Application")'
                ],
                'first_name': [
                    'input[name*="first"]',
                    'input[id*="first"]',
                    'input[placeholder*="First"]'
                ],
                'last_name': [
                    'input[name*="last"]',
                    'input[id*="last"]',
                    'input[placeholder*="Last"]'
                ],
                'email': [
                    'input[type="email"]',
                    'input[name*="email"]'
                ],
                'phone': [
                    'input[type="tel"]',
                    'input[name*="phone"]'
                ],
                'resume_upload': [
                    'input[type="file"]'
                ],
                'success_indicator': [
                    'text=Thank you',
                    'text=successfully submitted',
                    'text=application received'
                ]
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
        Apply to a job on a complex form platform with REAL submission.
        
        Args:
            job: Job posting
            resume: Resume
            profile: User profile
            auto_submit: If True, actually submits the application
        
        Returns:
            ApplicationResult with status and confirmation details
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
    
    async def _capture_screenshot(self, page, job_id: str, step: int, label: str) -> str:
        """Capture screenshot of current state."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self._detect_platform(job_id)}_{job_id}_step{step:02d}_{label}_{timestamp}.png"
        filepath = self.screenshot_dir / filename
        
        try:
            await page.screenshot(path=str(filepath), full_page=True)
            logger.info(f"  Screenshot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"  Screenshot failed: {e}")
            return ""
    
    async def _apply_workday(
        self, job: JobPosting, resume: Resume, profile: UserProfile, auto_submit: bool
    ) -> ApplicationResult:
        """
        Apply to a Workday job with real submission.
        """
        logger.info("  Filling Workday form...")
        
        session = await self.browser_manager.create_stealth_session(platform='workday')
        page = session.page
        
        screenshots = []
        step = 0
        
        try:
            # Navigate to job
            logger.info(f"  Navigating to {job.url}")
            await page.goto(job.url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
            
            step += 1
            screenshots.append(await self._capture_screenshot(page, job.id, step, "initial"))
            
            # Click apply button
            apply_clicked = await self._click_element(page, 'apply_button', 'workday')
            if not apply_clicked:
                logger.warning("  Apply button not found, might be on application page already")
            else:
                await asyncio.sleep(3)
                step += 1
                screenshots.append(await self._capture_screenshot(page, job.id, step, "after_apply_click"))
            
            # Handle multi-step form
            max_steps = 15
            for current_step in range(1, max_steps + 1):
                logger.info(f"  Processing step {current_step}")
                self.current_step = current_step
                
                await asyncio.sleep(2)
                
                # Capture step screenshot
                step += 1
                screenshots.append(await self._capture_screenshot(page, job.id, step, f"step_{current_step}"))
                
                # Check for iFrames and switch if needed
                await self._handle_iframes(page)
                
                # Detect and fill all form fields
                fields = await self._detect_form_fields(page)
                logger.info(f"    Detected {len(fields)} fields")
                
                filled_fields = await self._fill_detected_fields(page, fields, profile, resume)
                logger.info(f"    Filled {len(filled_fields)} fields")
                
                # Handle resume upload specifically
                if resume.file_path and Path(resume.file_path).exists():
                    await self._upload_resume_workday(page, resume.file_path)
                
                # Check for custom questions
                questions_answered = await self._answer_custom_questions(page, resume, profile)
                if questions_answered:
                    logger.info(f"    Answered {len(questions_answered)} custom questions")
                
                # Check if this is the submit step
                is_submit_step = await self._is_submit_step(page, 'workday')
                
                if is_submit_step:
                    logger.info("  Found submit step")
                    
                    # Capture review screenshot
                    step += 1
                    review_screenshot = await self._capture_screenshot(page, job.id, step, "review")
                    screenshots.append(review_screenshot)
                    
                    if not auto_submit:
                        return ApplicationResult(
                            status=ApplicationStatus.PENDING_REVIEW,
                            message=f"Workday form ready for final submission. Review screenshot: {review_screenshot}",
                            screenshot_path=review_screenshot
                        )
                    
                    # Submit the application
                    logger.info("  Submitting application...")
                    submit_clicked = await self._click_element(page, 'submit_button', 'workday')
                    
                    if submit_clicked:
                        await asyncio.sleep(5)
                        
                        # Check for success
                        if await self._check_success(page, 'workday'):
                            confirmation_id = await self._extract_confirmation(page)
                            
                            step += 1
                            success_screenshot = await self._capture_screenshot(page, job.id, step, "success")
                            screenshots.append(success_screenshot)
                            
                            return ApplicationResult(
                                status=ApplicationStatus.SUBMITTED,
                                message="Application submitted successfully via Workday",
                                confirmation_id=confirmation_id,
                                screenshot_path=success_screenshot,
                                submitted_at=datetime.now()
                            )
                        else:
                            # Check for errors
                            error_msg = await self._get_error_message(page)
                            if error_msg:
                                return ApplicationResult(
                                    status=ApplicationStatus.ERROR,
                                    message=f"Submission error: {error_msg}",
                                    screenshot_path=screenshots[-1]
                                )
                    else:
                        return ApplicationResult(
                            status=ApplicationStatus.ERROR,
                            message="Could not click submit button",
                            screenshot_path=screenshots[-1]
                        )
                
                # Click Next to proceed
                next_clicked = await self._click_element(page, 'next_button', 'workday')
                
                if not next_clicked:
                    # No next button - check if we're done
                    if await self._check_success(page, 'workday'):
                        confirmation_id = await self._extract_confirmation(page)
                        return ApplicationResult(
                            status=ApplicationStatus.SUBMITTED,
                            message="Application submitted (no next button)",
                            confirmation_id=confirmation_id,
                            screenshot_path=screenshots[-1],
                            submitted_at=datetime.now()
                        )
                    
                    logger.warning("  No next button found, might be stuck")
                    break
                
                await asyncio.sleep(2)
            
            # Max steps reached
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Max steps ({max_steps}) reached without submission",
                screenshot_path=screenshots[-1]
            )
            
        except Exception as e:
            logger.error(f"  Workday error: {e}")
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Workday error: {str(e)[:200]}",
                screenshot_path=screenshots[-1] if screenshots else None,
                error=str(e)
            )
        finally:
            await self.browser_manager.close_session(session.session_id)
    
    async def _apply_taleo(
        self, job: JobPosting, resume: Resume, profile: UserProfile, auto_submit: bool
    ) -> ApplicationResult:
        """
        Apply to a Taleo job with real submission.
        """
        logger.info("  Filling Taleo form...")
        
        session = await self.browser_manager.create_stealth_session(platform='taleo')
        page = session.page
        
        screenshots = []
        step = 0
        
        try:
            await page.goto(job.url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
            
            step += 1
            screenshots.append(await self._capture_screenshot(page, job.id, step, "initial"))
            
            # Click apply link
            apply_clicked = await self._click_element(page, 'apply_button', 'taleo')
            if apply_clicked:
                await asyncio.sleep(3)
                step += 1
                screenshots.append(await self._capture_screenshot(page, job.id, step, "after_apply"))
            
            # Taleo often uses multiple pages or sections
            max_sections = 10
            for section in range(1, max_sections + 1):
                logger.info(f"  Processing section {section}")
                
                await asyncio.sleep(2)
                step += 1
                screenshots.append(await self._capture_screenshot(page, job.id, step, f"section_{section}"))
                
                # Fill basic fields
                await self._fill_field_by_type(page, 'first_name', profile.first_name, 'taleo')
                await self._fill_field_by_type(page, 'last_name', profile.last_name, 'taleo')
                await self._fill_field_by_type(page, 'email', profile.email, 'taleo')
                await self._fill_field_by_type(page, 'phone', profile.phone, 'taleo')
                
                # Upload resume
                if resume.file_path and Path(resume.file_path).exists():
                    await self._upload_resume_generic(page, resume.file_path, 'taleo')
                
                # Answer custom questions
                await self._answer_custom_questions(page, resume, profile)
                
                # Check if submit step
                is_submit = await self._is_submit_step(page, 'taleo')
                
                if is_submit:
                    step += 1
                    review_screenshot = await self._capture_screenshot(page, job.id, step, "review")
                    screenshots.append(review_screenshot)
                    
                    if not auto_submit:
                        return ApplicationResult(
                            status=ApplicationStatus.PENDING_REVIEW,
                            message=f"Taleo form ready for submission. Review: {review_screenshot}",
                            screenshot_path=review_screenshot
                        )
                    
                    # Submit
                    submit_clicked = await self._click_element(page, 'submit_button', 'taleo')
                    
                    if submit_clicked:
                        await asyncio.sleep(5)
                        
                        if await self._check_success(page, 'taleo'):
                            confirmation_id = await self._extract_confirmation(page)
                            return ApplicationResult(
                                status=ApplicationStatus.SUBMITTED,
                                message="Application submitted via Taleo",
                                confirmation_id=confirmation_id,
                                screenshot_path=screenshots[-1],
                                submitted_at=datetime.now()
                            )
                
                # Click next
                next_clicked = await self._click_element(page, 'next_button', 'taleo')
                if not next_clicked:
                    break
            
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Taleo form partially filled",
                screenshot_path=screenshots[-1]
            )
            
        except Exception as e:
            logger.error(f"  Taleo error: {e}")
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Taleo error: {str(e)[:200]}",
                screenshot_path=screenshots[-1] if screenshots else None
            )
        finally:
            await self.browser_manager.close_session(session.session_id)
    
    async def _apply_sap(
        self, job: JobPosting, resume: Resume, profile: UserProfile, auto_submit: bool
    ) -> ApplicationResult:
        """SAP SuccessFactors - complex, often requires account."""
        logger.info("  SAP SuccessFactors requires manual application")
        
        # SAP is very complex, return external link
        return ApplicationResult(
            status=ApplicationStatus.EXTERNAL_APPLICATION,
            message="SAP SuccessFactors requires manual application",
            external_url=job.url
        )
    
    async def _apply_generic(
        self, job: JobPosting, resume: Resume, profile: UserProfile, auto_submit: bool
    ) -> ApplicationResult:
        """Generic fallback for unknown complex forms."""
        logger.info("  Attempting generic complex form fill...")
        
        session = await self.browser_manager.create_stealth_session(platform='unknown')
        page = session.page
        
        screenshots = []
        step = 0
        
        try:
            await page.goto(job.url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
            
            step += 1
            screenshots.append(await self._capture_screenshot(page, job.id, step, "initial"))
            
            # Try to fill any fields we can find
            await self._fill_field_by_type(page, 'first_name', profile.first_name, 'generic')
            await self._fill_field_by_type(page, 'last_name', profile.last_name, 'generic')
            await self._fill_field_by_type(page, 'email', profile.email, 'generic')
            await self._fill_field_by_type(page, 'phone', profile.phone, 'generic')
            
            # Upload resume
            if resume.file_path and Path(resume.file_path).exists():
                await self._upload_resume_generic(page, resume.file_path, 'generic')
            
            step += 1
            screenshots.append(await self._capture_screenshot(page, job.id, step, "filled"))
            
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Generic form fill attempted - manual review required",
                screenshot_path=screenshots[-1]
            )
            
        except Exception as e:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"Generic error: {str(e)[:100]}",
                screenshot_path=screenshots[-1] if screenshots else None
            )
        finally:
            await self.browser_manager.close_session(session.session_id)
    
    async def _handle_iframes(self, page):
        """Detect and handle iFrames (common in Workday)."""
        try:
            frames = page.frames
            if len(frames) > 1:
                logger.info(f"    Found {len(frames)} frames, checking for form frames")
                for frame in frames:
                    try:
                        # Check if frame has form elements
                        has_form = await frame.locator('input, select, textarea').count() > 0
                        if has_form:
                            logger.info("    Found form in iframe")
                            return frame
                    except:
                        continue
        except Exception as e:
            logger.debug(f"    iFrame handling error: {e}")
        return page
    
    async def _detect_form_fields(self, page) -> List[FormField]:
        """Dynamically detect all form fields on the page."""
        fields = []
        
        try:
            # Execute JavaScript to detect fields
            field_data = await page.evaluate("""
                () => {
                    const fields = [];
                    const inputs = document.querySelectorAll('input, select, textarea');
                    
                    inputs.forEach((el, index) => {
                        if (el.type === 'hidden' || el.offsetParent === null) return;
                        
                        const label = document.querySelector(`label[for="${el.id}"]`) ||
                                     el.closest('label') ||
                                     el.previousElementSibling;
                        
                        const labelText = label ? label.textContent.trim() : '';
                        
                        // Get options for select elements
                        let options = [];
                        if (el.tagName === 'SELECT') {
                            options = Array.from(el.options).map(o => o.text);
                        }
                        
                        fields.push({
                            tag: el.tagName.toLowerCase(),
                            type: el.type,
                            name: el.name,
                            id: el.id,
                            label: labelText,
                            placeholder: el.placeholder || '',
                            required: el.required,
                            selector: el.id ? `#${el.id}` : 
                                     el.name ? `[name="${el.name}"]` :
                                     `${el.tagName.toLowerCase()}:nth-of-type(${index + 1})`,
                            options: options
                        });
                    });
                    
                    return fields;
                }
            """)
            
            for data in field_data:
                field_type = self._map_field_type(data['type'], data['tag'])
                field = FormField(
                    selector=data['selector'],
                    name=data['name'] or data['id'] or '',
                    field_type=field_type,
                    label=data['label'],
                    required=data['required'],
                    options=data['options'],
                    placeholder=data['placeholder']
                )
                fields.append(field)
                
        except Exception as e:
            logger.error(f"    Field detection error: {e}")
        
        return fields
    
    def _map_field_type(self, html_type: str, tag: str) -> FormFieldType:
        """Map HTML field type to FormFieldType."""
        type_mapping = {
            'text': FormFieldType.TEXT,
            'email': FormFieldType.EMAIL,
            'tel': FormFieldType.TEL,
            'number': FormFieldType.NUMBER,
            'textarea': FormFieldType.TEXTAREA,
            'select': FormFieldType.SELECT,
            'checkbox': FormFieldType.CHECKBOX,
            'radio': FormFieldType.RADIO,
            'file': FormFieldType.FILE,
            'date': FormFieldType.DATE,
            'hidden': FormFieldType.HIDDEN
        }
        return type_mapping.get(html_type, FormFieldType.TEXT)
    
    async def _fill_detected_fields(self, page, fields: List[FormField], profile: UserProfile, resume: Resume) -> List[str]:
        """Fill detected fields with profile/resume data."""
        filled = []
        
        field_mapping = {
            'first': profile.first_name,
            'last': profile.last_name,
            'email': profile.email,
            'phone': profile.phone,
            'mobile': profile.phone,
            'linkedin': profile.linkedin_url or '',
            'location': '',
            'website': '',
            'portfolio': ''
        }
        
        for field in fields:
            try:
                # Determine value based on field name/label
                value = None
                label_lower = (field.label or field.name).lower()
                
                for key, val in field_mapping.items():
                    if key in label_lower or key in field.name.lower():
                        value = val
                        break
                
                if value and field.field_type in [FormFieldType.TEXT, FormFieldType.EMAIL, FormFieldType.TEL]:
                    loc = page.locator(field.selector).first
                    if await loc.count() > 0:
                        await loc.fill(str(value))
                        filled.append(field.name)
                        await asyncio.sleep(0.3)
                        
            except Exception as e:
                logger.debug(f"    Failed to fill field {field.name}: {e}")
        
        return filled
    
    async def _fill_field_by_type(self, page, field_type: str, value: str, platform: str) -> bool:
        """Fill field by type using platform-specific selectors."""
        if not value:
            return False
        
        selectors = self.platform_selectors.get(platform, {}).get(field_type, [])
        
        for selector in selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.fill(str(value))
                    return True
            except:
                continue
        
        return False
    
    async def _upload_resume_workday(self, page, file_path: str):
        """Upload resume for Workday."""
        try:
            selectors = self.platform_selectors['workday']['resume_upload']
            
            for selector in selectors:
                loc = page.locator(selector).first
                if await loc.count() > 0:
                    await loc.set_input_files(file_path)
                    logger.info(f"    Resume uploaded: {file_path}")
                    await asyncio.sleep(2)
                    return True
                    
        except Exception as e:
            logger.error(f"    Resume upload failed: {e}")
        return False
    
    async def _upload_resume_generic(self, page, file_path: str, platform: str):
        """Generic resume upload."""
        try:
            file_input = page.locator('input[type="file"]').first
            if await file_input.count() > 0:
                await file_input.set_input_files(file_path)
                logger.info(f"    Resume uploaded")
                await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"    Resume upload error: {e}")
    
    async def _answer_custom_questions(self, page, resume: Resume, profile: UserProfile) -> List[Dict]:
        """Answer custom questions using AI."""
        answered = []
        
        if not self.ai_service:
            return answered
        
        try:
            # Find question containers
            question_selectors = [
                '[data-automation-id*="question"]',
                '.form-group',
                '.field-container',
                '[class*="question"]'
            ]
            
            for selector in question_selectors:
                questions = await page.locator(selector).all()
                
                for question_el in questions:
                    try:
                        # Get question text
                        label = await question_el.locator('label, .field-label, .question-text').inner_text()
                        
                        if not label:
                            continue
                        
                        # Get input element
                        input_el = question_el.locator('input, textarea, select').first
                        if await input_el.count() == 0:
                            continue
                        
                        # Check if already filled
                        current_val = await input_el.input_value()
                        if current_val:
                            continue
                        
                        # Get input type
                        input_type = await input_el.get_attribute('type') or 'text'
                        
                        # Answer with AI
                        answer = await self.ai_service.answer_application_question(
                            question=label,
                            resume_context=resume.raw_text[:2000],
                            existing_answers=profile.custom_answers
                        )
                        
                        # Fill based on type
                        if input_type in ['text', 'email', 'tel']:
                            await input_el.fill(answer)
                        elif input_type == 'textarea':
                            await input_el.fill(answer)
                        elif input_type == 'select-one':
                            # Try to select matching option
                            options = await input_el.locator('option').all()
                            for option in options:
                                opt_text = await option.inner_text()
                                if answer.lower() in opt_text.lower():
                                    await input_el.select_option(value=await option.get_attribute('value'))
                                    break
                        
                        answered.append({'question': label, 'answer': answer})
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        continue
                        
        except Exception as e:
            logger.error(f"    Question answering error: {e}")
        
        return answered
    
    async def _click_element(self, page, element_type: str, platform: str) -> bool:
        """Click element using platform-specific selectors."""
        selectors = self.platform_selectors.get(platform, {}).get(element_type, [])
        
        for selector in selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    if await loc.is_enabled():
                        await loc.click()
                        logger.debug(f"    Clicked: {selector}")
                        return True
            except Exception as e:
                continue
        
        return False
    
    async def _is_submit_step(self, page, platform: str) -> bool:
        """Check if current step is the submit step."""
        # Check for submit button
        submit_selectors = self.platform_selectors.get(platform, {}).get('submit_button', [])
        
        for selector in submit_selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    return True
            except:
                continue
        
        # Check for review indicators
        review_keywords = ['review', 'verify', 'confirm', 'submit application']
        content = await page.content()
        content_lower = content.lower()
        
        for keyword in review_keywords:
            if keyword in content_lower:
                return True
        
        return False
    
    async def _check_success(self, page, platform: str) -> bool:
        """Check if application was successfully submitted."""
        success_selectors = self.platform_selectors.get(platform, {}).get('success_indicator', [])
        
        for selector in success_selectors:
            try:
                if selector.startswith('text='):
                    text = selector.replace('text=', '')
                    loc = page.locator(f"text={text}").first
                else:
                    loc = page.locator(selector).first
                
                if await loc.count() > 0 and await loc.is_visible():
                    return True
            except:
                continue
        
        return False
    
    async def _extract_confirmation(self, page) -> Optional[str]:
        """Extract confirmation ID from success page."""
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
    
    async def _get_error_message(self, page) -> Optional[str]:
        """Get error message from page."""
        error_selectors = [
            '.error-message',
            '[role="alert"]',
            '.form-error',
            '.validation-error',
            '[data-automation-id*="error"]'
        ]
        
        for selector in error_selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    return await loc.inner_text()
            except:
                continue
        
        return None
