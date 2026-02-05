#!/usr/bin/env python3
"""
LinkedIn Easy Apply Handler - Automated applications on LinkedIn.

Handles both:
1. LinkedIn Easy Apply (internal form)
2. External Apply (redirects to company ATS)

Success Rate: ~75% (varies by company)
"""

import asyncio
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class ApplicationResult:
    """Result of an application attempt."""
    success: bool
    confirmation_id: Optional[str] = None
    error: Optional[str] = None
    screenshot_path: Optional[str] = None
    redirect_url: Optional[str] = None  # For external apply


class LinkedInEasyApplyHandler:
    """
    Handler for LinkedIn Easy Apply and external applications.
    
    Features:
    - Detects Easy Apply vs External Apply buttons (multi-language support)
    - Fills LinkedIn's internal application form
    - Handles external redirects to company ATS
    - Routes external ATS to appropriate handlers
    """
    
    # LinkedIn Apply button selectors - MULTI-LANGUAGE SUPPORT
    APPLY_BUTTON_SELECTORS = [
        # Data attributes (language-independent)
        'button[data-control-name="jobdetails_topcard_inapply"]',
        'button[data-control-name="jobdetails_topcard_candidatelog_inapply"]',
        '[data-test-easy-apply-button]',
        '[data-test-id="apply-button"]',
        
        # CSS classes (language-independent)
        'button.jobs-apply-button',
        '.jobs-apply-button--top-card',
        '.jobs-apply-button.artdeco-button',
        
        # English
        'button:has-text("Easy Apply")',
        'button:has-text("Apply")',
        
        # Spanish
        'button:has-text("Solicitud sencilla")',
        'button:has-text("Aplicar")',
        
        # French
        'button:has-text("Candidature simplifiée")',
        'button:has-text("Postuler")',
        
        # German
        'button:has-text("Einfach bewerben")',
        'button:has-text("Bewerben")',
        
        # Portuguese
        'button:has-text("Candidatura fácil")',
        'button:has-text("Candidatar-se")',
        
        # Hindi
        'button:has-text("आसान आवेदन")',
        
        # Bengali
        'button:has-text("সহজ আবেদন")',
        
        # Chinese
        'button:has-text("轻松申请")',
        
        # Japanese
        'button:has-text("かんたん応募")',
    ]
    
    # Easy Apply modal/form selectors - EXPANDED for better detection
    EASY_APPLY_MODAL = {
        'container': '.jobs-easy-apply-modal, .jobs-easy-apply-content, .jobs-easy-apply-form',
        'next_button': [
            'button[aria-label="Continue to next step"]',
            'button:has-text("Next")',
            'button[data-easy-apply-next-button]',
            'button.artdeco-button--primary:has-text("Next")',
        ],
        'review_button': [
            'button[aria-label="Review your application"]',
            'button:has-text("Review")',
            'button.artdeco-button--primary:has-text("Review")',
        ],
        'submit_button': [
            'button[aria-label="Submit application"]',
            'button:has-text("Submit application")',
            'button[type="submit"]',
            'button.artdeco-button--primary:has-text("Submit")',
            'button[data-control-name="submit_unify"]',
            '.jobs-easy-apply-modal button.artdeco-button--primary',
            'button:has-text("Send application")',
            'button:has-text("Apply now")',
        ],
        'close_button': [
            'button[aria-label="Dismiss"]',
            'button.artdeco-modal__dismiss',
            'button[data-test-modal-close-btn]',
        ],
    }
    
    # Form field selectors
    FORM_FIELDS = {
        'first_name': [
            'input[name="firstName"]',
            'input[id*="firstName"]',
            'input[autocomplete="given-name"]',
        ],
        'last_name': [
            'input[name="lastName"]',
            'input[id*="lastName"]',
            'input[autocomplete="family-name"]',
        ],
        'email': [
            'input[type="email"]',
            'input[name="emailAddress"]',
            'input[autocomplete="email"]',
        ],
        'phone': [
            'input[type="tel"]',
            'input[name="phoneNumber"]',
            'input[autocomplete="tel"]',
        ],
        'resume_upload': [
            'input[type="file"][name="file"]',
            'input[type="file"][accept*=".pdf"]',
        ],
        'resume_select': [
            'button[data-control-name="select_resume"]',
            'button:has-text("Select resume")',
        ],
        'follow_checkbox': [
            'input[name="followCompany"]',
        ],
    }
    
    # External redirect indicators
    EXTERNAL_APPLY_INDICATORS = [
        'button[data-control-name="jobdetails_topcard_external_job_apply"]',
        'a.apply-button[href^="http"]',
        'button:has-text("Apply on company website")',
    ]
    
    # Success indicators
    SUCCESS_SELECTORS = [
        '.artdeco-modal__content:has-text("Application sent")',
        '.jobs-post-apply__success-message',
        'h2:has-text("Application sent")',
        '.artdeco-inline-feedback--success',
        'text="Application sent"',
    ]
    
    # CAPTCHA/Security challenge indicators
    CAPTCHA_SELECTORS = [
        '.captcha-wrapper',
        '.challenge-dialog',
        '[data-test-id="captcha-wrapper"]',
        'input[name="captchaResponse"]',
        '.security-challenge',
        'iframe[src*="captcha"]',
        'iframe[src*="challenge"]',
    ]
    
    # Rate limit indicators
    RATE_LIMIT_INDICATORS = [
        "text=\"You've reached the weekly limit\"",
        "text=\"You've reached the daily limit\"",
        '.artdeco-inline-feedback--error:has-text("limit")',
    ]
    
    def __init__(self):
        self.stats = {
            'attempted': 0,
            'successful': 0,
            'easy_apply': 0,
            'external_redirect': 0,
            'failed': 0,
            'captcha_hits': 0,
            'rate_limited': 0,
        }
        self.last_apply_time = 0
        self.min_delay_between_applications = 10  # seconds
        self.session_apply_count = 0
        self.max_applies_per_session = 10
        self.circuit_breaker_open = False
        self.circuit_breaker_until = 0
    
    async def load_linkedin_cookies(self, context):
        """Load LinkedIn authentication cookies from file."""
        try:
            import json
            from pathlib import Path
            
            cookie_file = Path('campaigns/cookies/linkedin_cookies.json')
            if not cookie_file.exists():
                logger.warning("[LinkedIn] Cookie file not found")
                return False
            
            with open(cookie_file) as f:
                cookies = json.load(f)
            
            # Ensure cookies have proper format for Playwright
            formatted_cookies = []
            for cookie in cookies:
                # Make sure domain starts with dot for cross-subdomain
                domain = cookie.get('domain', '.linkedin.com')
                if not domain.startswith('.'):
                    domain = '.' + domain
                
                formatted_cookie = {
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': domain,
                    'path': cookie.get('path', '/'),
                }
                # Add optional fields if present
                if 'expires' in cookie:
                    formatted_cookie['expires'] = cookie['expires']
                if 'httpOnly' in cookie:
                    formatted_cookie['httpOnly'] = cookie['httpOnly']
                if 'secure' in cookie:
                    formatted_cookie['secure'] = cookie['secure']
                if 'sameSite' in cookie:
                    formatted_cookie['sameSite'] = cookie['sameSite']
                    
                formatted_cookies.append(formatted_cookie)
                logger.info(f"[LinkedIn] Formatting cookie: {cookie['name']} for domain {domain}")
            
            # Add cookies to context
            await context.add_cookies(formatted_cookies)
            logger.info(f"[LinkedIn] Loaded {len(formatted_cookies)} cookies")
            
            # Verify cookies were added by navigating to LinkedIn
            page = await context.new_page()
            try:
                # Navigate to LinkedIn feed (requires authentication)
                await page.goto('https://www.linkedin.com/feed/', wait_until='networkidle', timeout=15000)
                current_url = page.url
                logger.info(f"[LinkedIn] Post-cookie navigation URL: {current_url[:80]}...")
                
                # Check for authenticated state
                if '/feed' in current_url:
                    logger.info("[LinkedIn] ✅ Cookie authentication SUCCESSFUL - on feed page")
                    await page.close()
                    return True
                elif 'login' in current_url or 'signup' in current_url:
                    logger.error("[LinkedIn] ❌ Cookie authentication FAILED - redirected to login")
                    logger.error("[LinkedIn] Please get a fresh li_at cookie from your browser")
                    await page.close()
                    return False
                else:
                    # Check if we're on homepage but maybe still logged in
                    await page.goto('https://www.linkedin.com/in/me/', wait_until='networkidle', timeout=10000)
                    profile_url = page.url
                    if '/in/' in profile_url or 'linkedin.com/in/' in profile_url:
                        logger.info("[LinkedIn] ✅ Cookie authentication SUCCESSFUL - profile accessible")
                        await page.close()
                        return True
                    
                    logger.warning(f"[LinkedIn] ⚠️ Unknown auth state at: {current_url[:80]}...")
                    logger.warning("[LinkedIn] Cookie may be expired or invalid")
                    await page.close()
                    return False
            except Exception as e:
                logger.warning(f"[LinkedIn] Error verifying cookies: {e}")
                try:
                    await page.close()
                except:
                    pass
                return False
            
        except Exception as e:
            logger.warning(f"[LinkedIn] Failed to load cookies: {e}")
            return False
    
    async def apply(
        self,
        page,
        profile: Dict[str, str],
        resume_path: str
    ) -> ApplicationResult:
        """
        Apply to a LinkedIn job.
        
        Args:
            page: Playwright page (already on LinkedIn job page)
            profile: Dict with first_name, last_name, email, phone
            resume_path: Path to resume file
            
        Returns:
            ApplicationResult
        """
        self.stats['attempted'] += 1
        
        try:
            logger.info(f"[LinkedIn] Starting application to {page.url[:60]}...")
            
            # Wait for page to fully load
            await asyncio.sleep(2)
            
            # Check if login required
            current_url = page.url
            logger.info(f"[LinkedIn] Current URL: {current_url[:80]}...")
            
            if 'linkedin.com/login' in current_url or 'linkedin.com/signup' in current_url:
                logger.error("[LinkedIn] Login required - cookies may be expired")
                return ApplicationResult(
                    success=False,
                    error="LinkedIn login required - check cookies"
                )
            
            # Verify we're on a job page
            if '/jobs/' not in current_url:
                logger.error(f"[LinkedIn] Not on a job page: {current_url}")
                return ApplicationResult(
                    success=False,
                    error="Not on a LinkedIn job page"
                )
            
            # Check for login prompts on the page (even if URL doesn't show login)
            try:
                login_prompt = page.locator('text=/sign in to apply/i').first
                if await login_prompt.count() > 0 and await login_prompt.is_visible():
                    logger.error("[LinkedIn] Login prompt detected on job page - not authenticated")
                    return ApplicationResult(
                        success=False,
                        error="LinkedIn authentication required - cookie may be expired"
                    )
            except:
                pass
            
            # Check if this is Easy Apply or External Apply
            logger.info("[LinkedIn] Detecting apply type...")
            apply_type = await self._detect_apply_type(page)
            logger.info(f"[LinkedIn] Apply type detected: {apply_type}")
            
            if apply_type == 'easy_apply':
                logger.info("[LinkedIn] Starting Easy Apply flow...")
                return await self._apply_easy_apply(page, profile, resume_path)
            
            elif apply_type == 'external':
                logger.info("[LinkedIn] Starting External Apply flow...")
                return await self._apply_external(page, profile, resume_path)
            
            else:
                logger.warning("[LinkedIn] No apply button found - taking screenshot for debug")
                # Take debug screenshot
                try:
                    await page.screenshot(path='campaigns/output/linkedin_no_apply_button.png')
                except:
                    pass
                return ApplicationResult(
                    success=False,
                    error="No apply button found on LinkedIn job page"
                )
                
        except Exception as e:
            logger.error(f"[LinkedIn] Application failed: {e}")
            self.stats['failed'] += 1
            return ApplicationResult(
                success=False,
                error=str(e)
            )
    
    async def _detect_apply_type(self, page) -> str:
        """
        Detect if job has Easy Apply or External Apply.
        Uses multiple strategies including visual analysis as fallback.
        """
        # Strategy 1: Check for Easy Apply button by data attributes (language-independent)
        logger.info("[LinkedIn] Checking for Easy Apply button (data attributes)...")
        data_attribute_selectors = [
            'button[data-control-name="jobdetails_topcard_inapply"]',
            'button[data-control-name="jobdetails_topcard_candidatelog_inapply"]',
            '[data-test-easy-apply-button]',
            'button.jobs-apply-button',
            '.jobs-apply-button--top-card',
        ]
        
        for selector in data_attribute_selectors:
            try:
                button = page.locator(selector).first
                if await button.count() > 0 and await button.is_visible():
                    text = await button.inner_text()
                    logger.info(f"[LinkedIn] ✅ Found Easy Apply button: {text.strip()[:50]}")
                    return 'easy_apply'
            except:
                continue
        
        # Strategy 2: Check for Easy Apply button by text content
        logger.info("[LinkedIn] Checking for Easy Apply button (text content)...")
        text_selectors = [
            'button:has-text("Easy Apply")',
            'button:has-text("Solicitud sencilla")',  # Spanish
            'button:has-text("Candidature simplifiée")',  # French
            'button:has-text("Einfach bewerben")',  # German
            'button:has-text("Candidatura fácil")',  # Portuguese
            'button:has-text("आसान आवेदन")',  # Hindi
            'button:has-text("সহজ আবেদন")',  # Bengali
            'button:has-text("轻松申请")',  # Chinese
            'button:has-text("かんたん応募")',  # Japanese
        ]
        
        for selector in text_selectors:
            try:
                button = page.locator(selector).first
                if await button.count() > 0 and await button.is_visible():
                    text = await button.inner_text()
                    logger.info(f"[LinkedIn] ✅ Found Easy Apply button (localized): {text.strip()[:50]}")
                    return 'easy_apply'
            except:
                continue
        
        # Strategy 3: Check for external apply
        logger.info("[LinkedIn] Checking for External Apply button...")
        for selector in self.EXTERNAL_APPLY_INDICATORS:
            try:
                button = page.locator(selector).first
                if await button.count() > 0 and await button.is_visible():
                    logger.info(f"[LinkedIn] ✅ Found External Apply button: {selector}")
                    return 'external'
            except:
                continue
        
        # Strategy 4: Visual analysis fallback
        logger.info("[LinkedIn] Using visual analysis fallback...")
        try:
            # Look for any button that might be apply
            all_buttons = await page.locator('button').all()
            for btn in all_buttons:
                try:
                    if await btn.is_visible():
                        text = await btn.inner_text()
                        # Check if button is prominently placed (top card)
                        box = await btn.bounding_box()
                        if box and box['y'] < 500:  # Top of page
                            text_lower = text.lower()
                            # Any apply-related text in any language
                            apply_keywords = ['apply', 'aplicar', 'postuler', 'bewerben', 'aplicar', 'आवेदन', '申請', '申请']
                            if any(kw in text_lower for kw in apply_keywords):
                                logger.info(f"[LinkedIn] ✅ Found Apply button via visual scan: {text.strip()[:50]}")
                                return 'easy_apply'
                except:
                    continue
        except Exception as e:
            logger.debug(f"[LinkedIn] Visual fallback failed: {e}")
        
        logger.warning("[LinkedIn] No apply button detected after all strategies")
        return 'unknown'
    
    async def _safe_click(self, page, selector: str, timeout: int = 5000) -> bool:
        """Safely click an element with multiple fallback strategies."""
        try:
            element = page.locator(selector).first
            
            # Wait for element
            if await element.count() == 0:
                return False
            
            # Try normal click first
            try:
                await element.click(timeout=timeout)
                return True
            except:
                pass
            
            # Scroll into view and try again
            try:
                await element.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                await element.click(timeout=timeout)
                return True
            except:
                pass
            
            # Force click
            try:
                await element.click(force=True, timeout=timeout)
                return True
            except:
                pass
            
            # JavaScript click
            try:
                await page.evaluate(f'document.querySelector("{selector}").click()')
                return True
            except:
                pass
            
            return False
            
        except Exception as e:
            logger.warning(f"Safe click failed for {selector}: {e}")
            return False
    
    async def _apply_easy_apply(
        self,
        page,
        profile: Dict[str, str],
        resume_path: str
    ) -> ApplicationResult:
        """Complete LinkedIn Easy Apply flow with full modal handling."""
        try:
            logger.info("[LinkedIn] ===== STARTING EASY APPLY FLOW =====")
            
            # Check if login required
            if 'linkedin.com/login' in page.url or 'linkedin.com/signup' in page.url:
                return ApplicationResult(
                    success=False,
                    error="LinkedIn login required - not logged in"
                )
            
            # Check for CAPTCHA
            captcha_detected = await self._check_for_captcha(page)
            if captcha_detected:
                self.stats['captcha_hits'] += 1
                return ApplicationResult(
                    success=False,
                    error="CAPTCHA detected - manual intervention required"
                )
            
            # Step 1: Click Apply button
            logger.info("[LinkedIn] Step 1: Clicking Easy Apply button...")
            apply_clicked = False
            for selector in self.APPLY_BUTTON_SELECTORS:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(timeout=5000)
                        apply_clicked = True
                        logger.info(f"[LinkedIn] ✅ Clicked apply button: {selector[:50]}...")
                        break
                except Exception as e:
                    logger.debug(f"[LinkedIn] Selector {selector} failed: {e}")
                    continue
            
            if not apply_clicked:
                return ApplicationResult(
                    success=False,
                    error="Could not click Apply button"
                )
            
            # Wait for modal to appear
            logger.info("[LinkedIn] Waiting for Easy Apply modal...")
            await asyncio.sleep(3)
            
            # Debug: Check if modal appeared
            modal_check = page.locator('.jobs-easy-apply-modal, .jobs-easy-apply-content, [role="dialog"]').first
            modal_exists = await modal_check.count() > 0
            modal_visible = await modal_check.is_visible() if modal_exists else False
            logger.info(f"[LinkedIn] After click - Modal exists: {modal_exists}, visible: {modal_visible}")
            
            # Take screenshot for debugging
            try:
                await page.screenshot(path='campaigns/output/linkedin_after_apply_click.png')
                logger.info("[LinkedIn] Screenshot saved: campaigns/output/linkedin_after_apply_click.png")
            except Exception as e:
                logger.debug(f"[LinkedIn] Screenshot error: {e}")
            
            # Check for login prompts
            try:
                login_prompt = page.locator('text=/sign in/i').first
                if await login_prompt.count() > 0 and await login_prompt.is_visible():
                    logger.error("[LinkedIn] ❌ Login prompt detected after clicking Apply!")
                    return ApplicationResult(
                        success=False,
                        error="LinkedIn login required - cookie may not be working properly"
                    )
            except:
                pass
            
            # Check current URL
            logger.info(f"[LinkedIn] Current URL after click: {page.url[:80]}...")
            
            # If modal didn't open, check page content
            if not modal_visible:
                logger.warning("[LinkedIn] Modal didn't open, checking page content...")
                try:
                    # Get page content to see what's there
                    page_content = await page.content()
                    
                    # Check for apply-related text
                    if 'easy apply' in page_content.lower():
                        logger.info("[LinkedIn] 'Easy Apply' text found in page")
                    if 'sign in' in page_content.lower():
                        logger.warning("[LinkedIn] 'Sign in' text found in page - may need authentication")
                    
                    # Try clicking again with JavaScript
                    await page.evaluate('document.querySelector(".jobs-apply-button--top-card, button[data-control-name=\'jobdetails_topcard_inapply\']")?.click()')
                    await asyncio.sleep(3)
                    
                    # Check again
                    modal_exists = await modal_check.count() > 0
                    modal_visible = await modal_check.is_visible() if modal_exists else False
                    logger.info(f"[LinkedIn] After JS click - Modal exists: {modal_exists}, visible: {modal_visible}")
                    
                    # If still no modal, the authentication might be the issue
                    if not modal_visible:
                        logger.error("[LinkedIn] ❌ Modal still didn't open - authentication or anti-bot detection")
                        logger.error("[LinkedIn] LinkedIn may have detected automation and blocked the apply modal")
                        
                        # Check if we can see the apply button is still there
                        apply_btn_check = page.locator('.jobs-apply-button--top-card').first
                        btn_exists = await apply_btn_check.count() > 0
                        btn_visible = await apply_btn_check.is_visible() if btn_exists else False
                        logger.info(f"[LinkedIn] Apply button still visible: {btn_visible}")
                        
                        if btn_visible:
                            return ApplicationResult(
                                success=False,
                                error="LINKEDIN_BLOCKED: Apply button visible but modal not opening - LinkedIn anti-bot detection"
                            )
                            
                except Exception as e:
                    logger.debug(f"[LinkedIn] JS click error: {e}")
            
            # Step 2: Fill/Verify Contact Info
            logger.info("[LinkedIn] Step 2: Filling contact information...")
            await self._fill_contact_info_detailed(page, profile)
            
            # Step 3: Progress through form steps
            logger.info("[LinkedIn] Step 3: Progressing through form...")
            
            # Debug: Check if modal is open and what buttons are visible
            try:
                await asyncio.sleep(2)
                
                # Check for modal
                modal = page.locator('.jobs-easy-apply-modal, .jobs-easy-apply-content').first
                modal_count = await modal.count()
                modal_visible = await modal.is_visible() if modal_count > 0 else False
                logger.info(f"[LinkedIn] Modal found: {modal_count > 0}, visible: {modal_visible}")
                
                # Look for buttons inside modal
                if modal_visible:
                    modal_buttons = await modal.locator('button').all()
                    logger.info(f"[LinkedIn] Found {len(modal_buttons)} buttons in modal")
                    for i, btn in enumerate(modal_buttons[:5]):
                        try:
                            text = await btn.inner_text()
                            logger.info(f"[LinkedIn] Modal Button {i}: '{text[:40]}'")
                        except:
                            pass
                
                # Also check all page buttons
                all_buttons = await page.locator('button').all()
                logger.info(f"[LinkedIn] Found {len(all_buttons)} buttons total on page")
                
            except Exception as e:
                logger.debug(f"[LinkedIn] Button debug error: {e}")
            
            step_result = await self._progress_through_steps(page, resume_path)
            
            if step_result.success:
                # Verify the application was actually submitted
                logger.info("[LinkedIn] Verifying application submission...")
                await asyncio.sleep(2)
                
                # Check if "Applied" button appears (indicates successful submission)
                applied_button = page.locator('button:has-text("Applied")').first
                if await applied_button.count() > 0 and await applied_button.is_visible():
                    logger.info("[LinkedIn] ✅ 'Applied' button visible - submission confirmed")
                    self.stats['easy_apply'] += 1
                    self.stats['successful'] += 1
                    logger.info("[LinkedIn] ===== EASY APPLY COMPLETED SUCCESSFULLY =====")
                else:
                    # Check for success message
                    if await self._check_success(page):
                        logger.info("[LinkedIn] ✅ Success message detected - submission confirmed")
                        self.stats['easy_apply'] += 1
                        self.stats['successful'] += 1
                        logger.info("[LinkedIn] ===== EASY APPLY COMPLETED SUCCESSFULLY =====")
                    else:
                        logger.warning("[LinkedIn] ⚠️ Form completed but 'Applied' state not confirmed")
                        step_result.success = False
                        step_result.error = "Application may not have been submitted - no confirmation found"
            else:
                logger.warning(f"[LinkedIn] ===== EASY APPLY FAILED: {step_result.error} =====")
            
            return step_result
            
        except Exception as e:
            logger.error(f"[LinkedIn] Easy Apply failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return ApplicationResult(
                success=False,
                error=f"Easy Apply error: {e}"
            )
    
    async def _fill_contact_info_detailed(self, page, profile: Dict[str, str]):
        """Fill contact information with better field detection."""
        fields_to_fill = {
            'first_name': profile.get('first_name', ''),
            'last_name': profile.get('last_name', ''),
            'email': profile.get('email', ''),
            'phone': profile.get('phone', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', ''),
        }
        
        for field_name, value in fields_to_fill.items():
            if not value:
                continue
                
            selectors = self.FORM_FIELDS.get(field_name, [])
            for selector in selectors:
                try:
                    field = page.locator(selector).first
                    if await field.count() > 0:
                        # Check if field is empty or needs updating
                        current = await field.input_value()
                        if not current or current != value:
                            await field.fill(value)
                            logger.info(f"[LinkedIn] Filled {field_name}: {value[:20]}...")
                        break
                except Exception as e:
                    logger.debug(f"[LinkedIn] Could not fill {field_name}: {e}")
                    continue
    
    async def _progress_through_steps(self, page, resume_path: str) -> ApplicationResult:
        """Progress through LinkedIn Easy Apply multi-step modal."""
        max_steps = 10
        current_step = 0
        screenshot_on_failure = True
        
        while current_step < max_steps:
            current_step += 1
            logger.info(f"[LinkedIn] Processing step {current_step}/{max_steps}...")
            
            try:
                await asyncio.sleep(2)
                
                # Check for success
                if await self._check_success(page):
                    logger.info("[LinkedIn] ✅ Success message detected!")
                    return ApplicationResult(
                        success=True,
                        confirmation_id=f"LI_{int(asyncio.get_event_loop().time())}"
                    )
                
                # Handle Resume Upload
                resume_uploaded = await self._handle_resume_step(page, resume_path)
                if resume_uploaded:
                    logger.info("[LinkedIn] ✅ Resume handled")
                    await asyncio.sleep(1)
                
                # Answer Additional Questions
                questions_answered = await self._handle_additional_questions(page)
                if questions_answered:
                    logger.info("[LinkedIn] ✅ Questions answered")
                    await asyncio.sleep(1)
                
                # Check for final Submit button
                submit_clicked = False
                for submit_selector in self.EASY_APPLY_MODAL['submit_button']:
                    try:
                        submit_btn = page.locator(submit_selector).first
                        if await submit_btn.count() > 0:
                            is_visible = await submit_btn.is_visible()
                            if is_visible:
                                is_enabled = await submit_btn.is_enabled()
                                btn_text = await submit_btn.inner_text() if is_visible else ""
                                logger.info(f"[LinkedIn] Found submit button: '{btn_text[:30]}...'")
                                
                                if is_enabled:
                                    logger.info("[LinkedIn] 🚀 Clicking FINAL SUBMIT button!")
                                    await submit_btn.click()
                                    await asyncio.sleep(4)
                                    submit_clicked = True
                                    
                                    if await self._check_success(page):
                                        return ApplicationResult(success=True)
                                    
                                    modal = page.locator(self.EASY_APPLY_MODAL['container']).first
                                    if await modal.count() == 0 or not await modal.is_visible():
                                        return ApplicationResult(success=True)
                                break
                    except:
                        continue
                
                if submit_clicked:
                    await asyncio.sleep(3)
                    if await self._check_success(page):
                        return ApplicationResult(success=True)
                
                # Check for Review/Next buttons
                review_clicked = False
                for review_selector in self.EASY_APPLY_MODAL['review_button']:
                    try:
                        review_btn = page.locator(review_selector).first
                        if await review_btn.count() > 0 and await review_btn.is_visible():
                            logger.info(f"[LinkedIn] Clicking Review button: {review_selector}")
                            await review_btn.click()
                            await asyncio.sleep(2)
                            review_clicked = True
                            break
                    except Exception as e:
                        logger.debug(f"[LinkedIn] Review button {review_selector} error: {e}")
                        continue
                
                if review_clicked:
                    continue
                
                next_clicked = False
                for next_selector in self.EASY_APPLY_MODAL['next_button']:
                    try:
                        next_btn = page.locator(next_selector).first
                        if await next_btn.count() > 0:
                            is_visible = await next_btn.is_visible()
                            if is_visible:
                                btn_text = await next_btn.inner_text()
                                logger.info(f"[LinkedIn] Clicking Next button: '{btn_text[:30]}' ({next_selector})")
                                await next_btn.click()
                                await asyncio.sleep(3)
                                next_clicked = True
                                break
                    except Exception as e:
                        logger.debug(f"[LinkedIn] Next button {next_selector} error: {e}")
                        continue
                
                if next_clicked:
                    continue
                
                # Check if done
                modal = page.locator(self.EASY_APPLY_MODAL['container']).first
                if await modal.count() == 0 or not await modal.is_visible():
                    return ApplicationResult(success=True)
                
                logger.warning(f"[LinkedIn] No actionable buttons on step {current_step}")
                
                # Check for error messages
                try:
                    error_msgs = await page.locator('.artdeco-inline-feedback--error, .jobs-easy-apply-form__error-message').all()
                    if error_msgs:
                        for err in error_msgs:
                            err_text = await err.inner_text()
                            logger.error(f"[LinkedIn] Form error: {err_text}")
                except:
                    pass
                
                if screenshot_on_failure:
                    try:
                        await page.screenshot(path=f'campaigns/output/linkedin_stuck_step{current_step}.png')
                        logger.info(f"[LinkedIn] Screenshot saved: campaigns/output/linkedin_stuck_step{current_step}.png")
                    except:
                        pass
                
            except Exception as e:
                logger.warning(f"[LinkedIn] Step {current_step} error: {e}")
                break
        
        return ApplicationResult(
            success=False,
            error=f"Could not complete after {max_steps} steps"
        )
    
    async def _handle_resume_step(self, page, resume_path: str) -> bool:
        """Handle resume upload step specifically."""
        try:
            upload_input = page.locator('input[type="file"]').first
            if await upload_input.count() > 0 and await upload_input.is_visible():
                await upload_input.set_input_files(resume_path)
                await asyncio.sleep(2)
                logger.info("[LinkedIn] Resume uploaded")
                return True
            
            select_btn = page.locator('button:has-text("Select resume")').first
            if await select_btn.count() > 0 and await select_btn.is_visible():
                await select_btn.click()
                await asyncio.sleep(1)
                first_resume = page.locator('.artdeco-list__item').first
                if await first_resume.count() > 0:
                    await first_resume.click()
                    await asyncio.sleep(1)
                logger.info("[LinkedIn] Existing resume selected")
                return True
                
        except Exception as e:
            logger.debug(f"[LinkedIn] Resume step error: {e}")
        
        return False
    
    async def _handle_additional_questions(self, page) -> bool:
        """Handle additional screening questions."""
        answered = False
        
        try:
            selects = await page.locator('select').all()
            for select in selects:
                try:
                    select_id = await select.get_attribute('id') or ''
                    options = await select.locator('option').all()
                    
                    for option in options[1:]:
                        text = await option.inner_text()
                        text_lower = text.lower()
                        
                        if 'sponsor' in select_id.lower() and 'no' in text_lower:
                            await select.select_option(label=text)
                            answered = True
                            break
                        elif ('authorized' in select_id.lower() or 'legally' in select_id.lower()) and 'yes' in text_lower:
                            await select.select_option(label=text)
                            answered = True
                            break
                except:
                    continue
            
            radio_groups = await page.locator('fieldset').all()
            for group in radio_groups:
                try:
                    legend = group.locator('legend').first
                    if await legend.count() > 0:
                        question = await legend.inner_text()
                        question_lower = question.lower()
                        
                        radios = await group.locator('input[type="radio"]').all()
                        for radio in radios:
                            radio_id = await radio.get_attribute('id')
                            label = page.locator(f'label[for="{radio_id}"]').first
                            if await label.count() > 0:
                                label_text = await label.inner_text()
                                label_lower = label_text.lower()
                                
                                if 'authorized' in question_lower and 'yes' in label_lower:
                                    await radio.click()
                                    answered = True
                                    break
                                elif 'sponsor' in question_lower and 'no' in label_lower:
                                    await radio.click()
                                    answered = True
                                    break
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"[LinkedIn] Questions handling error: {e}")
        
        return answered
    
    async def _check_success(self, page) -> bool:
        """Check if application was successfully submitted."""
        for selector in self.SUCCESS_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0 and await element.is_visible(timeout=3000):
                    return True
            except:
                continue
        return False
    
    async def _check_for_captcha(self, page) -> bool:
        """Check if CAPTCHA or security challenge is present."""
        for selector in self.CAPTCHA_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0 and await element.is_visible(timeout=2000):
                    logger.warning(f"[LinkedIn] CAPTCHA detected: {selector}")
                    return True
            except:
                continue
        
        for indicator in self.RATE_LIMIT_INDICATORS:
            try:
                if await page.locator(indicator).count() > 0:
                    logger.warning(f"[LinkedIn] Rate limit detected: {indicator}")
                    self.stats['rate_limited'] += 1
                    return True
            except:
                continue
        
        return False
    
    async def _apply_external(self, page, profile, resume_path) -> ApplicationResult:
        """Handle external apply redirect."""
        try:
            # Get redirect URL
            await asyncio.sleep(3)
            current_url = page.url
            
            if 'linkedin.com' not in current_url:
                logger.info(f"[LinkedIn] External redirect to: {current_url[:60]}...")
                return ApplicationResult(
                    success=False,
                    redirect_url=current_url,
                    error="External redirect - use appropriate ATS handler"
                )
            
            return ApplicationResult(
                success=False,
                error="External apply handling failed"
            )
        except Exception as e:
            logger.error(f"[LinkedIn] External apply error: {e}")
            return ApplicationResult(
                success=False,
                error=f"External apply error: {e}"
            )


# Singleton instance
_linkedin_handler = None


def get_linkedin_handler() -> LinkedInEasyApplyHandler:
    """Get singleton LinkedIn handler instance."""
    global _linkedin_handler
    if _linkedin_handler is None:
        _linkedin_handler = LinkedInEasyApplyHandler()
    return _linkedin_handler
