"""
ADP Workforce Now ATS Handler
HR-focused ATS, simpler than Workday/SuccessFactors
"""

import asyncio
from typing import Optional
from ..models import ApplicationResult, ATSPlatform
from .base_handler import BaseATSHandler


class ADPHandler(BaseATSHandler):
    """Handler for ADP Workforce Now ATS"""
    
    IDENTIFIERS = ['adp.com', 'workforcenow.adp.com', 'recruiting.adp.com']
    PLATFORM = ATSPlatform.ADP
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is ADP job posting"""
        url_lower = url.lower()
        return any(id in url_lower for id in self.IDENTIFIERS)
    
    async def apply(self, job_url: str) -> ApplicationResult:
        """Apply to ADP job"""
        session = await self.browser.create_stealth_session("adp")
        page = session["page"]
        session_id = session["session_id"]
        
        try:
            await page.goto(job_url, wait_until='networkidle')
            await self._human_delay(2, 3)
            
            # Handle captcha
            if not await self.browser.solve_captcha_if_present(session_id, page):
                return ApplicationResult(
                    success=False,
                    platform=self.PLATFORM,
                    job_id=job_url,
                    job_url=job_url,
                    status='captcha_blocked',
                    session_id=session_id
                )
            
            # ADP usually has simpler single-page or minimal multi-step forms
            # Click Apply
            apply_btn = await page.wait_for_selector(
                'button:has-text("Apply"), '
                'input[value="Apply"], '
                'a:has-text("Apply")',
                timeout=10000
            )
            await apply_btn.click()
            await self._human_delay(2, 4)
            
            # Check for account creation/login
            if await page.query_selector('text="Create Account"'):
                await self._create_adp_account(page)
            elif await page.query_selector('text="Sign In"'):
                # Try guest apply first
                guest = await page.query_selector('text="Continue as Guest"')
                if guest:
                    await guest.click()
                    await self._human_delay(2, 3)
            
            # Fill form
            await self._fill_with_mapper(page)
            
            # Submit
            submit_btn = await page.query_selector(
                'button[type="submit"], '
                'input[type="submit"], '
                'button:has-text("Submit")'
            )
            
            if submit_btn:
                await submit_btn.click()
                await self._human_delay(3, 5)
                
                return ApplicationResult(
                    success=True,
                    platform=self.PLATFORM,
                    job_id=job_url,
                    job_url=job_url,
                    status='submitted',
                    session_id=session_id
                )
            
            return ApplicationResult(
                success=False,
                platform=self.PLATFORM,
                job_id=job_url,
                job_url=job_url,
                status='incomplete',
                error_message='Submit button not found',
                session_id=session_id
            )
            
        except Exception as e:
            return ApplicationResult(
                success=False,
                platform=self.PLATFORM,
                job_id=job_url,
                job_url=job_url,
                status='error',
                error_message=str(e),
                session_id=session_id
            )
        finally:
            await self.browser.close_session(session_id)
    
    async def _create_adp_account(self, page):
        """Create ADP account if needed"""
        await self._fill_with_mapper(page, ['email', 'first_name', 'last_name'])
        
        # Password
        password = self._generate_temp_password()
        pwd_fields = await page.query_selector_all('input[type="password"]')
        for field in pwd_fields[:2]:  # Password and confirm
            await field.fill(password)
        
        # Submit
        create_btn = await page.query_selector('button:has-text("Create"), input[value="Create"]')
        if create_btn:
            await create_btn.click()
            await self._human_delay(4, 6)
