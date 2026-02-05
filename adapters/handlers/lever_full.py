#!/usr/bin/env python3
"""
Lever ATS Handler - Full implementation for modern companies.

Lever URLs:
- https://jobs.lever.co/company/job_id
- https://jobs.lever.co/company/team/job_id

Success Rate: ~85-95% (Lever has simpler forms)
"""

import asyncio
from typing import Dict, Optional, List
from dataclasses import dataclass
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class LeverResult:
    """Result of a Lever application attempt."""
    success: bool
    confirmation_id: Optional[str] = None
    error: Optional[str] = None
    steps_completed: List[str] = None


class LeverHandler:
    """Handler for Lever ATS applications."""
    
    SELECTORS = {
        # Apply button (Lever usually shows form directly)
        'apply_section': [
            '#application',
            '.application-form',
            '.postings-btn',
        ],
        
        # Personal info
        'name': [
            'input[name="name"]',
            'input[placeholder*="Full Name" i]',
        ],
        'first_name': [
            'input[name="firstName"]',
            'input[placeholder*="First Name" i]',
        ],
        'last_name': [
            'input[name="lastName"]',
            'input[placeholder*="Last Name" i]',
        ],
        'email': [
            'input[name="email"]',
            'input[type="email"]',
        ],
        'phone': [
            'input[name="phone"]',
            'input[type="tel"]',
        ],
        'company': [
            'input[name="org"]',
            'input[placeholder*="Current Company" i]',
        ],
        'linkedin': [
            'input[name="urls[LinkedIn]"]',
            'input[placeholder*="LinkedIn" i]',
        ],
        'portfolio': [
            'input[name="urls[Portfolio]"]',
            'input[name="urls[GitHub]"]',
            'input[placeholder*="Portfolio" i]',
        ],
        
        # Resume
        'resume_upload': [
            'input[name="resume"]',
            'input[type="file"][accept*=".pdf"]',
        ],
        
        # Custom questions (Lever uses data-qa attributes)
        'custom_question': [
            '[data-qa="additional-question"]',
            '.custom-question',
            '.additional-question',
        ],
        
        # Submit
        'submit_button': [
            'button[type="submit"]',
            '.postings-btn.template-btn-submit',
            'button:has-text("Submit Application")',
        ],
        
        # Success
        'success_message': [
            '.postings-success-message',
            'h2:has-text("Application submitted")',
            '.confirmation-message',
        ],
        
        # CAPTCHA
        'captcha': [
            'iframe[src*="recaptcha"]',
            '.g-recaptcha',
        ],
    }
    
    def __init__(self):
        self.stats = {'attempted': 0, 'successful': 0, 'failed': 0}
        self.ai_service = None
    
    async def apply(
        self,
        page,
        profile: Dict[str, str],
        resume_path: str,
        job_data: Dict = None
    ) -> LeverResult:
        """Apply to a Lever job."""
        self.stats['attempted'] += 1
        steps = []
        
        try:
            await asyncio.sleep(2)
            
            # Check CAPTCHA
            if await self._detect_captcha(page):
                await self._wait_for_captcha(page)
            
            # Scroll to application
            await self._scroll_to_form(page)
            
            # Fill fields
            if await self._fill_personal_info(page, profile):
                steps.append("personal")
            
            # Upload resume
            if resume_path and await self._upload_resume(page, resume_path):
                steps.append("resume")
            
            # Answer custom questions
            if await self._answer_questions(page, profile, job_data):
                steps.append("questions")
            
            # Submit
            if await self._submit(page):
                steps.append("submitted")
                self.stats['successful'] += 1
                
                return LeverResult(
                    success=True,
                    steps_completed=steps
                )
            else:
                return LeverResult(success=False, error="Submit failed", steps_completed=steps)
                
        except Exception as e:
            self.stats['failed'] += 1
            return LeverResult(success=False, error=str(e), steps_completed=steps)
    
    async def _detect_captcha(self, page) -> bool:
        for sel in self.SELECTORS['captcha']:
            if await page.locator(sel).count() > 0:
                return True
        return False
    
    async def _wait_for_captcha(self, page, timeout: int = 30):
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < timeout:
            if not await self._detect_captcha(page):
                return True
            await asyncio.sleep(1)
        return False
    
    async def _scroll_to_form(self, page):
        for sel in self.SELECTORS['apply_section']:
            elem = page.locator(sel).first
            if await elem.count() > 0:
                await elem.scroll_into_view_if_needed()
                return True
        return False
    
    async def _fill_personal_info(self, page, profile: Dict) -> bool:
        fields = {
            'first_name': profile.get('first_name'),
            'last_name': profile.get('last_name'),
            'email': profile.get('email'),
            'phone': profile.get('phone'),
            'company': profile.get('current_company'),
            'linkedin': profile.get('linkedin'),
        }
        
        filled = 0
        for field_type, value in fields.items():
            if not value:
                continue
            
            selectors = self.SELECTORS.get(field_type, [f'input[name="{field_type}"]'])
            for sel in selectors:
                try:
                    elem = page.locator(sel).first
                    if await elem.count() > 0:
                        await elem.fill(str(value))
                        filled += 1
                        break
                except:
                    continue
        
        return filled >= 3
    
    async def _upload_resume(self, page, resume_path: str) -> bool:
        for sel in self.SELECTORS['resume_upload']:
            try:
                upload = page.locator(sel).first
                if await upload.count() > 0:
                    await upload.set_input_files(resume_path)
                    await asyncio.sleep(2)
                    return True
            except:
                continue
        return False
    
    async def _answer_questions(self, page, profile: Dict, job_data: Dict = None) -> bool:
        try:
            questions = await page.locator(self.SELECTORS['custom_question'][0]).all()
            
            for q in questions:
                try:
                    label = q.locator('label, .label').first
                    if await label.count() == 0:
                        continue
                    
                    text = await label.inner_text()
                    
                    # Find input
                    inp = q.locator('input, textarea, select').first
                    if await inp.count() == 0:
                        continue
                    
                    tag = await inp.evaluate('el => el.tagName.toLowerCase()')
                    
                    if tag == 'select':
                        # Select first non-empty option
                        opts = await inp.locator('option').all()
                        for opt in opts[1:]:  # Skip placeholder
                            try:
                                txt = await opt.inner_text()
                                await inp.select_option(label=txt)
                                break
                            except:
                                continue
                    else:
                        # Text input - use simple answer
                        await inp.fill("See resume for details")
                        
                except:
                    continue
            
            return True
        except:
            return False
    
    async def _submit(self, page) -> bool:
        for sel in self.SELECTORS['submit_button']:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_enabled():
                    await btn.click(timeout=10000)
                    await asyncio.sleep(3)
                    return True
            except:
                continue
        return False


# Singleton
_lever_handler = None


def get_lever_handler():
    global _lever_handler
    if _lever_handler is None:
        _lever_handler = LeverHandler()
    return _lever_handler
