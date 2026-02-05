#!/usr/bin/env python3
"""
Other ATS Handlers - SmartRecruiters and Taleo/Oracle.
"""

import asyncio
from typing import Dict, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ATSResult:
    success: bool
    confirmation_id: Optional[str] = None
    error: Optional[str] = None


class SmartRecruitersHandler:
    """Handler for SmartRecruiters ATS."""
    
    async def apply(self, page, profile: Dict, resume_path: str) -> ATSResult:
        """Apply to SmartRecruiters job."""
        try:
            await asyncio.sleep(2)
            
            # SmartRecruiters often has a simple 1-page form
            # Fill basic info
            fields = {
                'input[name="firstName"]': profile.get('first_name'),
                'input[name="lastName"]': profile.get('last_name'),
                'input[name="email"]': profile.get('email'),
                'input[name="phone"]': profile.get('phone'),
            }
            
            for selector, value in fields.items():
                if value:
                    try:
                        elem = page.locator(selector).first
                        if await elem.count() > 0:
                            await elem.fill(str(value))
                    except:
                        continue
            
            # Upload resume
            if resume_path:
                try:
                    upload = page.locator('input[type="file"]').first
                    if await upload.count() > 0:
                        await upload.set_input_files(resume_path)
                        await asyncio.sleep(2)
                except:
                    pass
            
            # Submit
            submit = page.locator('button[type="submit"], .apply-button').first
            if await submit.count() > 0:
                await submit.click(timeout=10000)
                await asyncio.sleep(3)
                return ATSResult(success=True)
            
            return ATSResult(success=False, error="Submit button not found")
            
        except Exception as e:
            return ATSResult(success=False, error=str(e))


class TaleoHandler:
    """Handler for Taleo/Oracle ATS (enterprise)."""
    
    async def apply(self, page, profile: Dict, resume_path: str) -> ATSResult:
        """Apply to Taleo job."""
        try:
            await asyncio.sleep(2)
            
            # Taleo often requires registration first
            # Try to find and fill basic info
            
            fields = {
                'input#firstname': profile.get('first_name'),
                'input#lastname': profile.get('last_name'),
                'input#email': profile.get('email'),
                'input#phone': profile.get('phone'),
            }
            
            for selector, value in fields.items():
                if value:
                    try:
                        elem = page.locator(selector).first
                        if await elem.count() > 0:
                            await elem.fill(str(value))
                    except:
                        continue
            
            # Look for continue/next buttons
            for btn_text in ['Continue', 'Next', 'Submit']:
                try:
                    btn = page.locator(f'button:has-text("{btn_text}")').first
                    if await btn.count() > 0 and await btn.is_enabled():
                        await btn.click()
                        await asyncio.sleep(2)
                        break
                except:
                    continue
            
            return ATSResult(success=True)
            
        except Exception as e:
            return ATSResult(success=False, error=str(e))


# Singletons
_sr_handler = None
_taleo_handler = None


def get_smartrecruiters_handler():
    global _sr_handler
    if _sr_handler is None:
        _sr_handler = SmartRecruitersHandler()
    return _sr_handler


def get_taleo_handler():
    global _taleo_handler
    if _taleo_handler is None:
        _taleo_handler = TaleoHandler()
    return _taleo_handler
