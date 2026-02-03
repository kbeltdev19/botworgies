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
            
            # Wait for page to fully load (Indeed loads content dynamically)
            await asyncio.sleep(5)
            
            # Try multiple strategies to find apply button
            # Strategy 1: Look for "Apply on company site" button (most common)
            company_site_selectors = [
                'a:has-text("Apply on company site")',
                'a:has-text("Apply on Company Site")',  
                'button:has-text("Apply on company site")',
                '[data-testid="apply-on-company-site"]',
                'a[href*="apply"]:has-text("company")',
                '.iaIcon + a',  # Icon followed by link pattern
                'a[class*="apply"][href]',
            ]
            
            for selector in company_site_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        href = await button.get_attribute('href')
                        if href:
                            print(f"Found 'Apply on company site' button: {href[:80]}...")
                            return ApplicationResult(
                                success=False,
                                status="redirect",
                                error_message=f"Apply on company site: {href}",
                                platform=ATSPlatform.INDEED,
                                job_id=job_url,
                                job_url=job_url,
                                session_id=session["session_id"],
                                redirect_url=href
                            )
                except:
                    continue
            
            # Strategy 2: Look for any external apply link
            external_link_selectors = [
                'a[rel="nofollow"][target="_blank"]',
                'a[href^="http"]:has-text("Apply")',
                'a[data-tn-element="jobTitle"]',
            ]
            
            for selector in external_link_selectors:
                try:
                    links = await page.query_selector_all(selector)
                    for link in links:
                        href = await link.get_attribute('href')
                        text = await link.text_content() or ""
                        if href and 'indeed.com' not in href and ('apply' in text.lower() or 'job' in text.lower()):
                            print(f"Found external link: {href[:80]}...")
                            return ApplicationResult(
                                success=False,
                                status="redirect",
                                error_message=f"External apply link: {href}",
                                platform=ATSPlatform.INDEED,
                                job_id=job_url,
                                job_url=job_url,
                                session_id=session["session_id"],
                                redirect_url=href
                            )
                except:
                    continue
            
            # Strategy 3: Check for Indeed Easy Apply (rare)
            easy_apply_selectors = [
                'button:has-text("Apply now")',
                '[data-testid="apply-button"]',
                '.indeed-apply-button',
                'button:has-text("Apply with Indeed")',
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
            
            # Strategy 4: Look for job description link that might contain apply info
            try:
                page_content = await page.content()
                if 'apply' in page_content.lower():
                    # Page has apply-related content but we couldn't find button
                    # This might be a job that requires visiting company site
                    print("Page contains 'apply' content but no button found - likely external apply")
                    return ApplicationResult(
                        success=False,
                        status="external_redirect",
                        error_message="External application required - visit company website",
                        platform=ATSPlatform.INDEED,
                        job_id=job_url,
                        job_url=job_url,
                        session_id=session["session_id"]
                    )
            except:
                pass
            
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
