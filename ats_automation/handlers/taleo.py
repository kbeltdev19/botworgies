"""
Oracle Taleo ATS Handler
Used by many Fortune 500 companies
Characteristics: iframe-heavy, older UI
"""

import asyncio
from typing import Optional
from ..models import ApplicationResult, ATSPlatform
from .base_handler import BaseATSHandler


class TaleoHandler(BaseATSHandler):
    """Handler for Oracle Taleo ATS (taleo.net)"""
    
    IDENTIFIERS = ['taleo.net', 'oraclecloud.com', 'taleo']
    PLATFORM = ATSPlatform.TALEO
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is a Taleo job posting"""
        url_lower = url.lower()
        return any(id in url_lower for id in self.IDENTIFIERS)
    
    async def apply(self, job_url: str) -> ApplicationResult:
        """Apply to Taleo job"""
        session = await self.browser.create_stealth_session("taleo")
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
            
            # Taleo often uses iframes - find the main content frame
            target_frame = await self._get_main_frame(page)
            
            # Click Apply
            apply_link = await target_frame.wait_for_selector(
                'text="Apply to job", '
                'text="Apply now", '
                'a:has-text("Apply"), '
                'button:has-text("Apply")',
                timeout=10000
            )
            await apply_link.click()
            await self._human_delay(2, 3)
            
            # Handle account creation
            if await target_frame.query_selector('text="New User"'):
                await self._create_taleo_account(target_frame)
            elif await target_frame.query_selector('text="Create Account"'):
                await self._create_taleo_account(target_frame)
            
            # Multi-page form
            max_pages = 10
            for page_num in range(max_pages):
                print(f"Taleo page {page_num + 1}")
                
                # Fill current page
                filled = await self._fill_with_mapper(target_frame)
                print(f"  Filled {filled} fields")
                
                # Check for next or submit
                next_btn = await target_frame.query_selector(
                    'input[value="Next"], '
                    'input[value="Continue"], '
                    'button:has-text("Next"), '
                    'button:has-text("Continue")'
                )
                
                if next_btn:
                    await next_btn.click()
                    await self._human_delay(3, 5)
                else:
                    # Look for submit
                    submit_btn = await target_frame.query_selector(
                        'input[value="Submit"], '
                        'input[value="Finish"], '
                        'input[value="Complete"], '
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
                error_message='Did not reach submit button',
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
    
    async def _get_main_frame(self, page):
        """Get the main content frame (Taleo uses iframes)"""
        frames = page.frames
        
        # Try to find the frame with the application form
        for frame in frames[1:]:  # Skip main frame
            try:
                content = await frame.content()
                if any(text in content for text in ['Apply to job', 'Create Account', 'Email Address']):
                    return frame
            except:
                continue
        
        # Default to page if no iframe found
        return page
    
    async def _create_taleo_account(self, frame):
        """Create account on Taleo system"""
        # Fill email
        email_field = await frame.query_selector('input[name*="email"], input[type="email"]')
        if email_field:
            await email_field.fill(self.profile.email)
        
        # Fill password
        password = self._generate_temp_password()
        pwd_field = await frame.query_selector('input[type="password"]')
        if pwd_field:
            await pwd_field.fill(password)
        
        # Confirm password if present
        pwd_confirm = await frame.query_selector('input[name*="confirm"], input[name*="verify"]')
        if pwd_confirm:
            await pwd_confirm.fill(password)
        
        # Click create
        create_btn = await frame.query_selector(
            'input[value="Create Account"], '
            'button:has-text("Create Account")'
        )
        if create_btn:
            await create_btn.click()
            await self._human_delay(4, 6)
