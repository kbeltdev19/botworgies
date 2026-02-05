"""
Optimized Indeed Adapter with Retry Logic, CAPTCHA Handling, and A/B Testing
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from adapters.base import JobPlatformAdapter, JobPosting, ApplicationResult, ApplicationStatus
from api.captcha_solver import CaptchaDetector, CaptchaSolver, CaptchaType
from api.form_retry_handler import FormRetryHandler, FormSubmissionError, RetryReason
from api.ab_testing import get_ab_test_manager, SpeedVariant
from api.proxy_manager import PlatformProxyStrategy, ResidentialProxyManager

logger = logging.getLogger(__name__)


class IndeedOptimizedAdapter(JobPlatformAdapter):
    """
    Indeed adapter with all optimizations:
    - CAPTCHA solving
    - Form validation retry
    - Residential proxies
    - A/B tested speeds
    """
    
    def __init__(self, browser_manager, session_cookie: Optional[str] = None):
        super().__init__(browser_manager, session_cookie)
        self.retry_handler = FormRetryHandler()
        self.captcha_solver = None
        self.proxy_strategy = None
        self.ab_manager = get_ab_test_manager()
        self.variant: Optional[SpeedVariant] = None
        self.speed_config = None
        
    async def initialize(self):
        """Initialize with CAPTCHA solver and proxy strategy."""
        self.captcha_solver = CaptchaSolver(provider="capsolver")
        proxy_manager = ResidentialProxyManager()
        self.proxy_strategy = PlatformProxyStrategy(proxy_manager)
        
        # Assign A/B test variant
        self.variant = self.ab_manager.assign_variant("indeed_optimized")
        self.speed_config = self.ab_manager.get_config(self.variant)
        
        logger.info(f"IndeedOptimized initialized with variant: {self.variant.value}")
        logger.info(f"Target speed: {self.speed_config.target_apps_per_minute} apps/min")
        
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Any,
        profile: Any,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        Apply to a job on Indeed with full optimization.
        """
        await self.initialize()
        
        operation_id = f"indeed_{job.id}_{datetime.now().timestamp()}"
        
        # Get optimized proxy
        proxy = self.proxy_strategy.get_proxy_for_platform("indeed")
        
        async def submit_application():
            """Main submission logic with retry."""
            return await self._execute_application(
                job, resume, profile, cover_letter, auto_submit, proxy
            )
        
        async def validate_result(result):
            """Validate application result."""
            if result.status != ApplicationStatus.COMPLETED:
                return False, result.message
            return True, ""
        
        # Execute with retry logic
        retry_result = await self.retry_handler.execute_with_retry(
            operation_id=operation_id,
            submit_func=submit_application,
            validate_func=validate_result
        )
        
        # Record A/B test result
        success = retry_result["success"]
        self.ab_manager.record_result(
            self.variant,
            success=success,
            error_type=retry_result.get("error_type") if not success else None
        )
        
        if retry_result["success"]:
            return retry_result["result"]
        else:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=retry_result.get("error", "Unknown error"),
                platform="indeed"
            )
    
    async def _execute_application(
        self,
        job: JobPosting,
        resume: Any,
        profile: Any,
        cover_letter: Optional[str],
        auto_submit: bool,
        proxy: Optional[Any]
    ) -> ApplicationResult:
        """Execute the actual application logic."""
        
        # Create browser session with proxy
        session = await self.browser_manager.create_session(
            proxy=proxy.to_playwright_format() if proxy else None
        )
        
        try:
            page = session["page"]
            
            # Navigate to job
            await page.goto(job.url, wait_until="networkidle")
            
            # Check for CAPTCHA
            has_captcha, captcha_type = await self._detect_captcha(page)
            if has_captcha:
                logger.warning(f"CAPTCHA detected: {captcha_type}")
                solved = await self._solve_captcha(page, captcha_type)
                if not solved:
                    raise FormSubmissionError(
                        "Failed to solve CAPTCHA",
                        RetryReason.NETWORK_ERROR
                    )
            
            # Click apply button
            apply_btn = await page.query_selector('[data-testid="apply-button"], .apply-button, button:has-text("Apply")')
            if apply_btn:
                await apply_btn.click()
                await asyncio.sleep(self.speed_config.click_delay_ms / 1000)
            
            # Fill form with human-like delays
            await self._fill_form_with_delays(page, profile, resume)
            
            # Upload resume
            if resume:
                await self._upload_resume_with_retry(page, resume)
            
            # Fill cover letter
            if cover_letter:
                await self._fill_cover_letter(page, cover_letter)
            
            # Submit or stop
            if auto_submit:
                submit_btn = await page.query_selector('button[type="submit"], button:has-text("Submit")')
                if submit_btn:
                    await submit_btn.click()
                    await page.wait_for_load_state("networkidle")
            
            # Verify success
            success_indicators = [
                "application submitted",
                "thank you for applying",
                "we received your application",
                "success"
            ]
            
            content = await page.content()
            content_lower = content.lower()
            
            for indicator in success_indicators:
                if indicator in content_lower:
                    return ApplicationResult(
                        status=ApplicationStatus.COMPLETED,
                        message="Application submitted successfully",
                        platform="indeed",
                        screenshot_path=await self._take_screenshot(page)
                    )
            
            # Check for errors
            error_indicators = [
                "error occurred",
                "please try again",
                "invalid",
                "required field"
            ]
            
            for indicator in error_indicators:
                if indicator in content_lower:
                    raise FormSubmissionError(
                        f"Form error detected: {indicator}",
                        RetryReason.VALIDATION_ERROR
                    )
            
            return ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="Application filled but submission status unclear",
                platform="indeed"
            )
            
        except Exception as e:
            logger.error(f"Application error: {e}")
            raise
        finally:
            await self.browser_manager.close_session(session["id"])
    
    async def _detect_captcha(self, page) -> tuple:
        """Detect if CAPTCHA is present."""
        content = await page.content()
        return CaptchaDetector.detect_in_html(content)
    
    async def _solve_captcha(self, page, captcha_type: CaptchaType) -> bool:
        """Attempt to solve CAPTCHA."""
        try:
            html = await page.content()
            site_key = CaptchaDetector.detect_site_key(html, captcha_type)
            
            if not site_key:
                logger.warning("Could not extract site key")
                return False
            
            url = page.url
            
            async with self.captcha_solver as solver:
                if captcha_type == CaptchaType.RECAPTCHA_V2:
                    result = await solver.solve_recaptcha_v2(site_key, url)
                elif captcha_type == CaptchaType.HCAPTCHA:
                    result = await solver.solve_hcaptcha(site_key, url)
                else:
                    return False
                
                if result.success:
                    # Inject solution into page
                    await page.evaluate(f"""
                        document.getElementById('g-recaptcha-response').innerHTML = '{result.token}';
                        if (typeof grecaptcha !== 'undefined') {{
                            grecaptcha.getResponse = function() {{ return '{result.token}'; }};
                        }}
                    """)
                    logger.info(f"CAPTCHA solved in {result.solve_time_seconds:.1f}s")
                    return True
                else:
                    logger.error(f"CAPTCHA solve failed: {result.error_message}")
                    return False
                    
        except Exception as e:
            logger.error(f"CAPTCHA solving error: {e}")
            return False
    
    async def _fill_form_with_delays(self, page, profile, resume):
        """Fill form fields with human-like delays."""
        fields = {
            "firstName": profile.first_name,
            "lastName": profile.last_name,
            "email": profile.email,
            "phone": profile.phone,
        }
        
        for field_name, value in fields.items():
            selector = f'input[name="{field_name}"], input[id="{field_name}"]'
            field = await page.query_selector(selector)
            
            if field and value:
                await field.click()
                await asyncio.sleep(self.speed_config.click_delay_ms / 1000)
                
                # Type with human speed
                for char in value:
                    await field.type(char, delay=self.speed_config.typing_speed_wpm / 60 * 100)
                
                await asyncio.sleep(self.speed_config.mouse_movement_delay_ms / 1000)
    
    async def _upload_resume_with_retry(self, page, resume):
        """Upload resume with retry logic."""
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                input_selector = 'input[type="file"][accept*=".pdf"], input[name="resume"]'
                file_input = await page.query_selector(input_selector)
                
                if file_input:
                    await file_input.set_input_files(resume.file_path)
                    await asyncio.sleep(1)  # Wait for upload
                    
                    # Verify upload
                    uploaded = await page.query_selector('.upload-success, .file-uploaded')
                    if uploaded:
                        return True
                
                return False
                
            except Exception as e:
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise FormSubmissionError(
                        f"Resume upload failed: {e}",
                        RetryReason.NETWORK_ERROR
                    )
    
    async def _fill_cover_letter(self, page, cover_letter):
        """Fill cover letter field."""
        selectors = [
            'textarea[name="coverLetter"]',
            'textarea[name="message"]',
            'textarea[placeholder*="cover letter" i]'
        ]
        
        for selector in selectors:
            field = await page.query_selector(selector)
            if field:
                await field.fill(cover_letter)
                break
    
    async def _take_screenshot(self, page) -> str:
        """Take screenshot for verification."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"screenshots/indeed_{timestamp}.png"
        await page.screenshot(path=path)
        return path
