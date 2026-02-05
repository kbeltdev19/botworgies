"""
SAP SuccessFactors ATS Handler
Enterprise-focused, similar complexity to Workday
"""

import asyncio
from typing import Optional
from ..models import ApplicationResult, ATSPlatform
from .base_handler import BaseATSHandler


class SuccessFactorsHandler(BaseATSHandler):
    """Handler for SAP SuccessFactors ATS"""
    
    IDENTIFIERS = ['successfactors.com', 'sap.com', 'careerportal']
    PLATFORM = ATSPlatform.SUCCESSFACTORS
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is SuccessFactors job posting"""
        url_lower = url.lower()
        return any(id in url_lower for id in self.IDENTIFIERS)
    
    async def apply(self, job_url: str) -> ApplicationResult:
        """Apply to SuccessFactors job"""
        session = await self.browser.create_stealth_session("successfactors")
        page = session["page"]
        session_id = session["session_id"]
        
        try:
            await page.goto(job_url, wait_until='networkidle')
            await self._human_delay(2, 4)
            
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
            
            # Click Apply
            apply_btn = await page.wait_for_selector(
                'button:has-text("Apply"), '
                'a:has-text("Apply"), '
                'button[data-help-id="applyButton"]',
                timeout=10000
            )
            await apply_btn.click()
            await self._human_delay(2, 3)
            
            # Guest application or login
            guest_btn = await page.query_selector('text="Apply as Guest"')
            if guest_btn:
                await guest_btn.click()
                await self._human_delay(2, 3)
            
            # Multi-step process
            max_steps = 8
            for step in range(max_steps):
                # Fill current step
                await self._fill_with_mapper(page)
                
                # Check for navigation buttons
                next_btn = await page.query_selector(
                    'button[data-help-id="nextButton"], '
                    'button:has-text("Next"), '
                    'button:has-text("Continue")'
                )
                
                if next_btn:
                    await next_btn.click()
                    await self._human_delay(3, 5)
                else:
                    # Check for submit
                    submit_btn = await page.query_selector(
                        'button[data-help-id="submitButton"], '
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
                    break
            
            return ApplicationResult(
                success=False,
                platform=self.PLATFORM,
                job_id=job_url,
                job_url=job_url,
                status='incomplete',
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
