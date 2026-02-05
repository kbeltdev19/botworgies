"""
Unified Job Adapter Base Class

Consolidates common adapter functionality to eliminate duplication
across 20+ adapter implementations.

Usage:
    class GreenhouseAdapter(UnifiedJobAdapter):
        PLATFORM = "greenhouse"
        
        SELECTORS = {
            'first_name': ['#first_name', 'input[name="first_name"]'],
            'last_name': ['#last_name', 'input[name="last_name"]'],
            'email': ['#email', 'input[type="email"]'],
            'submit': ['#submit_app', 'input[type="submit"]'],
        }
        
        async def _navigate_to_application(self, job):
            await self.page.goto(job.url)
            await self.page.click('#apply_button')
        
        async def _check_success(self):
            return await self.page.locator('.confirmation').count() > 0

That's it! Everything else is handled by the base class.
"""

import asyncio
import logging
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from playwright.async_api import Page, BrowserContext

from adapters.base import (
    JobPlatformAdapter, JobPosting, ApplicationResult, 
    ApplicationStatus, UserProfile, Resume, PlatformType
)
from .screenshot_manager import ScreenshotManager, ScreenshotContext, ScreenshotConfig
from .form_filler import FormFiller, FieldMapping, FillStrategy
from monitoring.application_monitor import get_monitor, ApplicationMonitor

logger = logging.getLogger(__name__)


@dataclass
class AdapterConfig:
    """Configuration for a unified adapter."""
    # Timeouts
    navigation_timeout: int = 30000
    element_timeout: int = 10000
    submit_timeout: int = 30000
    
    # Delays
    pre_selector_delay: float = 2.0
    post_action_delay: float = 1.0
    post_submit_delay: float = 5.0
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 5.0
    
    # Screenshot settings
    capture_screenshots: bool = True
    screenshot_dir: Path = Path("./screenshots")
    
    # Form filling
    fill_strategy: FillStrategy = FillStrategy.STANDARD
    
    # Application flow
    max_form_steps: int = 15
    auto_submit: bool = False  # Default to review mode


class UnifiedJobAdapter(JobPlatformAdapter):
    """
    Unified base class for all job platform adapters.
    
    Eliminates boilerplate code across adapters by providing:
    - Automatic screenshot capture
    - Intelligent form filling
    - Standardized application flow
    - Built-in monitoring
    - Retry logic
    - Confirmation extraction
    
    Subclasses only need to define:
    1. PLATFORM identifier
    2. SELECTORS dictionary
    3. _navigate_to_application() method
    4. _check_success() method (optional)
    5. _extract_confirmation() method (optional)
    """
    
    # Class attributes - override in subclass
    PLATFORM: str = "unknown"
    PLATFORM_TYPE: PlatformType = PlatformType.EXTERNAL
    SELECTORS: Dict[str, List[str]] = {}
    
    # Platform-specific configuration
    CONFIG = AdapterConfig()
    
    def __init__(self, browser_manager, session_cookie: str = None, config: AdapterConfig = None):
        super().__init__(browser_manager, session_cookie)
        self.config = config or self.CONFIG
        
        # Initialize services
        self.screenshots = ScreenshotManager(ScreenshotConfig(
            base_dir=self.config.screenshot_dir / self.PLATFORM
        ))
        self.form_filler = FormFiller(strategy=self.config.fill_strategy)
        self.monitor = get_monitor()
        
        # Session state
        self.page: Optional[Page] = None
        self.context: Optional[BrowserContext] = None
        self.session = None
        self.step_counter = 0
        self.current_job: Optional[JobPosting] = None
    
    # ========================================================================
    # Main Application Flow
    # ========================================================================
    
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        Universal application flow.
        
        This method implements the standard application flow:
        1. Start monitoring
        2. Navigate to job
        3. Fill form
        4. Handle custom questions
        5. Submit or prepare for review
        6. Verify success
        7. Return result
        
        Override specific steps in subclass if needed.
        """
        self.current_job = job
        self.step_counter = 0
        actual_auto_submit = auto_submit or self.config.auto_submit
        
        # Start monitoring
        app_id = f"{self.PLATFORM}_{job.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.monitor.start_application(app_id, job.url, self.PLATFORM)
        
        try:
            # Create browser session
            await self._create_session()
            
            # Step 1: Navigate
            await self._step("navigate", self._navigate_to_application, job)
            
            # Step 2: Fill form
            fill_result = await self._step(
                "fill_form",
                self._fill_application_form,
                profile,
                resume
            )
            
            # Step 3: Handle custom questions
            await self._step(
                "answer_questions",
                self._handle_custom_questions,
                job,
                resume,
                profile
            )
            
            # Step 4: Submit or review
            if actual_auto_submit:
                result = await self._step(
                    "submit",
                    self._submit_application,
                    job
                )
            else:
                result = await self._step(
                    "prepare_review",
                    self._prepare_for_review,
                    job
                )
            
            # Step 5: Verify and extract confirmation
            if result.status == ApplicationStatus.SUBMITTED:
                confirmation_id = await self._extract_confirmation_id()
                result.confirmation_id = confirmation_id
                
                # Capture success screenshot
                await self._capture_step("success")
            
            # Finish monitoring
            self.monitor.finish_application(
                success=result.status == ApplicationStatus.SUBMITTED,
                confirmation_id=result.confirmation_id,
                error_message=result.error if result.status == ApplicationStatus.ERROR else None,
                metrics={
                    "steps_completed": self.step_counter,
                    "fields_filled": fill_result.filled_count if 'fill_result' in locals() else 0,
                    "screenshots_count": len(self.screenshots.captured)
                }
            )
            
            # Add screenshots to result
            if self.screenshots.captured:
                result.screenshot_path = str(self.screenshots.captured[-1].path)
            
            return result
            
        except Exception as e:
            logger.error(f"Application failed: {e}", exc_info=True)
            
            # Capture error screenshot
            if self.page:
                await self._capture_step("error")
            
            # Log failure
            self.monitor.finish_application(
                success=False,
                error_message=str(e)
            )
            
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=str(e)[:200],
                screenshot_path=str(self.screenshots.captured[-1].path) if self.screenshots.captured else None,
                error=str(e)
            )
        
        finally:
            await self._cleanup()
    
    # ========================================================================
    # Steps (override in subclass)
    # ========================================================================
    
    @abstractmethod
    async def _navigate_to_application(self, job: JobPosting):
        """
        Navigate to the job application page.
        
        Override this to:
        1. Navigate to job URL
        2. Click "Apply" button if needed
        3. Wait for form to load
        
        Example:
            await self.page.goto(job.url)
            await self.page.click('#apply_button')
            await self.page.wait_for_selector('#application_form')
        """
        raise NotImplementedError
    
    async def _fill_application_form(
        self,
        profile: UserProfile,
        resume: Resume
    ) -> Any:
        """
        Fill the application form.
        
        Uses FormFiller with platform-specific selectors.
        Override if platform needs special handling.
        """
        # Build field mappings from SELECTORS
        mappings = self._build_field_mappings()
        
        # Fill form
        result = await self.form_filler.fill_all(
            page=self.page,
            profile=profile,
            mappings=mappings,
            resume=resume
        )
        
        logger.info(f"Form filling complete: {result.filled_count}/{result.detected_count} fields")
        return result
    
    async def _handle_custom_questions(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile
    ):
        """
        Handle custom application questions.
        
        Override to implement platform-specific question handling.
        Base implementation uses AI to answer if available.
        """
        # Try to find and answer custom questions
        # This is platform-specific, so base implementation is minimal
        pass
    
    async def _submit_application(self, job: JobPosting) -> ApplicationResult:
        """
        Submit the application.
        
        Override for platform-specific submit logic.
        """
        submit_selectors = self.SELECTORS.get('submit', [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
        ])
        
        for selector in submit_selectors:
            try:
                submit_btn = self.page.locator(selector).first
                if await submit_btn.count() > 0 and await submit_btn.is_enabled():
                    await submit_btn.click()
                    await asyncio.sleep(self.config.post_submit_delay)
                    
                    # Check for success
                    is_success = await self._check_success()
                    
                    if is_success:
                        return ApplicationResult(
                            status=ApplicationStatus.SUBMITTED,
                            message="Application submitted successfully",
                            submitted_at=datetime.now()
                        )
                    else:
                        # Check for errors
                        error = await self._get_error_message()
                        if error:
                            return ApplicationResult(
                                status=ApplicationStatus.ERROR,
                                message=f"Submission error: {error}"
                            )
                    
                    break
            except Exception as e:
                logger.debug(f"Submit failed with {selector}: {e}")
                continue
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message="Could not submit application"
        )
    
    async def _prepare_for_review(self, job: JobPosting) -> ApplicationResult:
        """
        Prepare application for manual review.
        
        Captures screenshot and returns pending status.
        """
        await self._capture_step("review")
        
        return ApplicationResult(
            status=ApplicationStatus.PENDING_REVIEW,
            message="Application prepared for review. Please verify and submit manually.",
            external_url=job.url
        )
    
    async def _check_success(self) -> bool:
        """
        Check if application was successfully submitted.
        
        Override for platform-specific success detection.
        """
        success_selectors = self.SELECTORS.get('success', [
            '.confirmation',
            '.thank-you',
            '[class*="success"]',
        ])
        
        for selector in success_selectors:
            try:
                element = self.page.locator(selector).first
                if await element.count() > 0 and await element.is_visible():
                    return True
            except:
                continue
        
        return False
    
    async def _extract_confirmation_id(self) -> Optional[str]:
        """
        Extract confirmation ID from success page.
        
        Override for platform-specific extraction.
        """
        import re
        
        patterns = [
            r'confirmation\s*[#:]?\s*([A-Z0-9\-]+)',
            r'reference\s*[#:]?\s*([A-Z0-9\-]+)',
            r'application\s*[#:]?\s*([A-Z0-9\-]{5,})',
        ]
        
        try:
            text = await self.page.inner_text('body')
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    return matches[0].strip()
        except:
            pass
        
        return None
    
    async def _get_error_message(self) -> Optional[str]:
        """Get error message from page if present."""
        error_selectors = self.SELECTORS.get('error', [
            '.error-message',
            '.validation-error',
            '[role="alert"]',
        ])
        
        for selector in error_selectors:
            try:
                element = self.page.locator(selector).first
                if await element.count() > 0 and await element.is_visible():
                    return await element.inner_text()
            except:
                continue
        
        return None
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    async def _create_session(self):
        """Create browser session."""
        self.session = await self.browser_manager.create_stealth_session(
            platform=self.PLATFORM
        )
        self.page = self.session.page
        self.context = self.session.context
    
    async def _cleanup(self):
        """Clean up browser session."""
        if self.session:
            await self.browser_manager.close_session(self.session.session_id)
            self.session = None
            self.page = None
            self.context = None
    
    async def _step(self, label: str, func, *args, **kwargs):
        """Execute a step with screenshot capture."""
        self.step_counter += 1
        logger.info(f"Step {self.step_counter}: {label}")
        
        # Pre-step screenshot
        if self.config.capture_screenshots:
            await self._capture_step(f"{label}_start")
        
        # Execute
        try:
            result = await func(*args, **kwargs)
            
            # Post-step screenshot
            if self.config.capture_screenshots:
                await self._capture_step(label)
            
            return result
        except Exception as e:
            # Error screenshot
            if self.config.capture_screenshots:
                await self._capture_step(f"{label}_error")
            raise
    
    async def _capture_step(self, label: str):
        """Capture screenshot for current step."""
        if not self.page or not self.current_job:
            return
        
        context = ScreenshotContext(
            job_id=self.current_job.id,
            platform=self.PLATFORM,
            step=self.step_counter,
            label=label
        )
        
        await self.screenshots.capture(self.page, context)
    
    def _build_field_mappings(self) -> Dict[str, FieldMapping]:
        """Build FieldMapping objects from SELECTORS dict."""
        from .form_filler import FormFiller
        
        mappings = {}
        for field_name, selectors in self.SELECTORS.items():
            if field_name in ['submit', 'success', 'error', 'apply_button']:
                continue  # Skip non-form selectors
            
            mappings[field_name] = FieldMapping(
                profile_field=field_name,
                selectors=selectors if isinstance(selectors, list) else [selectors]
            )
        
        return mappings
    
    async def human_like_delay(self, min_sec: float = None, max_sec: float = None):
        """Add human-like delay."""
        import random
        min_delay = min_sec or self.config.pre_selector_delay
        max_delay = max_sec or (min_delay + 1)
        await asyncio.sleep(random.uniform(min_delay, max_delay))
    
    # ========================================================================
    # Required Abstract Methods
    # ========================================================================
    
    async def search_jobs(self, criteria) -> List[JobPosting]:
        """Search for jobs - must implement in subclass."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement search_jobs()")
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get job details - must implement in subclass."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement get_job_details()")


# Example minimal adapter implementation:
class ExampleMinimalAdapter(UnifiedJobAdapter):
    """
    Example of how simple an adapter can be with UnifiedJobAdapter.
    
    Just define:
    - PLATFORM
    - SELECTORS
    - _navigate_to_application()
    
    Everything else is handled by the base class!
    """
    
    PLATFORM = "example"
    PLATFORM_TYPE = PlatformType.EXTERNAL
    
    SELECTORS = {
        'first_name': ['#first_name', 'input[name="firstName"]'],
        'last_name': ['#last_name', 'input[name="lastName"]'],
        'email': ['#email', 'input[type="email"]'],
        'submit': ['#submit', 'button[type="submit"]'],
        'success': ['.confirmation', '.thank-you'],
    }
    
    async def _navigate_to_application(self, job: JobPosting):
        """Navigate to application form."""
        await self.page.goto(job.url)
        # Click apply if needed
        apply_btn = self.page.locator('#apply_button')
        if await apply_btn.count() > 0:
            await apply_btn.click()
            await self.page.wait_for_load_state('networkidle')
    
    async def search_jobs(self, criteria) -> List[JobPosting]:
        """Search for jobs."""
        return []  # Implement if platform supports search
    
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get job details."""
        return JobPosting(
            id="example_job",
            platform=self.PLATFORM_TYPE,
            title="Example Job",
            company="Example Co",
            location="Remote",
            url=job_url
        )
