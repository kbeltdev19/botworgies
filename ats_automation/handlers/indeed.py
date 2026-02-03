"""
Indeed Job Board Handler

Handles Indeed job pages - extracts job details and redirects to company ATS if needed
"""

import asyncio
from typing import Optional
from ..models import ATSPlatform, ApplicationResult, UserProfile
from ..browserbase_manager import BrowserBaseManager
from .base_handler import BaseATSHandler


class IndeedHandler(BaseATSHandler):
    """Handler for Indeed job board"""
    
    IDENTIFIERS = ['indeed.com/viewjob', 'indeed.com/rc/clk', 'indeed.com/apply']
    PLATFORM = ATSPlatform.INDEED
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is an Indeed job page"""
        url_lower = url.lower()
        return any(id in url_lower for id in self.IDENTIFIERS)
    
    async def apply(self, job_url: str) -> ApplicationResult:
        """
        Apply to an Indeed job
        
        Indeed jobs either:
        1. Have "Apply on company site" button (redirect to ATS)
        2. Have Indeed's own application form (rare now)
        """
        session = None
        try:
            session = await self.browser.create_stealth_session(platform="indeed")
            page = session["page"]
            
            print(f"Navigating to Indeed job: {job_url}")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            
            # Check for "Apply on company site" button
            company_site_selectors = [
                'a:has-text("Apply on company site")',
                '[data-testid="apply-on-company-site"]',
                'a[href*="apply"]:has-text("company")',
                'button:has-text("Apply on company site")',
            ]
            
            for selector in company_site_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        print("Found 'Apply on company site' button - redirecting...")
                        href = await button.get_attribute('href')
                        if href:
                            # Return result indicating redirect needed
                            return ApplicationResult(
                                success=False,
                                status="redirect",
                                error_message=f"Redirect to company ATS: {href}",
                                platform=ATSPlatform.INDEED,
                                job_id=job_url,
                                job_url=job_url,
                                session_id=session["session_id"]
                            )
                        else:
                            # Click and get new URL
                            await button.click()
                            await asyncio.sleep(3)
                            new_url = page.url
                            if new_url != job_url:
                                return ApplicationResult(
                                    success=False,
                                    status="redirect",
                                    error_message=f"Redirected to: {new_url}",
                                    platform=ATSPlatform.INDEED,
                                    job_id=job_url,
                                    job_url=job_url,
                                    session_id=session["session_id"]
                                )
                except Exception as e:
                    continue
            
            # Check for Indeed Easy Apply (rare)
            easy_apply_selectors = [
                'button:has-text("Apply now")',
                '[data-testid="apply-button"]',
                '.indeed-apply-button',
            ]
            
            for selector in easy_apply_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        print("Found Indeed Easy Apply button")
                        return ApplicationResult(
                            success=False,
                            status="manual_required",
                            error_message="Indeed Easy Apply detected - manual application required",
                            platform=ATSPlatform.INDEED,
                            job_id=job_url,
                            job_url=job_url,
                            session_id=session["session_id"]
                        )
                except:
                    continue
            
            return ApplicationResult(
                success=False,
                status="unknown_format",
                error_message="Could not detect application method on Indeed page",
                platform=ATSPlatform.INDEED,
                job_id=job_url,
                job_url=job_url,
                session_id=session["session_id"]
            )
            
        except Exception as e:
            print(f"Indeed application error: {e}")
            return ApplicationResult(
                success=False,
                status="error",
                error_message=str(e),
                platform=ATSPlatform.INDEED,
                job_id=job_url,
                job_url=job_url,
                session_id=session["session_id"] if session else None
            )
        finally:
            if session:
                await self.browser.close_session(session["session_id"])
