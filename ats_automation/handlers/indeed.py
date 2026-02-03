"""
Indeed Job Board Handler

Handles Indeed job pages - extracts job details and redirects to company ATS if needed
"""

from typing import Optional
from playwright.async_api import Page
from ..models import ATSPlatform, ApplicationResult, UserProfile
from ..browserbase_manager import BrowserBaseManager
from .base import BaseHandler


class IndeedHandler(BaseHandler):
    """Handler for Indeed job board"""
    
    PLATFORM = ATSPlatform.INDEED
    
    # URL patterns that indicate Indeed
    URL_PATTERNS = [
        "indeed.com/viewjob",
        "indeed.com/rc/clk",
        "indeed.com/apply",
    ]
    
    def __init__(self, browser: BrowserBaseManager, profile: UserProfile, ai_client=None):
        super().__init__(browser, profile, ai_client)
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is an Indeed job page"""
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in self.URL_PATTERNS)
    
    async def apply(self, job_url: str, auto_submit: bool = False) -> ApplicationResult:
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
            await asyncio.sleep(3)  # Let page settle
            
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
                                message=f"Redirect to company ATS: {href}",
                                platform=ATSPlatform.INDEED,
                                redirect_url=href
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
                                    message=f"Redirected to: {new_url}",
                                    platform=ATSPlatform.INDEED,
                                    redirect_url=new_url
                                )
                except Exception as e:
                    print(f"Error checking selector {selector}: {e}")
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
                        # Indeed Easy Apply is complex - for now mark as manual
                        return ApplicationResult(
                            success=False,
                            status="manual_required",
                            message="Indeed Easy Apply detected - manual application required",
                            platform=ATSPlatform.INDEED
                        )
                except:
                    continue
            
            # If we get here, couldn't determine application method
            return ApplicationResult(
                success=False,
                status="unknown_format",
                message="Could not detect application method on Indeed page",
                platform=ATSPlatform.INDEED
            )
            
        except Exception as e:
            print(f"Indeed application error: {e}")
            return ApplicationResult(
                success=False,
                status="error",
                message=str(e),
                platform=ATSPlatform.INDEED
            )
        finally:
            if session:
                await self.browser.close_session(session["session_id"])
    
    async def get_job_details(self, job_url: str) -> dict:
        """Extract job details from Indeed page"""
        session = None
        try:
            session = await self.browser.create_stealth_session(platform="indeed")
            page = session["page"]
            
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            
            details = {
                "title": "",
                "company": "",
                "location": "",
                "description": ""
            }
            
            # Try to extract job title
            title_selectors = ['h1', '[data-testid="job-title"]', '.jobTitle']
            for sel in title_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        details["title"] = await el.text_content() or ""
                        break
                except:
                    continue
            
            # Try to extract company
            company_selectors = ['[data-testid="company-name"]', '[data-company-name]', '.companyName']
            for sel in company_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        details["company"] = await el.text_content() or ""
                        break
                except:
                    continue
            
            return details
            
        except Exception as e:
            print(f"Error getting Indeed job details: {e}")
            return {}
        finally:
            if session:
                await self.browser.close_session(session["session_id"])


import asyncio  # For async sleep
