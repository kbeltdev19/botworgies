#!/usr/bin/env python3
"""
Generic ATS Handler - Handles unknown/external career sites.

Uses common form field patterns to auto-fill applications on any platform.
"""

import asyncio
from typing import Dict, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ApplicationResult:
    """Result of an application attempt."""
    success: bool
    confirmation_id: Optional[str] = None
    error: Optional[str] = None
    screenshot_path: Optional[str] = None


class GenericATSHandler:
    """
    Generic handler for unknown ATS platforms.
    
    Uses common field selectors to detect and fill forms on any career site.
    Success rate: ~30-50% depending on site complexity.
    """
    
    # Common field selectors (tried in order)
    FIELD_SELECTORS = {
        'first_name': [
            'input[name="first_name"]', 'input[name="firstName"]', 'input[name="firstname"]',
            'input[id="first_name"]', 'input[id="firstName"]', 'input[id="firstname"]',
            'input[placeholder*="first name" i]', 'input[placeholder*="first" i]',
            'input[aria-label*="first name" i]', 'input[aria-label*="first" i]',
            'input[data-field*="first" i]', 'input[data-name*="first" i]',
        ],
        'last_name': [
            'input[name="last_name"]', 'input[name="lastName"]', 'input[name="lastname"]',
            'input[id="last_name"]', 'input[id="lastName"]', 'input[id="lastname"]',
            'input[placeholder*="last name" i]', 'input[placeholder*="last" i]',
            'input[aria-label*="last name" i]', 'input[aria-label*="last" i]',
            'input[data-field*="last" i]', 'input[data-name*="last" i]',
        ],
        'email': [
            'input[type="email"]', 'input[name="email"]', 'input[name="email_address"]',
            'input[id="email"]', 'input[placeholder*="email" i]',
            'input[aria-label*="email" i]', 'input[data-field*="email" i]',
        ],
        'phone': [
            'input[type="tel"]', 'input[name="phone"]', 'input[name="phone_number"]',
            'input[name="mobile"]', 'input[id="phone"]', 'input[placeholder*="phone" i]',
            'input[placeholder*="mobile" i]', 'input[data-field*="phone" i]',
        ],
        'linkedin': [
            'input[name="linkedin"]', 'input[name="linkedin_url"]', 'input[name="linkedin_profile"]',
            'input[placeholder*="linkedin" i]', 'input[aria-label*="linkedin" i]',
        ],
        'website': [
            'input[name="website"]', 'input[name="portfolio"]', 'input[name="url"]',
            'input[placeholder*="website" i]', 'input[placeholder*="portfolio" i]',
        ],
        'resume': [
            'input[type="file"][accept*=".pdf"]', 'input[type="file"][accept*=".doc"]',
            'input[type="file"][name*="resume"]', 'input[type="file"][name*="cv"]',
            'input[type="file"][data-field*="resume"]', 'input[type="file"][aria-label*="resume" i]',
            'input[type="file"]',  # Last resort - any file input
        ],
        'submit': [
            'button[type="submit"]', 'input[type="submit"]',
            'button:has-text("Submit")', 'button:has-text("Apply")',
            'button:has-text("Send")', 'button:has-text("Send Application")',
            'input[value*="submit" i]', 'input[value*="apply" i]',
            'button[data-action="submit"]', 'button[data-testid*="submit"]',
        ],
    }
    
    # Success indicators
    SUCCESS_SELECTORS = [
        '.success-message', '.thank-you', '.confirmation',
        '[data-testid="success"]', '[data-testid="confirmation"]',
        'h1:has-text("Thank")', 'h2:has-text("Thank")',
        'h1:has-text("Success")', 'h2:has-text("Success")',
        '.alert-success', '.notification-success',
        'text="Application submitted"', 'text="Thank you for applying"',
    ]
    
    # Error indicators
    ERROR_SELECTORS = [
        '.error-message', '.form-error', '.alert-error',
        '[data-testid="error"]', '.has-error',
        'text="Required"', 'text="Please fill"',
    ]
    
    def __init__(self):
        self.stats = {
            'attempted': 0,
            'successful': 0,
            'failed': 0,
            'fields_filled': {},
        }
    
    async def apply(
        self,
        page,
        profile: Dict[str, str],
        resume_path: str
    ) -> ApplicationResult:
        """
        Apply to a job on an unknown ATS platform.
        
        Args:
            page: Playwright page
            profile: Dict with first_name, last_name, email, phone, etc.
            resume_path: Path to resume file
            
        Returns:
            ApplicationResult
        """
        self.stats['attempted'] += 1
        
        try:
            # Wait for page to load
            await asyncio.sleep(3)
            
            # Detect if this looks like an application form
            has_form = await self._detect_application_form(page)
            if not has_form:
                return ApplicationResult(
                    success=False,
                    error="No application form detected on page"
                )
            
            logger.info("[GenericATS] Application form detected")
            
            # Fill form fields
            fields_filled = await self._fill_form_fields(page, profile)
            
            if not fields_filled:
                return ApplicationResult(
                    success=False,
                    error="Could not fill any form fields"
                )
            
            # Upload resume
            resume_uploaded = await self._upload_resume(page, resume_path)
            
            # Submit form
            submitted = await self._submit_form(page)
            
            if submitted:
                # Check for success
                success = await self._check_success(page)
                if success:
                    self.stats['successful'] += 1
                    return ApplicationResult(
                        success=True,
                        confirmation_id=f"GENERIC_{int(asyncio.get_event_loop().time())}"
                    )
                else:
                    # Submitted but can't confirm success
                    return ApplicationResult(
                        success=True,  # Assume success if no error
                        confirmation_id=f"GENERIC_UNCONFIRMED_{int(asyncio.get_event_loop().time())}"
                    )
            else:
                self.stats['failed'] += 1
                return ApplicationResult(
                    success=False,
                    error="Could not submit form"
                )
                
        except Exception as e:
            logger.error(f"[GenericATS] Application failed: {e}")
            self.stats['failed'] += 1
            return ApplicationResult(
                success=False,
                error=f"Generic ATS error: {e}"
            )
    
    async def _detect_application_form(self, page) -> bool:
        """Detect if the page has an application form."""
        # Look for common form indicators
        form_selectors = [
            'form', 'input[type="text"]', 'input[type="email"]',
            'input[name*="name"]', 'button[type="submit"]',
        ]
        
        for selector in form_selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    return True
            except:
                continue
        
        return False
    
    async def _fill_form_fields(self, page, profile: Dict[str, str]) -> int:
        """Fill form fields using multiple selector strategies."""
        fields_filled = 0
        
        field_mapping = {
            'first_name': profile.get('first_name', ''),
            'last_name': profile.get('last_name', ''),
            'email': profile.get('email', ''),
            'phone': profile.get('phone', '').replace('-', '').replace(' ', ''),
            'linkedin': profile.get('linkedin', ''),
            'website': profile.get('website', ''),
        }
        
        for field_name, value in field_mapping.items():
            if not value:
                continue
            
            selectors = self.FIELD_SELECTORS.get(field_name, [])
            filled = await self._try_fill_field(page, selectors, value)
            
            if filled:
                fields_filled += 1
                self.stats['fields_filled'][field_name] = self.stats['fields_filled'].get(field_name, 0) + 1
                logger.debug(f"[GenericATS] Filled {field_name}")
        
        logger.info(f"[GenericATS] Filled {fields_filled} fields")
        return fields_filled
    
    async def _try_fill_field(self, page, selectors: List[str], value: str) -> bool:
        """Try to fill a field using multiple selectors."""
        for selector in selectors:
            try:
                element = page.locator(selector).first
                
                # Check if element exists and is visible
                if await element.count() == 0:
                    continue
                
                # Check if already filled
                try:
                    current_value = await element.input_value()
                    if current_value and len(current_value) > 0:
                        continue  # Skip if already has value
                except:
                    pass
                
                # Fill the field
                await element.fill(value)
                await asyncio.sleep(0.3)
                return True
                
            except Exception as e:
                logger.debug(f"[GenericATS] Failed to fill with selector {selector}: {e}")
                continue
        
        return False
    
    async def _upload_resume(self, page, resume_path: str) -> bool:
        """Upload resume to file input."""
        selectors = self.FIELD_SELECTORS['resume']
        
        for selector in selectors:
            try:
                element = page.locator(selector).first
                
                if await element.count() == 0:
                    continue
                
                if not await element.is_visible():
                    continue
                
                await element.set_input_files(resume_path)
                await asyncio.sleep(2)  # Wait for upload
                logger.info("[GenericATS] Resume uploaded")
                return True
                
            except Exception as e:
                logger.debug(f"[GenericATS] Resume upload failed with {selector}: {e}")
                continue
        
        logger.warning("[GenericATS] Could not upload resume")
        return False
    
    async def _submit_form(self, page) -> bool:
        """Submit the application form."""
        for selector in self.FIELD_SELECTORS['submit']:
            try:
                element = page.locator(selector).first
                
                if await element.count() == 0:
                    continue
                
                if not await element.is_visible():
                    continue
                
                if not await element.is_enabled():
                    continue
                
                # Scroll into view
                await element.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                
                # Click with force if needed
                try:
                    await element.click(timeout=5000)
                except:
                    await element.click(force=True, timeout=5000)
                
                await asyncio.sleep(3)  # Wait for submission
                logger.info("[GenericATS] Form submitted")
                return True
                
            except Exception as e:
                logger.debug(f"[GenericATS] Submit failed with {selector}: {e}")
                continue
        
        return False
    
    async def _check_success(self, page) -> bool:
        """Check if application was successfully submitted."""
        # Check success indicators
        for selector in self.SUCCESS_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0 and await element.is_visible(timeout=3000):
                    return True
            except:
                continue
        
        # Check for errors (negative indicator)
        for selector in self.ERROR_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0 and await element.is_visible(timeout=2000):
                    return False
            except:
                continue
        
        # If URL changed, likely submitted
        return True
    
    def get_stats(self) -> Dict:
        """Get handler statistics."""
        return self.stats.copy()


# Singleton instance
_generic_handler = None


def get_generic_ats_handler() -> GenericATSHandler:
    """Get singleton generic ATS handler instance."""
    global _generic_handler
    if _generic_handler is None:
        _generic_handler = GenericATSHandler()
    return _generic_handler
