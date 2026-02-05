"""
iCIMS ATS Handler
Popular for mid-market companies
"""

import asyncio
import re
from typing import Optional
import aiohttp
from ..models import ApplicationResult, ATSPlatform
from .base_handler import BaseATSHandler


class iCIMSHandler(BaseATSHandler):
    """Handler for iCIMS ATS (icims.com, jobs.net)"""
    
    IDENTIFIERS = ['icims.com', 'jobs.net']
    PLATFORM = ATSPlatform.ICIMS
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is iCIMS job posting"""
        url_lower = url.lower()
        return any(id in url_lower for id in self.IDENTIFIERS)
    
    async def apply(self, job_url: str) -> ApplicationResult:
        """Apply to iCIMS job"""
        # Try API first (sometimes available)
        api_result = await self._try_api_apply(job_url)
        if api_result and api_result.success:
            return api_result
        
        # Fallback to browser
        return await self._browser_apply(job_url)
    
    async def _try_api_apply(self, job_url: str) -> Optional[ApplicationResult]:
        """Try to use iCIMS JSON API if available"""
        try:
            # Extract job ID from URL
            match = re.search(r'job=(\d+)', job_url)
            if not match:
                return None
            
            job_id = match.group(1)
            base_url = job_url.split('/jobs')[0]
            api_url = f"{base_url}/jobs/{job_id}?json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Note: Most iCIMS instances don't allow API apply
                        # This is just for data extraction
                        print(f"iCIMS API data: {data.get('title', 'Unknown')}")
                        return None
        except Exception as e:
            print(f"iCIMS API attempt failed: {e}")
        
        return None
    
    async def _browser_apply(self, job_url: str) -> ApplicationResult:
        """Browser-based iCIMS application"""
        session = await self.browser.create_stealth_session("icims")
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
            
            # Find Apply button (iCIMS has various button styles)
            apply_btn = await page.wait_for_selector(
                '.iCIMS_Button:has-text("Apply Now"), '
                'a:has-text("Apply for this job online"), '
                'button:has-text("Apply"), '
                'input[value="Apply"]',
                timeout=10000
            )
            await apply_btn.click()
            await self._human_delay(2, 4)
            
            # Check if new tab opened
            pages = page.context.pages
            if len(pages) > 1:
                page = pages[-1]  # Switch to new tab
            
            # Check for login required
            if await page.query_selector('text="Sign In"'):
                await self._handle_icims_login(page)
            
            # Fill application form
            await self._fill_with_mapper(page)
            
            # Submit
            submit_btn = await page.query_selector(
                '.iCIMS_Button:has-text("Submit"), '
                'input[value="Submit"], '
                'button[type="submit"]'
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
    
    async def _handle_icims_login(self, page):
        """Handle iCIMS login or registration"""
        # Look for guest apply option
        guest = await page.query_selector('text="Apply as Guest"')
        if guest:
            await guest.click()
            await self._human_delay(2, 3)
            return
        
        # Fill registration form
        await self._fill_with_mapper(page, ['email', 'first_name', 'last_name'])
        
        # Create account
        create_btn = await page.query_selector('button:has-text("Create"), input[value="Create"]')
        if create_btn:
            await create_btn.click()
            await self._human_delay(3, 5)
