"""
AngelList/Wellfound Handler
Startup-focused platform
"""

import asyncio
from typing import Optional
from ..models import ApplicationResult, ATSPlatform
from .base_handler import BaseATSHandler


class AngelListHandler(BaseATSHandler):
    """Handler for AngelList/Wellfound"""
    
    IDENTIFIERS = ['angel.co', 'wellfound.com', 'angel.list']
    PLATFORM = ATSPlatform.ANGELLIST
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is AngelList/Wellfound job posting"""
        url_lower = url.lower()
        return any(id in url_lower for id in self.IDENTIFIERS)
    
    async def apply(self, job_url: str) -> ApplicationResult:
        """Apply to AngelList/Wellfound job"""
        session = await self.browser.create_stealth_session("angellist")
        page = session["page"]
        session_id = session["session_id"]
        
        try:
            await page.goto(job_url, wait_until='networkidle')
            await self._human_delay(2, 3)
            
            # Check if it's actually a Greenhouse/Lever embed
            content = await page.content()
            if 'greenhouse' in content.lower():
                # Delegate to Greenhouse handler
                from .greenhouse import GreenhouseHandler
                gh = GreenhouseHandler(self.browser, self.profile, self.ai_client)
                return await gh.apply(job_url)
            
            # Native AngelList apply
            apply_btn = await page.wait_for_selector(
                'text="Apply", '
                'text="Apply Now", '
                'button:has-text("Apply")',
                timeout=10000
            )
            await apply_btn.click()
            await self._human_delay(2, 3)
            
            # Check if login required
            if await page.query_selector('text="Sign in"'):
                await self._handle_angellist_login(page)
            
            # Fill application form
            await self._fill_with_mapper(page)
            
            # Submit
            submit_btn = await page.query_selector(
                'button[type="submit"], '
                'button:has-text("Submit"), '
                'input[value="Submit"]'
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
    
    async def _handle_angellist_login(self, page):
        """Handle AngelList login"""
        # AngelList often allows application without full login
        # Look for quick apply option
        quick_apply = await page.query_selector('text="Quick Apply"')
        if quick_apply:
            await quick_apply.click()
            await self._human_delay(2, 3)
            return
        
        # Fill email for application
        email_field = await page.query_selector('input[type="email"]')
        if email_field:
            await email_field.fill(self.profile.email)
        
        continue_btn = await page.query_selector('button:has-text("Continue"), button:has-text("Next")')
        if continue_btn:
            await continue_btn.click()
            await self._human_delay(2, 3)


class GreenhouseHandler(BaseATSHandler):
    """Handler for Greenhouse ATS (often used by startups via AngelList)"""
    
    IDENTIFIERS = ['greenhouse.io', 'boards.greenhouse.io']
    PLATFORM = ATSPlatform.GREENHOUSE
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is Greenhouse job posting"""
        url_lower = url.lower()
        return any(id in url_lower for id in self.IDENTIFIERS)
    
    async def apply(self, job_url: str) -> ApplicationResult:
        """Apply to Greenhouse job"""
        session = await self.browser.create_stealth_session("generic")
        page = session["page"]
        session_id = session["session_id"]
        
        try:
            await page.goto(job_url, wait_until='networkidle')
            await self._human_delay(2, 3)
            
            # Greenhouse Apply button
            apply_btn = await page.wait_for_selector(
                'a:has-text("Apply"), '
                'button:has-text("Apply"), '
                '#application',
                timeout=10000
            )
            await apply_btn.click()
            await self._human_delay(2, 3)
            
            # Fill form
            await self._fill_with_mapper(page)
            
            # Submit
            submit_btn = await page.query_selector(
                'input[type="submit"], '
                'button[type="submit"], '
                '#submit'
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
