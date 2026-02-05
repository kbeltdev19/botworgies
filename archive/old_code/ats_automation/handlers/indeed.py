"""
Indeed Job Board Handler (Improved)

Handles Indeed job pages - extracts job details and redirects to company ATS if needed
Includes: retry logic, multiple selectors, faster processing
"""

import asyncio
from typing import Optional
from ..models import ATSPlatform, ApplicationResult, UserProfile
from ..browserbase_manager import BrowserBaseManager
from .base_handler import BaseATSHandler
from ..utils.retry import RetryConfig, should_retry


class IndeedHandler(BaseATSHandler):
    """Handler for Indeed job board with retry logic"""
    
    IDENTIFIERS = ['indeed.com/viewjob', 'indeed.com/rc/clk', 'indeed.com/apply']
    PLATFORM = ATSPlatform.INDEED
    
    # All possible selectors for apply buttons (ordered by specificity)
    COMPANY_SITE_SELECTORS = [
        'a:has-text("Apply on company site")',
        'a:has-text("Apply on Company Site")',
        'a:has-text("Apply On Company Site")',
        'button:has-text("Apply on company site")',
        '[data-testid="apply-on-company-site"]',
        'a[href*="apply"]:has-text("company")',
        '.iaIcon + a',
        'a[class*="apply"][href]',
        'a[href*="applystart"]',
        'a[href*="indeed.com/applystart"]',
        'button:has-text("Apply now")',
        'a:has-text("Apply externally")',
        '[data-testid="job-apply-button"]',
        'a:has-text("Apply with Indeed")',
        'button[data-testid="apply-button"]',
    ]
    
    EXTERNAL_LINK_SELECTORS = [
        'a[rel="nofollow"][target="_blank"]',
        'a[href^="http"]:has-text("Apply")',
        'a[data-tn-element="jobTitle"]',
        'a[href*="boards.greenhouse.io"]',
        'a[href*="jobs.lever.co"]',
        'a[href*="myworkdayjobs.com"]',
        'a[href*="smartrecruiters.com"]',
        'a[href*="careers"][target="_blank"]',
    ]
    
    EASY_APPLY_SELECTORS = [
        'button:has-text("Apply now")',
        '[data-testid="apply-button"]',
        '.indeed-apply-button',
        'button:has-text("Apply with Indeed")',
        'button[data-testid="indeed-apply-button"]',
    ]
    
    async def can_handle(self, url: str) -> bool:
        """Check if URL is an Indeed job page"""
        url_lower = url.lower()
        return any(id in url_lower for id in self.IDENTIFIERS)
    
    async def apply(self, job_url: str, attempt: int = 0) -> ApplicationResult:
        """
        Apply to an Indeed job with retry logic
        
        Args:
            job_url: URL of the job
            attempt: Current retry attempt (0 = first try)
        """
        result = await self._try_apply(job_url, attempt)
        
        # Retry on specific failures
        if should_retry(result.status) and attempt < RetryConfig.INDEED_RETRIES:
            wait_time = RetryConfig.INDEED_DELAY * (2 ** attempt)
            print(f"⏳ Retrying Indeed job (attempt {attempt + 1}/{RetryConfig.INDEED_RETRIES + 1}) in {wait_time}s...")
            await asyncio.sleep(wait_time)
            return await self.apply(job_url, attempt + 1)
        
        return result
    
    async def _try_apply(self, job_url: str, attempt: int = 0) -> ApplicationResult:
        """Internal apply method"""
        session = None
        try:
            session = await self.browser.create_stealth_session(platform="indeed")
            page = session["page"]
            
            print(f"Navigating to Indeed job: {job_url}")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            
            # Dynamic wait: start with 2s, add 1s per retry attempt (max 4s)
            wait_time = min(2 + attempt, 4)
            await asyncio.sleep(wait_time)
            
            # Strategy 1: Look for "Apply on company site" button (most common)
            for selector in self.COMPANY_SITE_SELECTORS:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        href = await button.get_attribute('href')
                        if href:
                            print(f"✅ Found 'Apply on company site' button: {href[:60]}...")
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
            for selector in self.EXTERNAL_LINK_SELECTORS:
                try:
                    links = await page.query_selector_all(selector)
                    for link in links[:10]:  # Limit to first 10
                        href = await link.get_attribute('href')
                        text = await link.text_content() or ""
                        if href and 'indeed.com' not in href and ('apply' in text.lower() or 'job' in text.lower()):
                            print(f"✅ Found external link: {href[:60]}...")
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
            for selector in self.EASY_APPLY_SELECTORS:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        print("✅ Found Indeed Easy Apply button")
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
                content_lower = page_content.lower()
                
                if 'apply' in content_lower:
                    # Check if it mentions external apply
                    if any(marker in content_lower for marker in ['company site', 'external', 'visit']):
                        print("✅ External application detected from page content")
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
            
            # If we get here, couldn't detect application method
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
            print(f"❌ Indeed application error: {e}")
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
