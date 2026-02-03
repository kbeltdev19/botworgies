"""
LinkedIn Job Board Handler

Handles LinkedIn job pages - extracts job details and detects Easy Apply vs external apply
"""

import asyncio
from typing import Optional
from ..models import ATSPlatform, ApplicationResult, UserProfile
from ..browserbase_manager import BrowserBaseManager
from .base_handler import BaseATSHandler


class LinkedInHandler(BaseATSHandler):
    """Handler for LinkedIn job board"""
    
    IDENTIFIERS = ['linkedin.com/jobs/view', 'linkedin.com/jobs/cmp', 'linkedin.com/job/view']
    PLATFORM = ATSPlatform.LINKEDIN
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is a LinkedIn job page"""
        url_lower = url.lower()
        return any(id in url_lower for id in self.IDENTIFIERS)
    
    async def apply(self, job_url: str) -> ApplicationResult:
        """
        Apply to a LinkedIn job
        
        LinkedIn jobs either:
        1. Have "Easy Apply" button (in-app application)
        2. Have "Apply" button that redirects to company ATS
        """
        session = None
        try:
            session = await self.browser.create_stealth_session(platform="linkedin")
            page = session["page"]
            
            print(f"Navigating to LinkedIn job: {job_url}")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            
            # Check for Easy Apply button
            easy_apply_selectors = [
                'button:has-text("Easy Apply")',
                '[data-control-name="jobdetails_topcard_inapply"]',
                '.jobs-apply-button--top-card',
                'button.jobs-apply-button',
            ]
            
            for selector in easy_apply_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        text = await button.text_content() or ""
                        if "easy" in text.lower():
                            print("Found LinkedIn Easy Apply button")
                            return ApplicationResult(
                                success=False,
                                status="easy_apply_requires_login",
                                error_message="LinkedIn Easy Apply requires LinkedIn login - not automated",
                                platform=ATSPlatform.LINKEDIN,
                                job_id=job_url,
                                job_url=job_url,
                                session_id=session["session_id"]
                            )
                except:
                    continue
            
            # Check for external "Apply" button
            external_apply_selectors = [
                'a:has-text("Apply")',
                '[data-control-name="jobdetails_topcard_external_apple"]',
                'a.jobs-apply-button[href]',
                'button:has-text("Apply on company website")',
            ]
            
            for selector in external_apply_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        href = await button.get_attribute('href')
                        if href and href.startswith('http'):
                            print(f"Found external apply link: {href}")
                            return ApplicationResult(
                                success=False,
                                status="redirect",
                                error_message=f"Redirect to company ATS: {href}",
                                platform=ATSPlatform.LINKEDIN,
                                job_id=job_url,
                                job_url=job_url,
                                session_id=session["session_id"],
                                redirect_url=href
                            )
                except:
                    continue
            
            return ApplicationResult(
                success=False,
                status="unknown_format",
                error_message="Could not detect application method on LinkedIn page",
                platform=ATSPlatform.LINKEDIN,
                job_id=job_url,
                job_url=job_url,
                session_id=session["session_id"]
            )
            
        except Exception as e:
            print(f"LinkedIn application error: {e}")
            return ApplicationResult(
                success=False,
                status="error",
                error_message=str(e),
                platform=ATSPlatform.LINKEDIN,
                job_id=job_url,
                job_url=job_url,
                session_id=session["session_id"] if session else None
            )
        finally:
            if session:
                await self.browser.close_session(session["session_id"])
