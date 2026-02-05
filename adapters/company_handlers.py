"""
Company-Specific Application Handlers

Handles ATS platforms for specific companies with custom implementations.
Each company may have unique Workday configurations, login flows, or form layouts.
"""

import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import Page, BrowserContext

from adapters.base import JobPosting, ApplicationResult, ApplicationStatus, UserProfile, Resume
from browser.stealth_manager import StealthBrowserManager

logger = logging.getLogger(__name__)


@dataclass
class CompanyConfig:
    """Configuration for a specific company's ATS."""
    name: str
    domain_patterns: List[str]
    ats_type: str  # 'workday', 'custom', etc.
    selectors: Dict[str, str]
    requires_login: bool = False
    multi_step: bool = True
    has_captcha: bool = False


# Company-specific configurations
COMPANY_CONFIGS = {
    'salesforce': CompanyConfig(
        name='Salesforce',
        domain_patterns=['careers.salesforce.com', 'salesforce.wd12.myworkdayjobs.com'],
        ats_type='workday',
        selectors={
            'apply_button': 'button[data-automation-id="applyButton"], a:has-text("Apply")',
            'first_name': 'input[data-automation-id="legalNameSection_firstName"], input[name="firstName"]',
            'last_name': 'input[data-automation-id="legalNameSection_lastName"], input[name="lastName"]',
            'email': 'input[data-automation-id="email"], input[type="email"]',
            'phone': 'input[data-automation-id="phone"], input[type="tel"]',
            'resume_upload': 'input[type="file"][data-automation-id="resumeUpload"], input[type="file"]',
            'next_button': 'button[data-automation-id="bottom-navigation-next-button"], button:has-text("Next")',
            'submit_button': 'button[data-automation-id="submitButton"], button:has-text("Submit")',
            'success_indicator': '[data-automation-id="applicationConfirmation"], .confirmation-message',
        },
        requires_login=False,
        multi_step=True,
    ),
    
    'adobe': CompanyConfig(
        name='Adobe',
        domain_patterns=['careers.adobe.com'],
        ats_type='workday',
        selectors={
            'apply_button': 'button:has-text("Apply"), a:has-text("Apply")',
            'first_name': 'input[name="firstName"], input[placeholder*="First"]',
            'last_name': 'input[name="lastName"], input[placeholder*="Last"]',
            'email': 'input[name="email"], input[type="email"]',
            'phone': 'input[name="phone"], input[type="tel"]',
            'resume_upload': 'input[type="file"]',
            'next_button': 'button:has-text("Next"), button:has-text("Continue")',
            'submit_button': 'button[type="submit"], button:has-text("Submit")',
            'success_indicator': '.confirmation, .thank-you, [class*="success"]',
        },
        requires_login=False,
        multi_step=True,
    ),
    
    'microsoft': CompanyConfig(
        name='Microsoft',
        domain_patterns=['careers.microsoft.com'],
        ats_type='workday',
        selectors={
            'apply_button': 'button:has-text("Apply"), a:has-text("Apply")',
            'first_name': 'input[name="firstName"], input[data-testid="firstName"]',
            'last_name': 'input[name="lastName"], input[data-testid="lastName"]',
            'email': 'input[name="email"], input[type="email"]',
            'phone': 'input[name="phone"], input[type="tel"]',
            'resume_upload': 'input[type="file"]',
            'next_button': 'button:has-text("Next")',
            'submit_button': 'button:has-text("Submit")',
            'success_indicator': '.confirmation, .success-message',
        },
        requires_login=False,
        multi_step=True,
    ),
    
    'hubspot': CompanyConfig(
        name='HubSpot',
        domain_patterns=['hubspot.com/careers'],
        ats_type='greenhouse',
        selectors={
            'apply_button': '#apply_button, .apply-button',
            'first_name': '#first_name',
            'last_name': '#last_name',
            'email': '#email',
            'phone': '#phone',
            'resume_upload': 'input[type="file"]',
            'submit_button': '#submit_app, button[type="submit"]',
            'success_indicator': '.thank-you, .confirmation',
        },
        requires_login=False,
        multi_step=False,
    ),
}


class CompanySpecificHandler:
    """
    Handler for company-specific ATS implementations.
    
    Usage:
        handler = CompanySpecificHandler(browser_manager)
        result = await handler.apply(job, resume, profile, auto_submit=True)
    """
    
    def __init__(self, browser_manager: StealthBrowserManager):
        self.browser = browser_manager
        self.config: Optional[CompanyConfig] = None
        self.page: Optional[Page] = None
        self.context: Optional[BrowserContext] = None
    
    def detect_company(self, url: str) -> Optional[str]:
        """Detect company from URL."""
        url_lower = url.lower()
        
        for company_id, config in COMPANY_CONFIGS.items():
            for pattern in config.domain_patterns:
                if pattern.lower() in url_lower:
                    logger.info(f"Detected company: {config.name}")
                    return company_id
        
        return None
    
    async def apply(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        Apply to a job using company-specific handling.
        
        Args:
            job: Job posting
            resume: Resume to use
            profile: User profile information
            auto_submit: Whether to auto-submit or stop for review
            
        Returns:
            ApplicationResult with status and details
        """
        # Detect company
        company_id = self.detect_company(job.url)
        
        if not company_id:
            logger.warning(f"No company-specific handler for {job.url}")
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message="Company not recognized"
            )
        
        self.config = COMPANY_CONFIGS[company_id]
        
        logger.info(f"🎯 Using {self.config.name} handler ({self.config.ats_type})")
        
        # Create browser session
        session = await self.browser.create_stealth_session(
            platform=f"{company_id}_{self.config.ats_type}"
        )
        self.page = session.page
        self.context = session.context
        
        try:
            # Navigate to job
            await self.page.goto(job.url, timeout=60000)
            await self.page.wait_for_load_state('networkidle')
            
            # Handle based on ATS type
            if self.config.ats_type == 'workday':
                return await self._handle_workday(job, resume, profile, auto_submit)
            elif self.config.ats_type == 'greenhouse':
                return await self._handle_greenhouse(job, resume, profile, auto_submit)
            else:
                return await self._handle_generic(job, resume, profile, auto_submit)
                
        except Exception as e:
            logger.error(f"❌ Error applying to {job.company}: {e}")
            
            # Capture error screenshot
            try:
                screenshot_path = f"/tmp/company_handlers/{company_id}_error_{job.id}.png"
                Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
                await self.page.screenshot(path=screenshot_path, full_page=True)
            except:
                screenshot_path = None
            
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=str(e)[:200],
                screenshot_path=screenshot_path
            )
        
        finally:
            await self.browser.close_session(session.session_id)
    
    async def _handle_workday(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool
    ) -> ApplicationResult:
        """Handle Workday-based applications."""
        selectors = self.config.selectors
        
        # Check if this is a search page (not direct job URL)
        if 'search=' in job.url or 'jobs?' in job.url:
            logger.info("Detected search page, looking for job listings...")
            # Try to find and click on first job
            try:
                # Common job link selectors
                job_links = [
                    'a[href*="/job/"]',
                    'a[data-automation-id="jobTitle"]',
                    'a:has-text("Apply")',
                    '.job-listing a',
                    '[data-automation-id="jobListing"] a'
                ]
                for link_sel in job_links:
                    try:
                        job_link = self.page.locator(link_sel).first
                        if await job_link.count() > 0:
                            await job_link.click(timeout=10000)
                            await asyncio.sleep(3)
                            logger.info("Clicked on job listing")
                            break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"Could not find job listing: {e}")
        
        # Wait for page to settle
        await asyncio.sleep(3)
        
        # Try multiple apply button selectors
        apply_selectors = [
            selectors.get('apply_button', ''),
            'button[data-automation-id="applyButton"]',
            'a:has-text("Apply")',
            'button:has-text("Apply")',
            '[data-testid="apply-button"]',
            '.apply-button',
            'a[href*="/apply/"]'
        ]
        
        apply_clicked = False
        for sel in apply_selectors:
            if not sel:
                continue
            try:
                apply_btn = self.page.locator(sel).first
                if await apply_btn.count() > 0 and await apply_btn.is_visible():
                    await apply_btn.click(timeout=10000)
                    await asyncio.sleep(5)  # Wait longer for navigation/modal
                    logger.info(f"Clicked apply button with: {sel}")
                    apply_clicked = True
                    break
            except Exception as e:
                logger.debug(f"Selector {sel} failed: {e}")
                continue
        
        if not apply_clicked:
            logger.warning("Could not find apply button")
        
        # Handle iframe (common in Workday)
        try:
            # Check if there's an iframe and switch to it
            frames = self.page.frames
            if len(frames) > 1:
                logger.info(f"Found {len(frames)} frames, checking for application form...")
                for i, frame in enumerate(frames):
                    try:
                        # Try to find form in iframe
                        has_form = await frame.locator('input[name="firstName"]').count() > 0
                        if has_form:
                            logger.info(f"Found form in frame {i}")
                            # Note: We need to use this frame for subsequent operations
                            self.page = frame
                            break
                    except:
                        continue
        except Exception as e:
            logger.debug(f"Frame handling failed: {e}")
        
        # Handle new tab/popup
        try:
            # Wait a bit for any new tabs
            await asyncio.sleep(3)
            pages = self.context.pages
            if len(pages) > 1:
                logger.info(f"Multiple tabs detected ({len(pages)}), switching to newest...")
                self.page = pages[-1]  # Switch to newest tab
        except Exception as e:
            logger.debug(f"Tab switching failed: {e}")
        
        # Wait for form with multiple selector attempts
        form_found = False
        form_selectors = [
            selectors.get('first_name', ''),
            selectors.get('email', ''),
            'input[name="firstName"]',
            'input[name="email"]',
            'input[type="email"]',
            'input[data-automation-id*="firstName"]', 
            '[data-automation-id="legalNameSection_firstName"]',
            'input[placeholder*="First" i]',  # Case insensitive
            'input[placeholder*="Email" i]',
            'form input',  # Any input in a form
            'input[required]',  # Required inputs
        ]
        
        for sel in form_selectors:
            if not sel:
                continue
            try:
                # Check if visible, not just present
                element = self.page.locator(sel).first
                if await element.count() > 0:
                    is_visible = await element.is_visible()
                    if is_visible:
                        form_found = True
                        logger.info(f"Form found with selector: {sel}")
                        break
            except Exception as e:
                logger.debug(f"Selector {sel} not found: {e}")
                continue
        
        if not form_found:
            # Try to detect what's actually on the page
            logger.warning("Could not find standard application form")
            
            # Take screenshot for debugging
            screenshot = await self._capture_screenshot(job.id, 'no_form')
            
            # Check if there's a login prompt
            login_keywords = ['sign in', 'login', 'create account', 'register']
            page_text = await self.page.inner_text('body').lower()
            if any(kw in page_text for kw in login_keywords):
                logger.info("Login required for this application")
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message=f"Login required for {job.company} application",
                    external_url=job.url,
                    screenshot_path=screenshot
                )
            
            # Check for external redirect
            current_url = self.page.url
            if 'workday' in current_url or 'myworkday' in current_url:
                logger.info(f"Redirected to Workday: {current_url}")
                # Continue anyway - might be able to fill
                form_found = True
            else:
                return ApplicationResult(
                    status=ApplicationStatus.PENDING_REVIEW,
                    message=f"Could not find application form for {job.company}. Manual review needed.",
                    external_url=job.url,
                    screenshot_path=screenshot
                )
        
        # Fill basic info with multiple selector attempts
        await self._fill_field_with_fallbacks('first_name', profile.first_name, [
            selectors.get('first_name', ''),
            'input[name="firstName"]',
            'input[data-automation-id*="firstName"]',
            '[data-automation-id="legalNameSection_firstName"]'
        ])
        
        await self._fill_field_with_fallbacks('last_name', profile.last_name, [
            selectors.get('last_name', ''),
            'input[name="lastName"]',
            'input[data-automation-id*="lastName"]',
            '[data-automation-id="legalNameSection_lastName"]'
        ])
        
        await self._fill_field_with_fallbacks('email', profile.email, [
            selectors.get('email', ''),
            'input[type="email"]',
            'input[name="email"]',
            'input[data-automation-id*="email"]'
        ])
        
        await self._fill_field_with_fallbacks('phone', profile.phone, [
            selectors.get('phone', ''),
            'input[type="tel"]',
            'input[name="phone"]',
            'input[data-automation-id*="phone"]'
        ])
        
        # Upload resume
        try:
            file_input = self.page.locator(selectors['resume_upload']).first
            if await file_input.count() > 0:
                await file_input.set_input_files(resume.file_path)
                await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"Could not upload resume: {e}")
        
        # Handle multi-step forms
        if self.config.multi_step:
            max_steps = 10
            for step in range(max_steps):
                # Check for submit button (final step)
                submit_btn = self.page.locator(selectors['submit_button']).first
                if await submit_btn.count() > 0 and await submit_btn.is_visible():
                    if auto_submit:
                        await submit_btn.click()
                        await asyncio.sleep(3)
                        
                        # Check for success
                        success = await self._check_success(selectors['success_indicator'])
                        if success:
                            return ApplicationResult(
                                status=ApplicationStatus.SUBMITTED,
                                message=f"Application submitted to {job.company}",
                                confirmation_id=await self._extract_confirmation()
                            )
                    else:
                        # Review mode - capture screenshot and return
                        screenshot_path = await self._capture_screenshot(job.id, 'review')
                        return ApplicationResult(
                            status=ApplicationStatus.PENDING_REVIEW,
                            message=f"Application ready for review at {job.company}",
                            external_url=job.url,
                            screenshot_path=screenshot_path
                        )
                
                # Click next
                next_btn = self.page.locator(selectors['next_button']).first
                if await next_btn.count() > 0 and await next_btn.is_enabled():
                    await next_btn.click()
                    await asyncio.sleep(2)
                else:
                    break
        
        # If we get here, form wasn't submitted
        screenshot_path = await self._capture_screenshot(job.id, 'incomplete')
        return ApplicationResult(
            status=ApplicationStatus.PENDING_REVIEW,
            message=f"Application form filled, manual submission needed for {job.company}",
            external_url=job.url,
            screenshot_path=screenshot_path
        )
    
    async def _handle_greenhouse(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool
    ) -> ApplicationResult:
        """Handle Greenhouse-based applications."""
        selectors = self.config.selectors
        
        # Click apply
        try:
            apply_btn = self.page.locator(selectors['apply_button']).first
            await apply_btn.click(timeout=10000)
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"Could not click apply: {e}")
        
        # Fill form
        await self.page.fill(selectors['first_name'], profile.first_name)
        await self.page.fill(selectors['last_name'], profile.last_name)
        await self.page.fill(selectors['email'], profile.email)
        await self.page.fill(selectors['phone'], profile.phone)
        
        # Upload resume
        try:
            await self.page.set_input_files(selectors['resume_upload'], resume.file_path)
        except Exception as e:
            logger.warning(f"Could not upload resume: {e}")
        
        # Submit or review
        if auto_submit:
            await self.page.click(selectors['submit_button'])
            await asyncio.sleep(3)
            
            success = await self._check_success(selectors['success_indicator'])
            if success:
                return ApplicationResult(
                    status=ApplicationStatus.SUBMITTED,
                    message=f"Application submitted to {job.company}"
                )
        
        screenshot_path = await self._capture_screenshot(job.id, 'filled')
        return ApplicationResult(
            status=ApplicationStatus.PENDING_REVIEW,
            message=f"Form filled for {job.company}",
            screenshot_path=screenshot_path
        )
    
    async def _handle_generic(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool
    ) -> ApplicationResult:
        """Handle generic applications."""
        # Capture initial screenshot
        screenshot_path = await self._capture_screenshot(job.id, 'initial')
        
        return ApplicationResult(
            status=ApplicationStatus.PENDING_REVIEW,
            message=f"Generic handler for {job.company} - manual application needed",
            external_url=job.url,
            screenshot_path=screenshot_path
        )
    
    async def _fill_field(self, selector: str, value: str):
        """Fill a form field with retry."""
        if not value:
            return
        
        try:
            field = self.page.locator(selector).first
            if await field.count() > 0:
                await field.fill(value)
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.debug(f"Could not fill field {selector}: {e}")
    
    async def _fill_field_with_fallbacks(self, field_name: str, value: str, selectors: list):
        """Fill a field trying multiple selectors."""
        if not value:
            return
        
        for selector in selectors:
            if not selector:
                continue
            try:
                field = self.page.locator(selector).first
                if await field.count() > 0 and await field.is_visible():
                    await field.fill(value)
                    await asyncio.sleep(0.5)
                    logger.debug(f"Filled {field_name} with selector: {selector}")
                    return
            except Exception as e:
                logger.debug(f"Selector {selector} failed for {field_name}: {e}")
                continue
        
        logger.warning(f"Could not fill field {field_name} with any selector")
    
    async def _check_success(self, selector: str) -> bool:
        """Check if application was successful."""
        try:
            element = self.page.locator(selector).first
            return await element.count() > 0 and await element.is_visible()
        except:
            return False
    
    async def _extract_confirmation(self) -> Optional[str]:
        """Extract confirmation ID from page."""
        import re
        
        try:
            text = await self.page.inner_text('body')
            patterns = [
                r'confirmation\s*[#:]?\s*([A-Z0-9\-]+)',
                r'reference\s*[#:]?\s*([A-Z0-9\-]+)',
                r'application\s*[#:]?\s*([A-Z0-9\-]{5,})',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    return matches[0]
        except:
            pass
        return None
    
    async def _capture_screenshot(self, job_id: str, label: str) -> str:
        """Capture screenshot and return path."""
        screenshot_dir = Path("/tmp/company_handlers")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = asyncio.get_event_loop().time()
        path = screenshot_dir / f"{self.config.name.lower()}_{job_id}_{label}_{int(timestamp)}.png"
        
        try:
            await self.page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None


# Test function
async def test_company_handler():
    """Test the company-specific handler."""
    from adapters.base import UserProfile, Resume
    
    browser = StealthBrowserManager()
    handler = CompanySpecificHandler(browser)
    
    # Test detection
    test_urls = [
        'https://careers.salesforce.com/jobs/123',
        'https://careers.adobe.com/us/en/job/R123',
        'https://hubspot.com/careers/jobs/123',
    ]
    
    for url in test_urls:
        company = handler.detect_company(url)
        print(f"{company or 'unknown':15s} <- {url[:50]}...")


if __name__ == "__main__":
    asyncio.run(test_company_handler())
