#!/usr/bin/env python3
"""
Indeed Job Application Handler

Handles Indeed-specific application flows:
1. Indeed Easy Apply (direct form)
2. External redirect (company ATS)
3. One-click apply
"""

import asyncio
import re
from typing import Dict, Optional, Any
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)


@dataclass
class IndeedApplyResult:
    """Result of Indeed application attempt."""
    success: bool
    confirmation_id: Optional[str] = None
    error: Optional[str] = None
    redirect_url: Optional[str] = None
    is_easy_apply: bool = False


class IndeedHandler:
    """
    Handler for Indeed job applications.
    
    Supports:
    - Indeed Easy Apply (in-platform form)
    - External apply (redirect to company site)
    - One-click apply (quick applications)
    """
    
    # Indeed Easy Apply indicators
    EASY_APPLY_INDICATORS = [
        'button[data-testid="apply-button"]',
        'button:has-text("Apply now")',
        'button:has-text("Easily apply")',
        '.ia-IndeedApplyButton',
        'button[data-indeed-apply]',
    ]
    
    # External apply indicators
    EXTERNAL_APPLY_INDICATORS = [
        'button:has-text("Apply on company site")',
        'a:has-text("Apply on company site")',
        'button[data-testid="apply-external-button"]',
    ]
    
    # Form field selectors for Indeed Easy Apply
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
            'input[name="email"]',
            'input[autocomplete="email"]',
        ],
        'phone': [
            'input[type="tel"]',
            'input[name="phone"]',
            'input[autocomplete="tel"]',
        ],
        'resume': [
            'input[type="file"][name="resume"]',
            'input[type="file"][accept*=".pdf"]',
        ],
        'continue_button': [
            'button[type="submit"]',
            'button:has-text("Continue")',
            'button[data-testid="continue-button"]',
        ],
        'submit_button': [
            'button[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Submit application")',
        ],
    }
    
    # Success indicators
    SUCCESS_SELECTORS = [
        'text=/application.*submitted/i',
        'text=/successfully applied/i',
        '.ia-ApplicationSuccess',
        'h1:has-text("Application submitted")',
        '[data-testid="application-success"]',
    ]
    
    def __init__(self):
        self.stats = {
            'attempted': 0,
            'successful': 0,
            'easy_apply': 0,
            'external_redirect': 0,
            'failed': 0,
        }
    
    async def apply(
        self,
        page,
        profile: Dict[str, str],
        resume_path: str,
        job_data: Optional[Dict] = None
    ) -> IndeedApplyResult:
        """
        Apply to an Indeed job.
        
        Args:
            page: Playwright page (already on Indeed job page)
            profile: Dict with first_name, last_name, email, phone
            resume_path: Path to resume file
            job_data: Optional job data dict
            
        Returns:
            IndeedApplyResult
        """
        self.stats['attempted'] += 1
        
        try:
            logger.info("[Indeed] Starting application process...")
            
            # Wait for page to load
            await asyncio.sleep(3)
            
            # Check for CAPTCHA
            if await self._check_for_captcha(page):
                return IndeedApplyResult(
                    success=False,
                    error="CAPTCHA detected"
                )
            
            # Detect apply type
            apply_type = await self._detect_apply_type(page)
            logger.info(f"[Indeed] Apply type detected: {apply_type}")
            
            if apply_type == 'easy_apply':
                return await self._apply_easy_apply(page, profile, resume_path)
            elif apply_type == 'external':
                return await self._apply_external(page)
            else:
                return IndeedApplyResult(
                    success=False,
                    error="No apply button found on Indeed page"
                )
                
        except Exception as e:
            logger.error(f"[Indeed] Application failed: {e}")
            self.stats['failed'] += 1
            return IndeedApplyResult(
                success=False,
                error=str(e)
            )
    
    async def _detect_apply_type(self, page) -> str:
        """Detect if job has Indeed Easy Apply or External Apply."""
        # Check for Easy Apply first
        for selector in self.EASY_APPLY_INDICATORS:
            try:
                button = page.locator(selector).first
                if await button.count() > 0 and await button.is_visible():
                    text = await button.inner_text()
                    logger.info(f"[Indeed] Found Easy Apply button: {text[:50]}")
                    return 'easy_apply'
            except:
                continue
        
        # Check for External Apply
        for selector in self.EXTERNAL_APPLY_INDICATORS:
            try:
                button = page.locator(selector).first
                if await button.count() > 0 and await button.is_visible():
                    text = await button.inner_text()
                    logger.info(f"[Indeed] Found External Apply button: {text[:50]}")
                    return 'external'
            except:
                continue
        
        # Try generic apply button detection
        try:
            all_buttons = await page.locator('button').all()
            for btn in all_buttons:
                if await btn.is_visible():
                    text = await btn.inner_text()
                    text_lower = text.lower()
                    if 'apply' in text_lower and 'company' not in text_lower:
                        return 'easy_apply'
                    elif 'apply' in text_lower and 'company' in text_lower:
                        return 'external'
        except:
            pass
        
        return 'unknown'
    
    async def _apply_easy_apply(
        self,
        page,
        profile: Dict[str, str],
        resume_path: str
    ) -> IndeedApplyResult:
        """Apply using Indeed's Easy Apply flow."""
        try:
            logger.info("[Indeed] Starting Easy Apply flow...")
            
            # Click the apply button
            apply_clicked = False
            for selector in self.EASY_APPLY_INDICATORS:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        apply_clicked = True
                        logger.info(f"[Indeed] Clicked apply button: {selector}")
                        break
                except:
                    continue
            
            if not apply_clicked:
                return IndeedApplyResult(
                    success=False,
                    error="Could not click apply button"
                )
            
            # Wait for form to appear
            await asyncio.sleep(3)
            
            # Fill contact information
            await self._fill_contact_info(page, profile)
            
            # Upload resume
            await self._upload_resume(page, resume_path)
            
            # Progress through any additional steps
            max_steps = 5
            for step in range(max_steps):
                await asyncio.sleep(2)
                
                # Check for success
                if await self._check_success(page):
                    self.stats['successful'] += 1
                    self.stats['easy_apply'] += 1
                    return IndeedApplyResult(
                        success=True,
                        confirmation_id=f"INDEED_{int(asyncio.get_event_loop().time())}",
                        is_easy_apply=True
                    )
                
                # Click continue/submit
                continue_clicked = False
                for selector in self.FORM_FIELDS['continue_button'] + self.FORM_FIELDS['submit_button']:
                    try:
                        btn = page.locator(selector).first
                        if await btn.count() > 0 and await btn.is_visible():
                            await btn.click()
                            continue_clicked = True
                            logger.info(f"[Indeed] Clicked continue/submit button")
                            break
                    except:
                        continue
                
                if not continue_clicked:
                    break
            
            # Final success check
            if await self._check_success(page):
                self.stats['successful'] += 1
                self.stats['easy_apply'] += 1
                return IndeedApplyResult(
                    success=True,
                    confirmation_id=f"INDEED_{int(asyncio.get_event_loop().time())}",
                    is_easy_apply=True
                )
            
            return IndeedApplyResult(
                success=False,
                error="Could not complete Easy Apply flow"
            )
            
        except Exception as e:
            logger.error(f"[Indeed] Easy Apply failed: {e}")
            return IndeedApplyResult(
                success=False,
                error=f"Easy Apply error: {e}"
            )
    
    async def _apply_external(self, page) -> IndeedApplyResult:
        """Handle external redirect to company site."""
        try:
            logger.info("[Indeed] External apply - redirecting to company site...")
            
            # Click external apply button
            for selector in self.EXTERNAL_APPLY_INDICATORS:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        # Get the redirect URL before clicking
                        href = await btn.get_attribute('href') or ''
                        
                        await btn.click()
                        await asyncio.sleep(3)
                        
                        # Check if we navigated to a new page
                        current_url = page.url
                        if 'indeed.com' not in current_url:
                            self.stats['external_redirect'] += 1
                            return IndeedApplyResult(
                                success=False,
                                redirect_url=current_url,
                                error="External redirect - use company-specific handler"
                            )
                        
                        # Sometimes opens in new tab
                        if href and href.startswith('http'):
                            return IndeedApplyResult(
                                success=False,
                                redirect_url=href,
                                error="External redirect - use company-specific handler"
                            )
                        
                except:
                    continue
            
            return IndeedApplyResult(
                success=False,
                error="Could not process external apply"
            )
            
        except Exception as e:
            logger.error(f"[Indeed] External apply failed: {e}")
            return IndeedApplyResult(
                success=False,
                error=f"External apply error: {e}"
            )
    
    async def _fill_contact_info(self, page, profile: Dict[str, str]):
        """Fill contact information on Indeed form."""
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
                    if await field.count() > 0 and await field.is_visible():
                        await field.fill(value)
                        logger.info(f"[Indeed] Filled {field_name}: {value[:20]}...")
                        break
                except Exception as e:
                    logger.debug(f"[Indeed] Could not fill {field_name}: {e}")
                    continue
    
    async def _upload_resume(self, page, resume_path: str):
        """Upload resume on Indeed form."""
        try:
            for selector in self.FORM_FIELDS['resume']:
                try:
                    upload_input = page.locator(selector).first
                    if await upload_input.count() > 0 and await upload_input.is_visible():
                        await upload_input.set_input_files(resume_path)
                        logger.info("[Indeed] Resume uploaded")
                        await asyncio.sleep(2)
                        break
                except:
                    continue
        except Exception as e:
            logger.debug(f"[Indeed] Resume upload error: {e}")
    
    async def _check_success(self, page) -> bool:
        """Check if application was successfully submitted."""
        for selector in self.SUCCESS_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0 and await element.is_visible(timeout=3000):
                    return True
            except:
                continue
        
        # Check page content
        try:
            content = await page.content()
            success_patterns = [
                'application submitted',
                'successfully applied',
                'thank you for applying',
                'your application has been received',
            ]
            content_lower = content.lower()
            if any(pattern in content_lower for pattern in success_patterns):
                return True
        except:
            pass
        
        return False
    
    async def _check_for_captcha(self, page) -> bool:
        """Check if CAPTCHA is present."""
        captcha_selectors = [
            '.captcha',
            '#captcha',
            'iframe[src*="captcha"]',
            'text=/captcha/i',
        ]
        
        for selector in captcha_selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0 and await element.is_visible(timeout=2000):
                    logger.warning("[Indeed] CAPTCHA detected")
                    return True
            except:
                continue
        
        return False
    
    def get_stats(self) -> Dict[str, int]:
        """Get application statistics."""
        return self.stats.copy()


# Singleton instance
_indeed_handler = None


def get_indeed_handler() -> IndeedHandler:
    """Get singleton Indeed handler instance."""
    global _indeed_handler
    if _indeed_handler is None:
        _indeed_handler = IndeedHandler()
    return _indeed_handler
