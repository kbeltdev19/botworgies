"""
LinkedIn Job Board Handler

Handles LinkedIn job pages - extracts job details and detects Easy Apply vs external apply
"""

from typing import Optional
from playwright.async_api import Page
from ..models import ATSPlatform, ApplicationResult, UserProfile
from ..browserbase_manager import BrowserBaseManager
from .base import BaseHandler
import asyncio


class LinkedInHandler(BaseHandler):
    """Handler for LinkedIn job board"""
    
    PLATFORM = ATSPlatform.LINKEDIN
    
    # URL patterns that indicate LinkedIn
    URL_PATTERNS = [
        "linkedin.com/jobs/view",
        "linkedin.com/jobs/cmp",
        "linkedin.com/job/view",
    ]
    
    def __init__(self, browser: BrowserBaseManager, profile: UserProfile, ai_client=None):
        super().__init__(browser, profile, ai_client)
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is a LinkedIn job page"""
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in self.URL_PATTERNS)
    
    async def apply(self, job_url: str, auto_submit: bool = False) -> ApplicationResult:
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
            await asyncio.sleep(3)  # Let page settle
            
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
                            # LinkedIn Easy Apply is complex - requires login
                            return ApplicationResult(
                                success=False,
                                status="easy_apply_requires_login",
                                message="LinkedIn Easy Apply requires LinkedIn login - not automated",
                                platform=ATSPlatform.LINKEDIN
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
                                message=f"Redirect to company ATS: {href}",
                                platform=ATSPlatform.LINKEDIN,
                                redirect_url=href
                            )
                except:
                    continue
            
            # If we get here, couldn't determine application method
            return ApplicationResult(
                success=False,
                status="unknown_format",
                message="Could not detect application method on LinkedIn page",
                platform=ATSPlatform.LINKEDIN
            )
            
        except Exception as e:
            print(f"LinkedIn application error: {e}")
            return ApplicationResult(
                success=False,
                status="error",
                message=str(e),
                platform=ATSPlatform.LINKEDIN
            )
        finally:
            if session:
                await self.browser.close_session(session["session_id"])
    
    async def get_job_details(self, job_url: str) -> dict:
        """Extract job details from LinkedIn page"""
        session = None
        try:
            session = await self.browser.create_stealth_session(platform="linkedin")
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
            title_selectors = ['h1', '[data-testid="job-title"]', '.jobs-unified-top-card__job-title']
            for sel in title_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        details["title"] = await el.text_content() or ""
                        break
                except:
                    continue
            
            # Try to extract company
            company_selectors = ['[data-testid="company-name"]', '.jobs-unified-top-card__company-name']
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
            print(f"Error getting LinkedIn job details: {e}")
            return {}
        finally:
            if session:
                await self.browser.close_session(session["session_id"])
