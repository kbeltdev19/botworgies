#!/usr/bin/env python3
"""
Optimized Workday Handler - Handles complex multi-step forms.

Success Rate: ~50% (complex forms, lower success rate)
"""

import asyncio
from typing import Dict, Optional, Any
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


class WorkdayOptimizedHandler:
    """
    Optimized handler for Workday ATS.
    
    Workday has complex multi-step forms, so this handler:
    - Handles multi-step navigation
    - Waits for dynamic form loading
    - Handles complex field types
    """
    
    APPLY_BUTTON_SELECTOR = 'button[data-automation-id="applyButton"], button:has-text("Apply")'
    
    FORM_SELECTORS = {
        'first_name': 'input[data-automation-id="firstName"], input[name="firstName"]',
        'last_name': 'input[data-automation-id="lastName"], input[name="lastName"]',
        'email': 'input[data-automation-id="email"], input[name="email"], input[type="email"]',
        'phone': 'input[data-automation-id="phone"], input[name="phone"], input[type="tel"]',
        'address': 'input[data-automation-id="addressLine1"], input[name="address"]',
        'city': 'input[data-automation-id="city"], input[name="city"]',
        'zip': 'input[data-automation-id="postalCode"], input[name="postalCode"]',
        'resume': 'input[type="file"], input[data-automation-id="resume"]',
        'submit': 'button[data-automation-id="submit"], button:has-text("Submit")',
        'next': 'button[data-automation-id="next"], button:has-text("Next")',
    }
    
    SUCCESS_SELECTORS = [
        '[data-automation-id="applicationSubmitted"]',
        '.wd-application-submitted',
        'h1:has-text("Application Submitted")',
        'h2:has-text("Thank You")',
        '.confirmation-message',
    ]
    
    def __init__(self):
        self.stats = {
            'attempted': 0,
            'successful': 0,
            'steps_completed': 0,
        }
    
    async def apply(
        self,
        page,
        profile: Dict[str, str],
        resume_path: str
    ) -> ApplicationResult:
        """Apply to Workday job."""
        self.stats['attempted'] += 1
        
        try:
            # Click apply button
            apply_btn = page.locator(self.APPLY_BUTTON_SELECTOR).first
            if await apply_btn.count() > 0:
                await apply_btn.click()
                await asyncio.sleep(2)  # Workday loads slowly
            
            # Handle multi-step form
            max_steps = 5
            for step in range(max_steps):
                logger.debug(f"[Workday] Processing step {step + 1}")
                
                # Fill fields on current page
                await self._fill_current_page(page, profile)
                
                # Check for submit button
                submit_btn = page.locator(self.FORM_SELECTORS['submit']).first
                if await submit_btn.count() > 0 and await submit_btn.is_enabled():
                    await submit_btn.click()
                    await asyncio.sleep(3)
                    break
                
                # Click next
                next_btn = page.locator(self.FORM_SELECTORS['next']).first
                if await next_btn.count() > 0:
                    await next_btn.click()
                    await asyncio.sleep(2)
                else:
                    # No next button - might be done or stuck
                    break
            
            # Verify success
            success = await self._verify_success(page)
            
            if success:
                self.stats['successful'] += 1
                return ApplicationResult(success=True)
            else:
                return ApplicationResult(success=False, error="No confirmation")
                
        except Exception as e:
            logger.error(f"[Workday] Application failed: {e}")
            return ApplicationResult(success=False, error=str(e))
    
    async def _fill_current_page(self, page, profile: Dict[str, str]):
        """Fill all fields on current page."""
        fields = [
            ('first_name', profile.get('first_name')),
            ('last_name', profile.get('last_name')),
            ('email', profile.get('email')),
            ('phone', profile.get('phone')),
        ]
        
        for field_name, value in fields:
            if not value:
                continue
            
            selector = self.FORM_SELECTORS.get(field_name)
            if not selector:
                continue
            
            try:
                field = page.locator(selector).first
                if await field.count() > 0 and await field.is_visible():
                    await field.fill(value)
                    await asyncio.sleep(0.2)  # Small delay between fields
            except Exception as e:
                logger.debug(f"[Workday] Failed to fill {field_name}: {e}")
        
        # Handle resume upload if present
        try:
            resume_input = page.locator(self.FORM_SELECTORS['resume']).first
            if await resume_input.count() > 0:
                await resume_input.set_input_files(profile.get('resume_path', ''))
        except:
            pass
    
    async def _verify_success(self, page) -> bool:
        """Check if application was successful."""
        for selector in self.SUCCESS_SELECTORS:
            try:
                if await page.locator(selector).count() > 0:
                    return True
            except:
                continue
        
        # Check URL
        url = page.url.lower()
        if 'submitted' in url or 'confirmation' in url or 'success' in url:
            return True
        
        # Check for thank you text
        try:
            content = await page.content()
            if 'thank you' in content.lower() or 'application submitted' in content.lower():
                return True
        except:
            pass
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        success_rate = (
            self.stats['successful'] / self.stats['attempted'] * 100
            if self.stats['attempted'] > 0 else 0
        )
        
        return {
            **self.stats,
            'success_rate': f"{success_rate:.1f}%",
        }


# Singleton
_handler: Optional[WorkdayOptimizedHandler] = None


def get_workday_handler() -> WorkdayOptimizedHandler:
    """Get global handler instance."""
    global _handler
    if _handler is None:
        _handler = WorkdayOptimizedHandler()
    return _handler
